from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EARNINGS = ROOT / "data/research/v2/earnings_anomaly_recall.json"
PRICE = ROOT / "data/research/v2/full_market_price_structure.json"
OUT = ROOT / "data/research/v2/shadow_crosscheck.json"
TZ = ZoneInfo("Asia/Shanghai")

STRUCTURE_PRIORITY = {"breakout":4.0,"pullback":3.5,"trend_continuation":3.0,"transition":1.5,"base_not_started":1.0,"overheated":-1.0,"damaged":-3.0,"unavailable":-5.0}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def merged_row(item: dict, p: dict) -> dict:
    structure, chase = p.get("structure_type"), p.get("chase_risk")
    chase_bonus = {"low":1.0,"medium":0.0,"high":-2.0}.get(chase,0.0)
    score = float(item.get("triage_score") or 0.0) + 10.0*STRUCTURE_PRIORITY.get(structure,0.0) + 5.0*chase_bonus
    eligible = bool(item.get("low_risk_eligible", True) and p.get("low_risk_eligible", True))
    return {
        "code":item.get("code"),"name":item.get("name"),"earnings_status":item.get("status"),"triage_score":item.get("triage_score"),
        "earnings_reason":item.get("reason"),"metrics":item.get("metrics"),"quality_review_required":item.get("quality_review_required"),
        "quality_flags":item.get("quality_flags"),"recurring_profit_status":item.get("recurring_profit_status"),
        "risk_warning":bool(item.get("risk_warning") or p.get("risk_warning")),"low_risk_eligible":eligible,
        "current_price":p.get("current_price"),"structure_type":structure,"action":p.get("action"),"chase_risk":chase,
        "ma20":p.get("ma20"),"ma60":p.get("ma60"),"distance_to_ma20_pct":p.get("distance_to_ma20_pct"),"distance_to_ma60_pct":p.get("distance_to_ma60_pct"),
        "return_10d_pct":p.get("return_10d_pct"),"return_20d_pct":p.get("return_20d_pct"),"relative_strength_20d_vs_market_pct":p.get("relative_strength_20d_vs_market_pct"),
        "volume_ratio_1d_vs_20d":p.get("volume_ratio_1d_vs_20d"),"volume_ratio_5d_vs_20d":p.get("volume_ratio_5d_vs_20d"),"breakout_confirmed":p.get("breakout_confirmed"),
        "price_discovery":p.get("price_discovery"),"first_effective_resistance":p.get("first_effective_resistance"),"support_invalidation":p.get("support_invalidation"),
        "crosscheck_score":round(score,3),
    }


def main() -> int:
    e, p = load(EARNINGS), load(PRICE)
    companies = p.get("companies") or {}
    rows = []
    for item in e.get("candidates") or []:
        code = str(item.get("code") or "").zfill(6)
        pr = companies.get(code)
        if pr and pr.get("data_status") == "verified":
            rows.append(merged_row(item, pr))

    pass_all = [x for x in rows if x["earnings_status"] == "pass"]
    uncertain_all = [x for x in rows if x["earnings_status"] == "uncertain"]
    excluded_risk = [x for x in pass_all if not x["low_risk_eligible"]]
    pass_rows = [x for x in pass_all if x["low_risk_eligible"]]
    right_types = {"breakout","pullback","trend_continuation"}
    pass_right = [x for x in pass_rows if x["structure_type"] in right_types and x["chase_risk"] != "high"]
    pass_early = [x for x in pass_rows if x["structure_type"] in {"base_not_started","transition"}]
    pass_overheated = [x for x in pass_rows if x["structure_type"] == "overheated" or x["chase_risk"] == "high"]
    pass_damaged = [x for x in pass_rows if x["structure_type"] == "damaged"]
    quality_review = [x for x in pass_rows if x.get("quality_review_required")]

    key = lambda x: (-x["crosscheck_score"], -float(x.get("triage_score") or 0.0), x["code"])
    for xs in (pass_right, pass_early, pass_overheated, pass_damaged, quality_review): xs.sort(key=key)

    payload = {
        "schema_version":2,"mode":"shadow","generated_at":datetime.now(TZ).isoformat(),"reference_trade_date":e.get("reference_trade_date"),
        "purpose":"Case-free diagnostic only. It crosses broad earnings recall with full-market price state; it is not company-research, valuation, driver validation or final ranking.",
        "counts":{
            "earnings_pass_with_price":len(pass_all),"earnings_uncertain_with_price":len(uncertain_all),"earnings_pass_low_risk_eligible":len(pass_rows),
            "excluded_risk_warning_pass":len(excluded_risk),"pass_right_low_medium_chase":len(pass_right),"pass_base_or_transition":len(pass_early),
            "pass_overheated_or_high_chase":len(pass_overheated),"pass_damaged":len(pass_damaged),"pass_quality_review_required":len(quality_review),
        },
        "top_pass_right_low_medium_chase":pass_right[:40],"top_pass_base_or_transition":pass_early[:40],
        "top_pass_overheated_or_high_chase":pass_overheated[:20],"top_pass_damaged":pass_damaged[:20],"top_quality_review_required":quality_review[:30],
        "discipline":[
            "No fixed stock is required to appear.",
            "Risk-warning securities are scanned for coverage but cannot enter low-risk opportunity-like lists.",
            "Headline earnings growth is recall evidence only; recurring profit, one-off items, cash flow, driver exposure and the 1-2Q bridge must be verified before admission.",
            "crosscheck_score is diagnostic ordering only and cannot determine eligibility."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"ok",**payload["counts"]},ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
