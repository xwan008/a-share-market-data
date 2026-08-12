from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from validate import parse_quote_time, validate_price, validate_quote_fields

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
LATEST_PATH = DATA_DIR / "latest.json"


def is_main_board(code: str) -> bool:
    code = str(code).zfill(6)
    sh = code.startswith(("600", "601", "603", "605"))
    sz = code.startswith(("000", "001", "002", "003"))
    return sh or sz


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


def fetch_sina_snapshot() -> dict[str, dict]:
    import easyquotation

    q = easyquotation.use("sina")
    raw = q.market_snapshot(prefix=True)
    out: dict[str, dict] = {}
    for symbol, item in raw.items():
        code = normalize_code(symbol)
        if not is_main_board(code):
            continue
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


def fetch_akshare_snapshot() -> dict[str, dict]:
    import akshare as ak

    df: pd.DataFrame = ak.stock_zh_a_spot_em()
    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        code = normalize_code(row.get("代码"))
        if not is_main_board(code):
            continue
        out[code] = {
            "name": row.get("名称"),
            "price": row.get("最新价"),
            "prev_close": row.get("昨收"),
            "open": row.get("今开"),
            "high": row.get("最高"),
            "low": row.get("最低"),
            "volume": row.get("成交量"),
            "change_pct": row.get("涨跌幅"),
        }
    return out


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


def infer_trade_date(sina: dict[str, dict], now: datetime) -> str:
    """Use modal Sina quote date so weekday holidays do not masquerade as trading days."""
    dates = []
    for item in sina.values():
        value = item.get("date")
        if value:
            dates.append(str(value).replace("/", "-").strip())
    if not dates:
        return now.date().isoformat()
    return Counter(dates).most_common(1)[0][0]


def main() -> int:
    now = datetime.now(TZ)
    sina, sina_error = safe_fetch(fetch_sina_snapshot, "sina")
    ak, ak_error = safe_fetch(fetch_akshare_snapshot, "akshare")

    if not sina and not ak:
        print(json.dumps({"error": "all_sources_failed", "details": [sina_error, ak_error]}, ensure_ascii=False))
        return 2

    trade_date = infer_trade_date(sina, now)
    status = clock_market_status(now)
    if trade_date != now.date().isoformat():
        status = "closed_or_no_trade"

    codes = sorted(set(sina) | set(ak))
    stocks: dict[str, dict] = {}
    stats = {"high": 0, "medium": 0, "invalid": 0}

    for code in codes:
        s = sina.get(code, {})
        a = ak.get(code, {})
        s_price = positive_number(s.get("price")) if s else None
        a_price = positive_number(a.get("price")) if a else None

        if s_price is not None:
            base = s
            source = "sina"
            primary = s_price
            secondary = a_price
        elif a_price is not None:
            base = a
            source = "akshare"
            primary = a_price
            secondary = None
        else:
            base = s or a
            source = "sina" if s else "akshare"
            primary = None
            secondary = None

        validation = validate_price(primary_price=primary, secondary_price=secondary)
        warnings = validation.warnings + validate_quote_fields({
            "price": base.get("price"),
            "prev_close": base.get("prev_close"),
            "change_pct": a.get("change_pct"),
        })

        quote_time = parse_quote_time(s.get("date"), s.get("time")) if s else None
        if s.get("date") and str(s.get("date")).replace("/", "-") != trade_date:
            warnings.append("sina_quote_date_outlier")

        quote = {
            "name": base.get("name") or a.get("name") or s.get("name"),
            "market": "SH" if code.startswith(("600", "601", "603", "605")) else "SZ",
            "price": base.get("price"),
            "prev_close": base.get("prev_close"),
            "open": base.get("open"),
            "high": base.get("high"),
            "low": base.get("low"),
            "volume": base.get("volume"),
            "change_pct": a.get("change_pct"),
            "price_time": quote_time,
            "primary_source": source,
            "source_prices": {
                "sina": s.get("price") if s else None,
                "akshare": a.get("price") if a else None,
            },
            "confidence": validation.confidence,
            "warnings": sorted(set(warnings)),
        }
        stocks[code] = quote
        stats[validation.confidence] = stats.get(validation.confidence, 0) + 1

    payload = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "trade_date": trade_date,
        "timezone": "Asia/Shanghai",
        "market_status": status,
        "source_status": {
            "sina": "ok" if sina else "failed",
            "akshare": "ok" if ak else "failed",
            "errors": [x for x in (sina_error, ak_error) if x],
        },
        "validation_stats": stats,
        "stocks": stocks,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    should_persist_history = (
        payload["market_status"] == "closed"
        and payload["trade_date"] == now.date().isoformat()
        and bool(stocks)
    )
    if should_persist_history:
        hist_path = HISTORY_DIR / f"{trade_date}.json"
        history_payload = {
            "trade_date": trade_date,
            "generated_at": now.isoformat(),
            "stocks": {
                code: {
                    "name": q.get("name"),
                    "close": q.get("price"),
                    "prev_close": q.get("prev_close"),
                    "high": q.get("high"),
                    "low": q.get("low"),
                    "open": q.get("open"),
                    "volume": q.get("volume"),
                    "confidence": q.get("confidence"),
                }
                for code, q in stocks.items()
                if q.get("confidence") != "invalid"
            },
        }
        hist_path.write_text(json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "generated_at": payload["generated_at"],
        "trade_date": payload["trade_date"],
        "market_status": payload["market_status"],
        "stocks": len(stocks),
        "stats": stats,
        "source_status": payload["source_status"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
