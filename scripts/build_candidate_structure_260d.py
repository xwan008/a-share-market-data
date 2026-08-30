from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "data/research/pipeline/common_qualification_pool.json"
LATEST = ROOT / "data/latest.json"
HISTORY_DIR = ROOT / "data/history_shards"
OUT = ROOT / "data/research/pipeline/right_structure_scan.json"
TZ = ZoneInfo("Asia/Shanghai")
LOCAL_WINDOW = 180
CORE_WINDOW = 120
MIN_POINTS = 120
LONG_SUMMARY_MAX_AGE_DAYS = 10


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def local_item(code: str) -> dict | None:
    payload = load_json(HISTORY_DIR / f"{code[:4]}.json", {})
    item = (payload.get("stocks") or {}).get(code)
    return item if isinstance(item, dict) else None


def normalize_rows(item: dict | None) -> list[dict]:
    rows = []
    for row in (item or {}).get("history", []):
        close = f(row.get("close"))
        high = f(row.get("high"))
        low = f(row.get("low"))
        if close is None or close <= 0 or high is None or low is None:
            continue
        rows.append(
            {
                "date": str(row.get("date") or ""),
                "open": f(row.get("open")),
                "close": close,
                "high": high,
                "low": low,
                "volume": f(row.get("volume")),
            }
        )
    return sorted([r for r in rows if r["date"]], key=lambda x: x["date"])[-LOCAL_WINDOW:]


def pivots(rows: list[dict], window: int = 3) -> tuple[list[dict], list[dict]]:
    highs, lows = [], []
    for i in range(window, len(rows) - window):
        hi, lo = rows[i]["high"], rows[i]["low"]
        if all(hi >= rows[j]["high"] for j in range(i - window, i + window + 1)):
            highs.append({"date": rows[i]["date"], "price": hi})
        if all(lo <= rows[j]["low"] for j in range(i - window, i + window + 1)):
            lows.append({"date": rows[i]["date"], "price": lo})
    return highs, lows


