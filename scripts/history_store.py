from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
HISTORY_SHARDS_DIR = DATA_DIR / "history_shards"
LATEST_PATH = DATA_DIR / "latest.json"

ROLLING_DAYS = 25
HISTORY_SHARD_KEY_LENGTH = 4
USABLE_CONFIDENCE = {"high", "medium"}


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def should_append_history(latest: dict) -> bool:
    """Only completed trading sessions belong in daily rolling history."""
    return latest.get("market_status") == "closed"


def compact_row(trade_date: str, quote: dict) -> dict:
    return {
        "date": trade_date,
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "close": quote.get("price"),
        "volume": quote.get("volume"),
        "confidence": quote.get("confidence"),
    }


def merge_rows(existing: list[dict], incoming: list[dict], limit: int = ROLLING_DAYS) -> list[dict]:
    by_date: dict[str, dict] = {}
    for row in [*existing, *incoming]:
        d = row.get("date")
        if not d or row.get("close") in (None, 0):
            continue
        by_date[str(d)] = row
    return [by_date[d] for d in sorted(by_date)[-limit:]]


def write_history_shards(series: dict[str, dict], generated_at: str | None = None) -> int:
    HISTORY_SHARDS_DIR.mkdir(parents=True, exist_ok=True)
    groups: dict[str, dict] = defaultdict(dict)

    for code, item in series.items():
        code = str(code).zfill(6)
        key = code[:HISTORY_SHARD_KEY_LENGTH]
        groups[key][code] = item

    for key, stocks in groups.items():
        path = HISTORY_SHARDS_DIR / f"{key}.json"
        current = read_json(path, {"stocks": {}})
        current_stocks = current.get("stocks", {})

        for code, item in stocks.items():
            old = current_stocks.get(code, {})
            rows = merge_rows(old.get("history", []), item.get("history", []))
            current_stocks[code] = {
                "name": item.get("name") or old.get("name"),
                "history": rows,
            }

        payload = {
            "schema_version": 1,
            "generated_at": generated_at,
            "rolling_days": ROLLING_DAYS,
            "history_shard_key_length": HISTORY_SHARD_KEY_LENGTH,
            "shard": key,
            "stocks": current_stocks,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    return len(groups)


def append_latest_snapshot() -> tuple[int, int]:
    latest = read_json(LATEST_PATH, {})

    if not should_append_history(latest):
        print(
            json.dumps(
                {
                    "market_status": latest.get("market_status"),
                    "trade_date": latest.get("trade_date"),
                    "updated_stocks": 0,
                    "reason": "history_only_accepts_closed_sessions",
                },
                ensure_ascii=False,
            )
        )
        return 0, 0

    trade_date = latest.get("trade_date")
    stocks = latest.get("stocks", {})
    if not trade_date or not stocks:
        print("latest.json has no usable trade_date/stocks; history not updated")
        return 0, 0

    try:
        date.fromisoformat(trade_date)
    except ValueError:
        print(f"invalid trade_date: {trade_date}")
        return 0, 0

    updates: dict[str, dict] = {}
    for code, quote in stocks.items():
        if quote.get("confidence") not in USABLE_CONFIDENCE:
            continue
        if quote.get("price") in (None, 0):
            continue
        updates[code] = {
            "name": quote.get("name"),
            "history": [compact_row(trade_date, quote)],
        }

    shard_count = write_history_shards(updates, latest.get("generated_at"))
    print(
        json.dumps(
            {
                "trade_date": trade_date,
                "market_status": latest.get("market_status"),
                "updated_stocks": len(updates),
                "history_shards": shard_count,
                "rolling_days": ROLLING_DAYS,
            },
            ensure_ascii=False,
        )
    )
    return len(updates), shard_count


def main() -> int:
    append_latest_snapshot()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
