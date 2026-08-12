from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SHARDS = DATA / "shards"
SHARD_KEY_LENGTH = 5
SAMPLES = ("002475", "601138", "601899")


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    latest = read_json(DATA / "latest.json", {})
    trends = read_json(DATA / "trend_summary.json", {"stocks": {}})
    latest_stocks = latest.get("stocks", {})
    trend_stocks = trends.get("stocks", {})
    coverage = trends.get("coverage", {})
    SHARDS.mkdir(parents=True, exist_ok=True)

    for old in SHARDS.glob("*.json"):
        old.unlink()

    common = {
        "schema_version": 5,
        "generated_at": latest.get("generated_at"),
        "trade_date": latest.get("trade_date"),
        "market_status": latest.get("market_status"),
        "shard_key_length": SHARD_KEY_LENGTH,
    }

    groups: dict[str, dict] = defaultdict(dict)
    for code, q in latest_stocks.items():
        key = code[:SHARD_KEY_LENGTH]
        groups[key][code] = {
            "name": q.get("name"),
            "price": q.get("price"),
            "prev_close": q.get("prev_close"),
            "open": q.get("open"),
            "high": q.get("high"),
            "low": q.get("low"),
            "price_time": q.get("price_time"),
            "confidence": q.get("confidence"),
            "primary_source": q.get("primary_source"),
            "source_prices": q.get("source_prices"),
            "trend": trend_stocks.get(code),
        }

    for key, stocks in groups.items():
        payload = {**common, "shard": key, "stocks": stocks}
        (SHARDS / f"{key}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    health = {
        **common,
        "source_status": latest.get("source_status"),
        "validation_stats": latest.get("validation_stats"),
        "shard_count": len(groups),
        "history": {
            "storage": trends.get("history_storage"),
            "window_days": trends.get("history_window_days"),
            "structure_window_days": trends.get("structure_window_days"),
            "history_shard_key_length": trends.get("history_shard_key_length"),
            "coverage": coverage,
        },
        "sample_quotes": {
            code: {
                **(latest_stocks.get(code) or {}),
                "trend": trend_stocks.get(code),
            }
            for code in SAMPLES
        },
    }
    (DATA / "health.json").write_text(
        json.dumps(health, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"wrote {len(groups)} {SHARD_KEY_LENGTH}-digit quote shards; "
        f"history >=5d: {coverage.get('points_ge_5', 0)}, "
        f">=20d: {coverage.get('points_ge_20', 0)}, "
        f">=60d: {coverage.get('points_ge_60', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