def weekly_rows(rows: list[dict]) -> list[dict]:
    buckets: dict[tuple[int, int], dict] = {}
    for row in rows:
        try:
            day = dt.date.fromisoformat(row["date"])
        except ValueError:
            continue
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        if key not in buckets:
            buckets[key] = {
                "date": row["date"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
            }
        else:
            bucket = buckets[key]
            bucket["date"] = row["date"]
            bucket["high"] = max(bucket["high"], row["high"])
            bucket["low"] = min(bucket["low"], row["low"])
            bucket["close"] = row["close"]
    return [buckets[key] for key in sorted(buckets)]


def dense_resistance(rows: list[dict], price: float) -> list[float]:
    vals = [r["close"] for r in rows[-LOCAL_WINDOW:] if r["close"] > price * 1.01]
    if len(vals) < 3:
        return []
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return [hi]
    bins = 24
    width = (hi - lo) / bins
    counts = [0] * bins
    for value in vals:
        idx = min(bins - 1, int((value - lo) / width))
        counts[idx] += 1
    return [lo + (i + 0.5) * width for i, count in enumerate(counts) if count >= 3]


def summary_status(summary: dict, reference_date: str) -> tuple[str, int | None]:
    if not summary:
        return "missing", None
    source_date = summary.get("summary_data_date")
    try:
        ref = dt.date.fromisoformat(reference_date)
        src = dt.date.fromisoformat(str(source_date))
    except (TypeError, ValueError):
        return "invalid_date", None
    age = (ref - src).days
    if age < 0:
        return "future_date", age
    if age > LONG_SUMMARY_MAX_AGE_DAYS:
        return "stale", age
    if int(summary.get("summary_window_sessions") or 0) < 200:
        return "insufficient_window", age
    return "fresh", age


def dedupe_pressures(items: list[dict]) -> list[dict]:
    out = []
    for item in sorted(items, key=lambda x: x["price"]):
        if out and abs(item["price"] / out[-1]["price"] - 1) <= 0.002:
            if item["source"] not in out[-1].setdefault("also_from", []):
                out[-1]["also_from"].append(item["source"])
            continue
        out.append(item)
    return out


def analyze(code: str, name: str, rows: list[dict], quote: dict, summary: dict) -> dict:
    current = f(quote.get("price")) or rows[-1]["close"]
    last_date = rows[-1]["date"]
    closes = [r["close"] for r in rows]
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60

    core = rows[-CORE_WINDOW:]
    dh, dl = pivots(core, 3)
    wh, _ = pivots(weekly_rows(rows), 2)

    candidates = []
    for pivot in dh:
        if pivot["price"] > current * 1.01:
            candidates.append({"source": "daily_pivot_120d", "price": pivot["price"], "date": pivot["date"]})
    for pivot in wh:
        if pivot["price"] > current * 1.01:
            candidates.append({"source": "weekly_pivot_180d", "price": pivot["price"], "date": pivot["date"]})
    for value in dense_resistance(rows, current):
        candidates.append({"source": "dense_supply_180d", "price": value})

    for pivot in summary.get("weekly_high_pivots", []) if isinstance(summary, dict) else []:
        value = f(pivot.get("price")) if isinstance(pivot, dict) else None
        if value is not None and value > current * 1.01:
            candidates.append({"source": "weekly_pivot_52w_summary", "price": value, "date": pivot.get("date")})
    high52 = f(summary.get("high_52w")) if isinstance(summary, dict) else None
    if high52 is not None and high52 > current * 1.01:
        candidates.append({"source": "52week_high_summary", "price": high52, "date": summary.get("high_52w_date")})

    candidates = dedupe_pressures(candidates)
    first = candidates[0] if candidates else None

    support_candidates = [x["price"] for x in dl if x["price"] < current]
    if ma20 < current:
        support_candidates.append(ma20)
    if ma60 < current:
        support_candidates.append(ma60)
    fallback_lows = [r["low"] for r in rows[-20:] if r["low"] < current]
    support = max(support_candidates) if support_candidates else (min(fallback_lows) if fallback_lows else None)

    recent_highs = dh[-3:]
    recent_lows = dl[-3:]
    hh = len(recent_highs) >= 2 and recent_highs[-1]["price"] > recent_highs[-2]["price"]
    hl = len(recent_lows) >= 2 and recent_lows[-1]["price"] > recent_lows[-2]["price"]
    above20 = current >= ma20
    above60 = current >= ma60
    if hh and hl and above20:
        state = "bullish_intact"
    elif above20 and (hh or hl or above60):
        state = "transition_positive"
    else:
        state = "weak_or_damaged"

    upside = ((first["price"] / current) - 1) * 100 if first else None
    downside = ((current / support) - 1) * 100 if support and support > 0 and support < current else None
    rr = upside / downside if upside is not None and downside and downside > 0 else None

    if first is None:
        conclusion = "observe_no_resistance_map"
    elif upside < 10:
        conclusion = "structure_valid_but_insufficient_space" if state != "weak_or_damaged" else "observe"
    elif state == "bullish_intact" and rr is not None and rr >= 2:
        conclusion = "strong"
    elif state != "weak_or_damaged" and rr is not None and rr >= 1.5:
        conclusion = "participate"
    else:
        conclusion = "observe"

    return {
        "code": code,
        "name": name,
        "data_status": "verified",
        "history_source": "local_history_shards",
        "data_date": last_date,
        "history_points": len(rows),
        "core_structure_window_sessions": CORE_WINDOW,
        "local_history_target_sessions": LOCAL_WINDOW,
        "current_price": round(current, 4),
        "ma20": round(ma20, 4),
        "ma60": round(ma60, 4),
        "structure_state": state,
        "latest_daily_high_pivots": recent_highs,
        "latest_daily_low_pivots": recent_lows,
        "pressure_map": candidates[:16],
        "first_effective_resistance": first,
        "support_invalidation": round(support, 4) if support else None,
        "upside_to_first_resistance_pct": round(upside, 2) if upside is not None else None,
        "downside_to_invalidation_pct": round(downside, 2) if downside is not None else None,
        "risk_reward": round(rr, 2) if rr is not None else None,
        "long_term_summary_status": "fresh",
        "long_term_summary_data_date": summary.get("summary_data_date"),
        "long_term_summary_high_52w": high52,
        "conclusion": conclusion,
    }


def unavailable(code: str, name: str, reason: str, rows: list[dict], summary_state: str, summary_age: int | None) -> dict:
    return {
        "code": code,
        "name": name,
        "data_status": "unverified",
        "history_source": "local_history_shards",
        "data_date": rows[-1]["date"] if rows else None,
        "history_points": len(rows),
        "core_structure_window_sessions": CORE_WINDOW,
        "local_history_target_sessions": LOCAL_WINDOW,
        "long_term_summary_status": summary_state,
        "long_term_summary_age_days": summary_age,
        "conclusion": "unavailable",
        "error": reason,
    }


def main() -> int:
    common = load_json(COMMON, {})
    latest = load_json(LATEST, {})
    stocks = latest.get("stocks", {})
    reference_date = str(latest.get("trade_date") or "")
    codes = common.get("common_pool_codes", [])
    results, errors = {}, {}

    for code in codes:
        gate = (common.get("future_earnings_gate") or {}).get(code, {})
        name = gate.get("name") or (stocks.get(code) or {}).get("name") or code
        item = local_item(code)
        rows = normalize_rows(item)
        summary = (item or {}).get("long_term_summary") or {}
        s_state, s_age = summary_status(summary, reference_date) if reference_date else ("reference_date_missing", None)

        reason = None
        if not item:
            reason = "local_history_missing"
        elif len(rows) < MIN_POINTS:
            reason = f"local_history_insufficient:{len(rows)}<{MIN_POINTS}"
        elif not reference_date:
            reason = "reference_trade_date_missing"
        elif rows[-1]["date"] != reference_date:
            reason = f"local_history_stale:{rows[-1]['date']}!={reference_date}"
        elif s_state != "fresh":
            reason = f"long_term_summary_{s_state}"

        if reason:
            errors[code] = reason
            results[code] = unavailable(code, name, reason, rows, s_state, s_age)
        else:
            results[code] = analyze(code, name, rows, stocks.get(code, {}) or {}, summary)

    valid_dates = [r.get("data_date") for r in results.values() if r.get("data_status") == "verified"]
    date_counts = {d: valid_dates.count(d) for d in sorted(set(valid_dates))}
    incomplete = sorted(code for code, row in results.items() if row.get("conclusion") == "unavailable")
    payload = {
        "schema_version": 2,
        "generated_at": dt.datetime.now(TZ).isoformat(),
        "reference_trade_date": reference_date,
        "common_pool_count": len(codes),
        "history_source": "local_bounded_history",
        "local_history_target_sessions": LOCAL_WINDOW,
        "core_structure_window_sessions": CORE_WINDOW,
        "long_term_summary_max_age_days": LONG_SUMMARY_MAX_AGE_DAYS,
        "same_date_counts": date_counts,
        "incomplete_count": len(incomplete),
        "incomplete_codes": incomplete,
        "errors": errors,
        "companies": results,
        "right_set_codes": sorted(
            [code for code, row in results.items() if row.get("conclusion") in {"strong", "participate"}]
        ),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "common": len(codes),
                "verified": len(codes) - len(incomplete),
                "incomplete": len(incomplete),
                "right": len(payload["right_set_codes"]),
                "dates": date_counts,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
