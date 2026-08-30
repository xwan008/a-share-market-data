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
PRIMARY_WORKERS = 6
RECOVERY_WORKERS = 2
# Fetch a little more than one trading year during the weekly repair, but persist
# only the bounded 180-session OHLCV window plus a tiny 52-week summary.
REQUEST_BARS = 270
LONG_TERM_WINDOW = 252
RETRIES = 4
RECOVERY_PAUSE_SECONDS = 5
MIN_COMMIT_SUCCESS_RATIO = 0.20
TENCENT_VOLUME_LOT_SIZE = 100


def symbol_for(code: str) -> str:
    return ("sh" if code.startswith(("600", "601", "603", "605")) else "sz") + code


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_long_term_summary(history: list[dict], refreshed_at: str) -> dict | None:
    rows = history[-LONG_TERM_WINDOW:]
    if not rows:
        return None
    highs = [(as_float(r.get("high")), str(r.get("date") or "")) for r in rows]
    lows = [(as_float(r.get("low")), str(r.get("date") or "")) for r in rows]
    highs = [(v, d) for v, d in highs if v is not None]
    lows = [(v, d) for v, d in lows if v is not None]
    if not highs or not lows:
        return None
    high_value, high_date = max(highs, key=lambda x: x[0])
    low_value, low_date = min(lows, key=lambda x: x[0])

    # Weekly pivot highs are enough to preserve older, potentially relevant
    # resistance outside the full 180-session local-history window.
    weeks: dict[tuple[int, int], dict] = {}
    for r in rows:
        try:
            dt = datetime.fromisoformat(str(r["date"]))
        except Exception:
            continue
        iso = dt.date().isocalendar()
        key = (iso.year, iso.week)
        high = as_float(r.get("high"))
        low = as_float(r.get("low"))
        close = as_float(r.get("close"))
        if high is None or low is None or close is None:
            continue
        if key not in weeks:
            weeks[key] = {"date": r["date"], "high": high, "low": low, "close": close}
        else:
            weeks[key]["date"] = r["date"]
            weeks[key]["high"] = max(weeks[key]["high"], high)
            weeks[key]["low"] = min(weeks[key]["low"], low)
            weeks[key]["close"] = close
    weekly = [weeks[k] for k in sorted(weeks)]
    pivots = []
    window = 2
    for i in range(window, len(weekly) - window):
        value = weekly[i]["high"]
        if all(value >= weekly[j]["high"] for j in range(i - window, i + window + 1)):
            pivots.append({"date": weekly[i]["date"], "price": round(value, 4)})

    return {
        "summary_window_sessions": min(LONG_TERM_WINDOW, len(rows)),
        "summary_refreshed_at": refreshed_at,
        "summary_data_date": rows[-1]["date"],
        "latest_seen_date": rows[-1]["date"],
        "high_52w": round(high_value, 4),
        "high_52w_date": high_date,
        "low_52w": round(low_value, 4),
        "low_52w_date": low_date,
        "weekly_high_pivots": pivots[-10:],
    }


def fetch_tencent_history(
    code: str,
    name: str | None,
    refreshed_at: str,
    *,
    exclude_date: str | None = None,
) -> tuple[str, dict | None, str | None]:
    """Fetch Tencent qfq history with conservative retrying."""
    symbol = symbol_for(code)
    params = {"param": f"{symbol},day,,,{REQUEST_BARS},qfq"}
    last_error: str | None = None

    for attempt in range(RETRIES + 1):
        try:
            response = requests.get(
                URL,
                params=params,
                timeout=12,
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
                volume_lots = as_float(row[5])
                volume_shares = volume_lots * TENCENT_VOLUME_LOT_SIZE if volume_lots is not None else None
                if close is None or close <= 0:
                    continue
                history.append(
                    {
                        "date": d,
                        "open": open_,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume_shares,
                        "volume_unit": "shares",
                        "confidence": "historical_tencent",
                        "basis": "qfq",
                        "source": "tencent",
                    }
                )
            history = sorted(history, key=lambda r: r["date"])
            if history:
                summary = build_long_term_summary(history, refreshed_at)
                return (
                    code,
                    {
                        "name": name,
                        "history_basis": "tencent_qfq",
                        "last_full_refresh": refreshed_at,
                        "long_term_summary": summary,
                        "history": history[-ROLLING_DAYS:],
                    },
                    None,
                )
            last_error = "no_history_rows"
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{exc}"

        if attempt < RETRIES:
            time.sleep(min(8.0, 0.75 * (2**attempt)))

    return code, None, last_error


def fetch_codes(
    codes: list[str],
    stocks: dict[str, dict],
    refreshed_at: str,
    workers: int,
) -> tuple[dict[str, dict], dict[str, str]]:
    results: dict[str, dict] = {}
    failures: dict[str, str] = {}
    if not codes:
        return results, failures

    with ThreadPoolExecutor(max_workers=workers) as pool:
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
    return results, failures


def main() -> int:
    latest = read_json(LATEST_PATH, {})
    stocks = latest.get("stocks", {})
    latest_generated_at = latest.get("generated_at")
    refreshed_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    if not stocks:
        print("latest.json has no stocks")
        return 2

    codes = sorted(stocks)
    results, failures = fetch_codes(codes, stocks, refreshed_at, PRIMARY_WORKERS)
    first_pass_success = len(results)

    if failures:
        time.sleep(RECOVERY_PAUSE_SECONDS)
        retry_codes = sorted(failures)
        retry_results, retry_failures = fetch_codes(
            retry_codes,
            stocks,
            refreshed_at,
            RECOVERY_WORKERS,
        )
        recovered = len(retry_results)
        results.update(retry_results)
        failures = retry_failures
    else:
        recovered = 0

    success_ratio = len(results) / len(codes) if codes else 0.0

    # replace=True replaces only successfully fetched symbols. Failed symbols
    # retain their previous bounded history and summary, so a degraded refresh
    # never destroys the last good local data.
    shard_count = write_history_shards(
        results,
        refreshed_at,
        replace=True,
        prune_to_codes=stocks.keys(),
    )

    status = {
        "schema_version": 5,
        "source": "tencent_qfq_day",
        "requested_stocks": len(codes),
        "successful_stocks": len(results),
        "failed_stocks": len(failures),
        "success_ratio": success_ratio,
        "first_pass_successful_stocks": first_pass_success,
        "second_pass_recovered_stocks": recovered,
        "degraded": bool(failures),
        "stale_histories_retained": len(failures),
        "rolling_days": ROLLING_DAYS,
        "request_bars": REQUEST_BARS,
        "long_term_summary_window": LONG_TERM_WINDOW,
        "primary_workers": PRIMARY_WORKERS,
        "recovery_workers": RECOVERY_WORKERS,
        "retries_per_pass": RETRIES,
        "volume_unit": "shares",
        "tencent_source_volume_unit": "lots_100_shares",
        "history_shards_written": shard_count,
        "latest_trade_date": latest.get("trade_date"),
        "latest_generated_at": latest_generated_at,
        "history_refreshed_at": refreshed_at,
        "sample_failures": dict(list(failures.items())[:30]),
    }
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0 if success_ratio >= MIN_COMMIT_SUCCESS_RATIO else 3


if __name__ == "__main__":
    raise SystemExit(main())
