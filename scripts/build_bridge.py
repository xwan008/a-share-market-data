from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SHARDS = DATA / "shards"
PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003")
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
    SHARDS.mkdir(parents=True, exist_ok=True)

    common = {
        "schema_version": 1,
        "generated_at": latest.get("generated_at"),
        "trade_date": latest.get("trade_date"),
        "market_status": latest.get("market_status"),
    }

    for prefix in PREFIXES:
        stocks = {}
        for code, q in latest_stocks.items():
            if not code.startswith(prefix):
                continue
            stocks[code] = {
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
        payload = {**common, "prefix": prefix, "stocks": stocks}
        (SHARDS / f"{prefix}.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    health = {
        **common,
        "source_status": latest.get("source_status"),
        "validation_stats": latest.get("validation_stats"),
        "trend_days": trends.get("generated_from_days", 0),
        "sample_quotes": {code: latest_stocks.get(code) for code in SAMPLES},
    }
    (DATA / "health.json").write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(PREFIXES)} quote shards and health.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
