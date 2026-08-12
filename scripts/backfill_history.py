from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

try:
    from .history_store import ROLLING_DAYS, read_json, write_history_shards
except ImportError:  # direct script execution
    from history_store import ROLLING_DAYS, read_json, write_history_shards

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LATEST_PATH = DATA_DIR / "latest.json"
STATUS_PATH = DATA_DIR / "backfill_status.json"

URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
MAX_WORKERS = 12
REQUEST_BARS = 80
RETRIES = 2


def symbol_for(code: str) -> str:
    return ("sh" if code.startswith(("600", "601", "603", "605")) else "sz") + code


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_tencent_history(
    code: str,
    name: str | None,
    refreshed_at: str,
    *,
    exclude_date: str | None = None,
) -> tuple[str, dict | None, str | None]:
    """Fetch a bounded Tencent qfq daily series.

    exclude_date is used by intraday corporate-action repair so the current
    unfinished session can never enter completed daily history.
    """
    symbol = symbol_for(code)
    params = {"param": f"{symbol},day,,,{REQUEST_BARS},qfq"}
    last_error: str | None = None

    for attempt in range(RETRIES + 1):
        try:
            response = requests.get(
                URL,
                params=params,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 a-share-market-data/1.0"},
            )
            response.raise_for_status()
            payload = response.json()
            node = payload.get("data", {}).get(symbol, {})
            rows = node.get("qfqday") or node.get("day") or []
            history: list[dict] = []
            for row in rows:
                if not isinstance(row, list) or len(row) < 6:
                    continue
                d = str(row[0])
                if exclude_date and d == exclude_date:
                    continue
                open_ = as_float(row[1])
                close = as_float(row[2])
                high = as_float(row[3])
                low = as_float(row[4])
                volume = as_float(row[5])
                if close is None or close <= 0:
                    continue
                history.append(
                    {
                        "date": d,
                        "open": open_,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume,
                        "confidence": "historical_tencent",
                        "basis": "qfq",
                        "source": "tencent",
                    }
                )
            history = sorted(history, key=lambda r: r["date"])[-ROLLING_DAYS:]
            if history:
                return (
                    code,
                    {
                        "name": name,
                        "history_basis": "tencent_qfq",
                        "last_full_refresh": refreshed_at,
                        "history": history,
                    },
                    None,
                )
            last_error = "no_history_rows"
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{exc}"
        if attempt < RETRIES:
            time.sleep(0.35 * (attempt + 1))

    return code, None, last_error


def main() -> int:
    latest = read_json(LATEST_PATH, {})
    stocks = latest.get("stocks", {})
    latest_generated_at = latest.get("generated_at")
    refreshed_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    if not stocks:
        print("latest.json has no stocks")
        return 2

    results: dict[str, dict] = {}
    failures: dict[str, str] = {}
    codes = sorted(stocks)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(
                fetch_tencent_history,
                code,
                stocks[code].get("name"),
                refreshed_at,
            ): code
            for code in codes
        }
        for future in as_completed(futures):
            code, item, error = future.result()
            if item is not None:
                results[code] = item
            else:
                failures[code] = error or "unknown"

    shard_count = write_history_shards(
        results,
        refreshed_at,
        replace=True,
        prune_to_codes=stocks.keys(),
    )
    success_ratio = len(results) / len(codes) if codes else 0.0
    status = {
        "schema_version": 2,
        "source": "tencent_qfq_day",
        "requested_stocks": len(codes),
        "successful_stocks": len(results),
        "failed_stocks": len(failures),
        "success_ratio": success_ratio,
        "rolling_days": ROLLING_DAYS,
        "request_bars": REQUEST_BARS,
        "history_shards_written": shard_count,
        "latest_trade_date": latest.get("trade_date"),
        "latest_generated_at": latest_generated_at,
        "history_refreshed_at": refreshed_at,
        "sample_failures": dict(list(failures.items())[:30]),
    }
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))

    return 0 if success_ratio >= 0.70 else 3


if __name__ == "__main__":
    raise SystemExit(main())
