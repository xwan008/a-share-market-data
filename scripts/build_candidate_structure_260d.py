from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "data/research/pipeline/common_qualification_pool.json"
LATEST = ROOT / "data/latest.json"
OUT = ROOT / "data/research/pipeline/right_structure_scan.json"
TZ = ZoneInfo("Asia/Shanghai")
URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
BARS = 300


def symbol_for(code: str) -> str:
    return ("sh" if code.startswith(("600", "601", "603", "605")) else "sz") + code


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def fetch(code: str) -> tuple[list[dict], str | None]:
    symbol = symbol_for(code)
    params = {"param": f"{symbol},day,,,{BARS},qfq"}
    last = None
    for attempt in range(4):
        try:
            r = requests.get(URL, params=params, timeout=15, headers={"User-Agent":"Mozilla/5.0 a-share-market-data/1.0"})
            r.raise_for_status()
            node = r.json().get("data", {}).get(symbol, {})
            rows = node.get("qfqday") or node.get("day") or []
            out=[]
            for row in rows:
                if not isinstance(row, list) or len(row)<6: continue
                o,c,h,l,v = f(row[1]),f(row[2]),f(row[3]),f(row[4]),f(row[5])
                if c is None or c<=0: continue
                out.append({"date":str(row[0]),"open":o,"close":c,"high":h,"low":l,"volume":v})
            if len(out)>=200:
                return sorted(out,key=lambda x:x["date"]), None
            last=f"insufficient_rows:{len(out)}"
        except Exception as exc:
            last=f"{type(exc).__name__}:{exc}"
        time.sleep(0.6*(attempt+1))
    return [], last


def pivots(rows: list[dict], window: int=3) -> tuple[list[dict], list[dict]]:
    highs=[]; lows=[]
    for i in range(window,len(rows)-window):
        hi=rows[i]["high"]; lo=rows[i]["low"]
        if hi is not None and all(hi>=rows[j]["high"] for j in range(i-window,i+window+1) if rows[j]["high"] is not None):
            highs.append({"date":rows[i]["date"],"price":hi})
        if lo is not None and all(lo<=rows[j]["low"] for j in range(i-window,i+window+1) if rows[j]["low"] is not None):
            lows.append({"date":rows[i]["date"],"price":lo})
    return highs,lows


def weekly_rows(rows: list[dict]) -> list[dict]:
    buckets={}
    for r in rows:
        y,m,d=map(int,r["date"].split("-"))
        import datetime as dt
        iso=dt.date(y,m,d).isocalendar()
        key=(iso.year,iso.week)
        b=buckets.setdefault(key,{"date":r["date"],"high":r["high"],"low":r["low"],"close":r["close"]})
        b["date"]=r["date"]; b["close"]=r["close"]
        b["high"]=max(x for x in (b["high"],r["high"]) if x is not None)
        b["low"]=min(x for x in (b["low"],r["low"]) if x is not None)
    return list(buckets.values())


def dense_resistance(rows:list[dict], price:float) -> list[float]:
    vals=[r["close"] for r in rows[-252:] if r["close"] is not None and r["close"]>price*1.01]
    if len(vals)<3: return []
    lo=min(vals); hi=max(vals)
    if hi<=lo: return [hi]
    bins=24; width=(hi-lo)/bins
    counts=[0]*bins
    for x in vals:
        idx=min(bins-1,int((x-lo)/width))
        counts[idx]+=1
    zones=[]
    for i,c in enumerate(counts):
        if c>=3:
            zones.append(lo+(i+0.5)*width)
    return zones


