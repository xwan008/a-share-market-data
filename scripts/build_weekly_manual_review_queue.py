from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIGHT = ROOT / "data" / "research" / "pipeline" / "weekly_light_recall.json"
T2 = ROOT / "data" / "research" / "pipeline" / "t2_company_recall.json"
OLD = ROOT / "data" / "research" / "weekly_fundamental_opportunity_pool.json"
OUT = ROOT / "data" / "research" / "pipeline" / "weekly_manual_review_queue.json"


def t2_codes(data):
    out=set()
    for chain in data.get("t2_subchains",[]):
        for link in chain.get("value_chain_links",[]):
            for row in link.get("companies",[]): out.add(str(row.get("code") or "").zfill(6))
    return out


def main():
    light=json.loads(LIGHT.read_text(encoding="utf-8"))
    t2=json.loads(T2.read_text(encoding="utf-8"))
    old=json.loads(OLD.read_text(encoding="utf-8")) if OLD.exists() else {"candidates":[]}
    tc=t2_codes(t2)
    old_codes={str(x.get("code") or "").zfill(6) for x in old.get("candidates",[]) if x.get("code")}
    rows=[]
    for code,item in light.get("screen_results",{}).items():
        if item.get("status") not in {"pass","uncertain"}: continue
        metrics=item.get("metrics",{})
        name=str(item.get("name") or code)
        is_st=("ST" in name.upper()) or ("退" in name)
        reasons=[]
        priority=0.0
        if code in old_codes: reasons.append("legacy_pool_migration"); priority+=200
        if metrics.get("q3_positive_forecast"): reasons.append("explicit_q3_forecast"); priority+=150
        if code not in tc and not is_st:
            profit=metrics.get("net_profit") or 0
            rev=metrics.get("revenue") or 0
            py=metrics.get("net_profit_yoy_pct") or 0
            ry=metrics.get("revenue_yoy_pct") or 0
            qoq=metrics.get("net_profit_qoq_pct") or 0
            if profit>=100_000_000 and rev>=500_000_000 and py>=30 and ry>=5:
                reasons.append("strong_h1_non_t2")
                priority+=min(py,300)*0.25+min(ry,100)*0.2+min(max(qoq,0),200)*0.1
        if reasons:
            rows.append({"code":code,"name":name,"priority":round(priority,3),"reasons":reasons,"covered_by_t2":code in tc,"light_status":item.get("status"),"light_reason":item.get("reason"),"metrics":metrics})
    rows.sort(key=lambda x:(-x["priority"],x["code"]))
    # Keep all forecast and legacy names; cap extra H1-only manual web work to top 40.
    mandatory=[x for x in rows if "legacy_pool_migration" in x["reasons"] or "explicit_q3_forecast" in x["reasons"]]
    mandatory_codes={x["code"] for x in mandatory}
    extras=[x for x in rows if x["code"] not in mandatory_codes][:40]
    queue=mandatory+extras
    queue.sort(key=lambda x:(-x["priority"],x["code"]))
    payload={"schema_version":1,"queue_count":len(queue),"mandatory_count":len(mandatory),"extra_h1_review_count":len(extras),"queue":queue}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k!="queue"},ensure_ascii=False))

if __name__=="__main__": main()
