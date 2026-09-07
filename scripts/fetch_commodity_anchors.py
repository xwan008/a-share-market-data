from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "commodity" / "futures_daily.json"
LATEST = DATA / "latest.json"

SCHEMA_VERSION = 1
SOURCE = "akshare.futures_zh_daily_sina"
MAX_ANCHOR_AGE_DAYS = 7
NEUTRAL_WINDOW_SESSIONS = 504
MINIMUM_NEUTRAL_SESSIONS = 252
SERIES = {
    "CU0": {"name": "沪铜连续", "role": "revenue_price"},
    "AU0": {"name": "沪金连续", "role": "revenue_price"},
    "AL0": {"name": "沪铝连续", "role": "revenue_price"},
    "AO0": {"name": "氧化铝连续", "role": "input_cost"},
}


def fnum(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("empty percentile input")
    ordered = sorted(values)
    q = max(0.0, min(1.0, float(q)))
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def parse_day(value: object) -> date:
    return date.fromisoformat(str(value)[:10])


def normalize_rows(frame) -> list[dict]:
    if frame is None or frame.empty:
        return []
    columns = list(frame.columns)
    date_col = next((c for c in columns if str(c).lower() == "date"), None)
    close_col = next((c for c in columns if str(c).lower() == "close"), None)
    if date_col is None or close_col is None:
        raise RuntimeError(f"required futures columns missing: {columns}")

    rows: list[dict] = []
    for _, row in frame.iterrows():
        close = fnum(row.get(close_col))
        day = str(row.get(date_col) or "")[:10]
        if not day or close is None or close <= 0:
            continue
        rows.append({"date": day, "close": round(close, 6)})
    rows.sort(key=lambda item: item["date"])
    return rows


def summarize_rows(rows: list[dict], reference_trade_date: str) -> dict:
    if len(rows) < MINIMUM_NEUTRAL_SESSIONS:
        raise RuntimeError(f"insufficient_futures_history:{len(rows)}")

    last_date = rows[-1]["date"]
    age_days = (parse_day(reference_trade_date) - parse_day(last_date)).days
    if age_days < -1 or age_days > MAX_ANCHOR_AGE_DAYS:
        raise RuntimeError(
            f"stale_anchor:last_date={last_date}:reference={reference_trade_date}:age_days={age_days}"
        )

    closes = [float(row["close"]) for row in rows]
    current = closes[-1]
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    high60 = max(closes[-60:])
    neutral = closes[-min(NEUTRAL_WINDOW_SESSIONS, len(closes)) :]
    neutral_median = median(neutral)

    return {
        "last_date": last_date,
        "age_days": age_days,
        "history_points": len(rows),
        "neutral_window_sessions": len(neutral),
        "current": round(current, 6),
        "ma20": round(ma20, 6),
        "ma60": round(ma60, 6),
        "high60": round(high60, 6),
        "current_to_ma20": round(current / ma20, 6),
        "current_to_ma60": round(current / ma60, 6),
        "drawdown_from_60d_high_pct": round((current / high60 - 1.0) * 100.0, 4),
        "trend_20_vs_60_pct": round((ma20 / ma60 - 1.0) * 100.0, 4),
        "neutral_price_median": round(neutral_median, 6),
        "neutral_price_p40": round(percentile(neutral, 0.40), 6),
        "neutral_price_p60": round(percentile(neutral, 0.60), 6),
        "current_to_neutral": round(current / neutral_median, 6),
    }


def load_reference_trade_date() -> str:
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    trade_date = str(latest.get("trade_date") or "")[:10]
    if not trade_date:
        raise RuntimeError("latest trade_date missing")
    return trade_date


def main() -> int:
    import akshare as ak

    reference_trade_date = load_reference_trade_date()
    anchors: dict[str, dict] = {}
    errors: dict[str, str] = {}

    for symbol, meta in SERIES.items():
        try:
            frame = ak.futures_zh_daily_sina(symbol=symbol)
            all_rows = normalize_rows(frame)
            summary = summarize_rows(all_rows, reference_trade_date)
            anchors[symbol] = {
                "symbol": symbol,
                **meta,
                **summary,
                "history": all_rows[-NEUTRAL_WINDOW_SESSIONS:],
            }
        except Exception as exc:
            # Commodity-source outages must not suppress the entire A-share data refresh.
            # The research layer can fall back to conservative anchorless cycle valuation.
            errors[symbol] = f"{type(exc).__name__}:{exc}"

    status = "ok" if len(anchors) == len(SERIES) else ("degraded" if anchors else "unavailable")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_trade_date": reference_trade_date,
        "source": SOURCE,
        "status": status,
        "max_anchor_age_days": MAX_ANCHOR_AGE_DAYS,
        "neutral_window_sessions": NEUTRAL_WINDOW_SESSIONS,
        "minimum_neutral_sessions": MINIMUM_NEUTRAL_SESSIONS,
        "required_symbols": list(SERIES),
        "anchors": anchors,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "reference_trade_date": reference_trade_date,
                "anchors": sorted(anchors),
                "errors": errors,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