def analyze(code:str,name:str,rows:list[dict],quote:dict) -> dict:
    current=f(quote.get("price")) or rows[-1]["close"]
    last_date=rows[-1]["date"]
    closes=[r["close"] for r in rows]
    ma20=sum(closes[-20:])/20 if len(closes)>=20 else None
    ma60=sum(closes[-60:])/60 if len(closes)>=60 else None
    dh,dl=pivots(rows[-120:],3)
    wh,wl=pivots(weekly_rows(rows[-300:]),2)
    daily_res=[x["price"] for x in dh if x["price"]>current*1.01]
    weekly_res=[x["price"] for x in wh if x["price"]>current*1.01]
    high52=max(r["high"] for r in rows[-252:] if r["high"] is not None)
    dense=dense_resistance(rows,current)
    candidates=[]
    for source,vals in (("daily_60_120d",daily_res),("weekly_pivot",weekly_res),("dense_supply",dense)):
        for val in vals:
            candidates.append({"source":source,"price":val})
    if high52>current*1.01:
        candidates.append({"source":"52week_high","price":high52})
    candidates.sort(key=lambda x:x["price"])
    first=candidates[0] if candidates else None

    support_candidates=[x["price"] for x in dl if x["price"]<current]
    if ma20 and ma20<current: support_candidates.append(ma20)
    if ma60 and ma60<current: support_candidates.append(ma60)
    support=max(support_candidates) if support_candidates else min(r["low"] for r in rows[-20:] if r["low"] is not None)

    recent_highs=dh[-3:]
    recent_lows=dl[-3:]
    hh = len(recent_highs)>=2 and recent_highs[-1]["price"]>recent_highs[-2]["price"]
    hl = len(recent_lows)>=2 and recent_lows[-1]["price"]>recent_lows[-2]["price"]
    above20=ma20 is not None and current>=ma20
    above60=ma60 is not None and current>=ma60
    if hh and hl and above20:
        state="bullish_intact"
    elif above20 and (hh or hl or above60):
        state="transition_positive"
    else:
        state="weak_or_damaged"

    upside=((first["price"]/current)-1)*100 if first else None
    downside=((current/support)-1)*100 if support and support>0 and support<current else None
    rr=(upside/downside) if upside is not None and downside and downside>0 else None
    if first is None:
        conclusion="observe_no_resistance_map"
    elif upside<10:
        conclusion="structure_valid_but_insufficient_space" if state!="weak_or_damaged" else "observe"
    elif state=="bullish_intact" and rr is not None and rr>=2:
        conclusion="strong"
    elif state!="weak_or_damaged" and rr is not None and rr>=1.5:
        conclusion="participate"
    else:
        conclusion="observe"
    return {
        "code":code,"name":name,"data_date":last_date,"history_points":len(rows),"current_price":round(current,4),
        "ma20":round(ma20,4) if ma20 else None,"ma60":round(ma60,4) if ma60 else None,
        "structure_state":state,"latest_daily_high_pivots":recent_highs,"latest_daily_low_pivots":recent_lows,
        "pressure_map":candidates[:12],"first_effective_resistance":first,
        "support_invalidation":round(support,4) if support else None,
        "upside_to_first_resistance_pct":round(upside,2) if upside is not None else None,
        "downside_to_invalidation_pct":round(downside,2) if downside is not None else None,
        "risk_reward":round(rr,2) if rr is not None else None,
        "conclusion":conclusion,
    }


def main() -> int:
    common=json.loads(COMMON.read_text(encoding="utf-8"))
    latest=json.loads(LATEST.read_text(encoding="utf-8"))
    stocks=latest.get("stocks",{})
    codes=common.get("common_pool_codes",[])
    results={}; errors={}
    for idx,code in enumerate(codes,1):
        gate=(common.get("future_earnings_gate") or {}).get(code,{})
        name=gate.get("name") or (stocks.get(code) or {}).get("name") or code
        rows,err=fetch(code)
        if err:
            errors[code]=err
            results[code]={"code":code,"name":name,"conclusion":"unavailable","error":err}
        else:
            results[code]=analyze(code,name,rows,stocks.get(code,{}) or {})
        if idx%20==0: print(f"processed {idx}/{len(codes)}")
    valid_date=[r.get("data_date") for r in results.values() if r.get("data_date")]
    date_counts={d:valid_date.count(d) for d in sorted(set(valid_date))}
    payload={
        "schema_version":1,"generated_at":datetime.now(TZ).isoformat(),"common_pool_count":len(codes),
        "requested_history_bars":BARS,"same_date_counts":date_counts,"error_count":len(errors),"errors":errors,"companies":results,
        "right_set_codes":sorted([c for c,r in results.items() if r.get("conclusion") in {"strong","participate"}]),
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"ok","common":len(codes),"right":len(payload["right_set_codes"]),"errors":len(errors),"dates":date_counts},ensure_ascii=False))
    return 0

if __name__=="__main__": raise SystemExit(main())
