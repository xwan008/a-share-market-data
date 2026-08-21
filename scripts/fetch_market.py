from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validate import normalize_quote_date, parse_quote_time, validate_price, validate_quote_fields

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LATEST_PATH = DATA_DIR / "latest.json"

SH_MAIN_PREFIXES = ("600", "601", "603", "605")
SZ_MAIN_PREFIXES = ("000", "001", "002", "003")


def is_main_board(code: str) -> bool:
    code = str(code).zfill(6)
    return code.startswith((*SH_MAIN_PREFIXES, *SZ_MAIN_PREFIXES))


def is_main_board_symbol(raw: str) -> bool:
    raw = str(raw).lower().strip()
    if raw.startswith("sh"):
        return raw[2:].zfill(6).startswith(SH_MAIN_PREFIXES)
    if raw.startswith("sz"):
        return raw[2:].zfill(6).startswith(SZ_MAIN_PREFIXES)
    return is_main_board(raw)


def normalize_code(raw: str) -> str:
    raw = str(raw).lower().strip()
    if raw.startswith(("sh", "sz", "bj")):
        raw = raw[2:]
    return raw.zfill(6)


def positive_number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def calculate_change_pct(price, prev_close) -> float | None:
    current = positive_number(price)
    previous = positive_number(prev_close)
    if current is None or previous is None:
        return None
    return (current / previous - 1) * 100


def fetch_easyquotation_snapshot(provider: str) -> dict[str, dict]:
    import easyquotation

    q = easyquotation.use(provider)
    raw = q.market_snapshot(prefix=True)
    out: dict[str, dict] = {}
    for symbol, item in raw.items():
        if not is_main_board_symbol(symbol):
            continue
        code = normalize_code(symbol)
        out[code] = {
            "name": item.get("name"),
            "price": item.get("now"),
            "prev_close": item.get("close"),
            "open": item.get("open"),
            "high": item.get("high"),
            "low": item.get("low"),
            "volume": item.get("turnover"),
            "date": item.get("date"),
            "time": item.get("time"),
        }
    return out


def fetch_sina_snapshot() -> dict[str, dict]:
    return fetch_easyquotation_snapshot("sina")


def fetch_tencent_snapshot() -> dict[str, dict]:
    return fetch_easyquotation_snapshot("tencent")


def safe_fetch(fn, label: str) -> tuple[dict[str, dict], str | None]:
    try:
        return fn(), None
    except Exception as exc:
        return {}, f"{label}:{type(exc).__name__}:{exc}"


def clock_market_status(now: datetime) -> str:
    hm = now.hour * 60 + now.minute
    if now.weekday() >= 5:
        return "closed"
    if hm < 9 * 60 + 15:
        return "pre_open"
    if hm <= 11 * 60 + 30:
        return "morning_session"
    if hm < 13 * 60:
        return "morning_closed"
    if hm <= 15 * 60:
        return "afternoon_session"
    return "closed"


def infer_trade_date(sources: list[dict[str, dict]], now: datetime) -> str | None:
    dates: list[str] = []
    for source in sources:
        for item in source.values():
            quote_date = normalize_quote_date(item.get("date"))
            if quote_date:
                dates.append(quote_date)
    if not dates:
        return None
    return Counter(dates).most_common(1)[0][0]


def source_is_fresh(item: dict, trade_date: str | None) -> bool:
    if not item or positive_number(item.get("price")) is None:
        return False
    quote_date = normalize_quote_date(item.get("date"))
    return quote_date is not None and trade_date is not None and quote_date == trade_date


def main() -> int:
    now = datetime.now(TZ)
    sina, sina_error = safe_fetch(fetch_sina_snapshot, "sina")
    tencent, tencent_error = safe_fetch(fetch_tencent_snapshot, "tencent")
    if not sina and not tencent:
        print(
            json.dumps(
                {"error": "all_sources_failed", "details": [sina_error, tencent_error]},
                ensure_ascii=False,
            )
        )
        return 2

    trade_date = infer_trade_date([sina, tencent], now)
    status = clock_market_status(now)
    if trade_date is None:
        status = "date_unverified"
    elif trade_date != now.date().isoformat():
        status = "closed_or_no_trade"

    codes = sorted(set(sina) | set(tencent))
    stocks: dict[str, dict] = {}
    stats = {"high": 0, "medium": 0, "invalid": 0}

    for code in codes:
        s, t = sina.get(code, {}), tencent.get(code, {})
        fresh = [("sina", s), ("tencent", t)]
        fresh = [(name, item) for name, item in fresh if source_is_fresh(item, trade_date)]

        if fresh:
            source, base = fresh[0]
            primary = positive_number(base.get("price"))
            other_realtime = t if source == "sina" else s
            secondary = (
                positive_number(other_realtime.get("price"))
                if source_is_fresh(other_realtime, trade_date)
                else None
            )
        else:
            source, base, primary, secondary = "none", s or t, None, None

        change_pct = calculate_change_pct(base.get("price"), base.get("prev_close"))
        validation = validate_price(primary_price=primary, secondary_price=secondary)
        warnings = list(validation.warnings)
        for name, item in (("sina", s), ("tencent", t)):
            if item and positive_number(item.get("price")) is not None and not source_is_fresh(item, trade_date):
                warnings.append(f"{name}_date_unverified")
        warnings += validate_quote_fields(
            {
                "price": base.get("price"),
                "prev_close": base.get("prev_close"),
                "change_pct": change_pct,
            }
        )
        quote_time = (
            parse_quote_time(base.get("date"), base.get("time"))
            if source in {"sina", "tencent"}
            else None
        )

        quote = {
            "name": base.get("name") or s.get("name") or t.get("name"),
            "market": "SH" if code.startswith(SH_MAIN_PREFIXES) else "SZ",
            "price": base.get("price"),
            "prev_close": base.get("prev_close"),
            "open": base.get("open"),
            "high": base.get("high"),
            "low": base.get("low"),
            "volume": base.get("volume"),
            "change_pct": change_pct,
            "price_time": quote_time,
            "primary_source": source,
            "source_prices": {
                "sina": s.get("price") if s else None,
                "tencent": t.get("price") if t else None,
            },
            "source_dates": {
                "sina": normalize_quote_date(s.get("date")) if s else None,
                "tencent": normalize_quote_date(t.get("date")) if t else None,
            },
            "confidence": validation.confidence,
            "warnings": sorted(set(warnings)),
        }
        stocks[code] = quote
        stats[validation.confidence] += 1

    payload = {
        "schema_version": 3,
        "generated_at": now.isoformat(),
        "trade_date": trade_date,
        "timezone": "Asia/Shanghai",
        "market_status": status,
        "source_status": {
            "sina": "ok" if sina else "failed",
            "tencent": "ok" if tencent else "failed",
            "errors": [x for x in (sina_error, tencent_error) if x],
        },
        "validation_stats": stats,
        "stocks": stocks,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "trade_date": trade_date,
                "market_status": status,
                "stocks": len(stocks),
                "stats": stats,
                "source_status": payload["source_status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
