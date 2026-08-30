from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data/latest.json"
HISTORY_DIR = ROOT / "data/history_shards"
OUT = ROOT / "data/research/v2/full_market_price_structure.json"
TZ = ZoneInfo("Asia/Shanghai")
MIN_POINTS = 120
TARGET_POINTS = 180


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def load(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def rows_for(code: str) -> list[dict]:
    shard = load(HISTORY_DIR / f"{code[:4]}.json", {})
    item = (shard.get("stocks") or {}).get(code) or {}
    rows = []
    for r in item.get("history", []):
        close, high, low = f(r.get("close")), f(r.get("high")), f(r.get("low"))
        if close is None or high is None or low is None or close <= 0:
            continue
        rows.append({
            "date": str(r.get("date") or ""),
            "open": f(r.get("open")),
            "close": close,
            "high": high,
            "low": low,
            "volume": f(r.get("volume")),
        })
    return sorted([r for r in rows if r["date"]], key=lambda x: x["date"])[-TARGET_POINTS:]


def sma(values: list[float], n: int, offset: int = 0):
    end = len(values) - offset if offset else len(values)
    start = end - n
    if start < 0 or end <= 0:
        return None
    part = values[start:end]
    return sum(part) / len(part) if len(part) == n else None


def pivots(rows: list[dict], window: int = 3):
    highs, lows = [], []
    for i in range(window, len(rows) - window):
        hi, lo = rows[i]["high"], rows[i]["low"]
        if all(hi >= rows[j]["high"] for j in range(i-window, i+window+1)):
            highs.append({"date": rows[i]["date"], "price": hi})
        if all(lo <= rows[j]["low"] for j in range(i-window, i+window+1)):
            lows.append({"date": rows[i]["date"], "price": lo})
    return highs, lows


def atr_pct(rows: list[dict], n: int = 14):
    if len(rows) < n + 1:
        return None
    trs = []
    for i in range(len(rows)-n, len(rows)):
        prev = rows[i-1]["close"]
        tr = max(rows[i]["high"]-rows[i]["low"], abs(rows[i]["high"]-prev), abs(rows[i]["low"]-prev))
        trs.append(tr)
    current = rows[-1]["close"]
    return (sum(trs)/len(trs))/current if current > 0 else None


def base_metrics(code: str, name: str, rows: list[dict], quote: dict, reference_date: str):
    if len(rows) < MIN_POINTS:
        return {"code": code, "name": name, "data_status": "unavailable", "reason": f"history_insufficient:{len(rows)}"}
    if rows[-1]["date"] != reference_date:
        return {"code": code, "name": name, "data_status": "unavailable", "reason": f"history_stale:{rows[-1]['date']}!={reference_date}"}

    closes = [r["close"] for r in rows]
    current = f(quote.get("price")) or closes[-1]
    ma20, ma60 = sma(closes, 20), sma(closes, 60)
    ma20_5, ma60_5 = sma(closes, 20, 5), sma(closes, 60, 5)
    highs, lows = pivots(rows[-120:], 3)
    recent_highs, recent_lows = highs[-3:], lows[-3:]
    hh = len(recent_highs) >= 2 and recent_highs[-1]["price"] > recent_highs[-2]["price"]
    hl = len(recent_lows) >= 2 and recent_lows[-1]["price"] > recent_lows[-2]["price"]

    ret10 = current / closes[-11] - 1 if len(closes) >= 11 else None
    ret20 = current / closes[-21] - 1 if len(closes) >= 21 else None
    dist20 = current / ma20 - 1 if ma20 else None
    dist60 = current / ma60 - 1 if ma60 else None
    slope20 = ma20 / ma20_5 - 1 if ma20 and ma20_5 else None
    slope60 = ma60 / ma60_5 - 1 if ma60 and ma60_5 else None
    prev60_high = max(r["high"] for r in rows[-61:-1])
    prev120_high = max(r["high"] for r in rows[-121:-1]) if len(rows) >= 121 else prev60_high
    atp = atr_pct(rows)

    resistance = None
    above = [p for p in highs if p["price"] > current * 1.005]
    if above:
        resistance = min(above, key=lambda x: x["price"])
    elif current < prev120_high * 0.995:
        resistance = {"date": None, "price": prev120_high, "source": "prior_120d_high"}

    support_candidates = [x["price"] for x in recent_lows if x["price"] < current]
    if ma20 and ma20 < current:
        support_candidates.append(ma20)
    if ma60 and ma60 < current:
        support_candidates.append(ma60)
    support = max(support_candidates) if support_candidates else min(r["low"] for r in rows[-20:])

    return {
        "code": code,
        "name": name,
        "data_status": "verified",
        "data_date": rows[-1]["date"],
        "history_points": len(rows),
        "current_price": round(current, 4),
        "ma20": round(ma20, 4),
        "ma60": round(ma60, 4),
        "ma20_slope_5d_pct": round(slope20*100, 2) if slope20 is not None else None,
        "ma60_slope_5d_pct": round(slope60*100, 2) if slope60 is not None else None,
        "return_10d_pct": round(ret10*100, 2) if ret10 is not None else None,
        "return_20d_pct": round(ret20*100, 2) if ret20 is not None else None,
        "distance_to_ma20_pct": round(dist20*100, 2) if dist20 is not None else None,
        "distance_to_ma60_pct": round(dist60*100, 2) if dist60 is not None else None,
        "atr14_pct": round(atp*100, 2) if atp is not None else None,
        "prior_60d_high": round(prev60_high, 4),
        "prior_120d_high": round(prev120_high, 4),
        "higher_high": hh,
        "higher_low": hl,
        "first_effective_resistance": resistance,
        "support_invalidation": round(support, 4) if support else None,
        "raw_return_20d": ret20,
    }


def classify(row: dict, market_ret20: float):
    if row.get("data_status") != "verified":
        row.update({"structure_type": "unavailable", "action": "unavailable", "chase_risk": None})
        return row

    p, ma20, ma60 = row["current_price"], row["ma20"], row["ma60"]
    d20 = (row.get("distance_to_ma20_pct") or 0)/100
    d60 = (row.get("distance_to_ma60_pct") or 0)/100
    r10 = (row.get("return_10d_pct") or 0)/100
    r20 = row.get("raw_return_20d") or 0
    s20 = (row.get("ma20_slope_5d_pct") or 0)/100
    s60 = (row.get("ma60_slope_5d_pct") or 0)/100
    atr = (row.get("atr14_pct") or 0)/100
    rs20 = r20 - market_ret20
    row["relative_strength_20d_vs_market_pct"] = round(rs20*100, 2)

    if d20 > 0.12 or r10 > 0.18 or (atr > 0.06 and r10 > 0.12):
        chase = "high"
    elif d20 > 0.07 or r10 > 0.12 or d60 > 0.18:
        chase = "medium"
    else:
        chase = "low"

    above = p > ma20 > ma60
    slopes_up = s20 > 0 and s60 >= 0
    breakout60 = p >= row["prior_60d_high"] * 0.995
    breakout120 = p >= row["prior_120d_high"] * 0.995
    structure_up = row.get("higher_high") or row.get("higher_low")

    if above and slopes_up and (breakout120 or breakout60) and chase == "high":
        stype, action = "overheated", "wait_pullback"
    elif above and slopes_up and (breakout120 or breakout60):
        stype, action = "breakout", "participate" if chase == "low" else "watch_breakout"
    elif above and slopes_up and structure_up and rs20 >= -0.02:
        stype, action = "trend_continuation", "participate" if chase == "low" else ("watch_trend" if chase == "medium" else "wait_pullback")
    elif ma20 > ma60 and s60 >= 0 and p > ma60 and abs(d20) <= 0.035 and row.get("higher_low"):
        stype, action = "pullback", "participate" if chase != "high" else "wait_pullback"
    elif p < ma60 and ma20 < ma60 and s20 < 0:
        stype, action = "damaged", "avoid"
    elif abs(ma20/ma60 - 1) <= 0.03 and abs(d20) <= 0.05 and abs(r20) <= 0.10:
        stype, action = "base_not_started", "wait_breakout"
    else:
        stype, action = "transition", "observe"

    row["chase_risk"] = chase
    row["structure_type"] = stype
    row["action"] = action
    row["price_discovery"] = bool(breakout120 and row.get("first_effective_resistance") is None)
    if row["price_discovery"]:
        row["resistance_context"] = "price_discovery_or_new_high; absence of overhead resistance is not a negative signal"
    elif row.get("first_effective_resistance"):
        row["resistance_context"] = "below_known_resistance"
    else:
        row["resistance_context"] = "no_nearby_mapped_resistance"

    support = row.get("support_invalidation")
    if support and support < p:
        row["downside_to_invalidation_pct"] = round((p/support - 1)*100, 2)
    else:
        row["downside_to_invalidation_pct"] = None
    res = row.get("first_effective_resistance")
    if isinstance(res, dict) and f(res.get("price")) and res["price"] > p:
        row["upside_to_first_resistance_pct"] = round((res["price"]/p - 1)*100, 2)
    else:
        row["upside_to_first_resistance_pct"] = None
    row.pop("raw_return_20d", None)
    return row


def main():
    latest = load(LATEST, {})
    stocks = latest.get("stocks", {})
    reference_date = str(latest.get("trade_date") or "")
    base = {}
    market_returns = []
    for code, quote in stocks.items():
        code = str(code).zfill(6)
        rows = rows_for(code)
        row = base_metrics(code, (quote or {}).get("name") or code, rows, quote or {}, reference_date)
        base[code] = row
        if row.get("data_status") == "verified" and isinstance(row.get("raw_return_20d"), (int, float)):
            market_returns.append(row["raw_return_20d"])

    market_ret20 = median(market_returns) if market_returns else 0.0
    results = {code: classify(row, market_ret20) for code, row in base.items()}
    candidates = sorted(code for code, row in results.items() if row.get("structure_type") in {"trend_continuation", "breakout", "pullback"} and row.get("chase_risk") != "high")
    unavailable = sorted(code for code, row in results.items() if row.get("data_status") != "verified")
    counts = {}
    for row in results.values():
        t = row.get("structure_type")
        counts[t] = counts.get(t, 0) + 1

    payload = {
        "schema_version": 1,
        "mode": "shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "reference_trade_date": reference_date,
        "universe_source": "all_mainboard_codes_from_data/latest.json",
        "universe_count": len(stocks),
        "verified_count": len(stocks) - len(unavailable),
        "unavailable_count": len(unavailable),
        "market_median_return_20d_pct": round(market_ret20*100, 2),
        "structure_type_counts": counts,
        "right_candidate_codes": candidates,
        "unavailable_codes": unavailable,
        "companies": results,
        "method_note": "V2 price structure scans the full mainboard independently from fundamental/company research. New highs without overhead resistance are treated as price discovery, not automatic rejection."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "universe": len(stocks), "verified": payload["verified_count"], "right_candidates": len(candidates), "types": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
