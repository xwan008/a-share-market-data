from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
HISTORY_SHARDS_DIR = DATA_DIR / "history_shards"
OUTPUT = DATA_DIR / "trend_summary.json"


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    out = {
        "schema_version": 2,
        "history_storage": "rolling_shards",
        "history_window_days": 25,
        "history_shard_key_length": 4,
        "stocks": {},
    }
    shard_files = sorted(HISTORY_SHARDS_DIR.glob("*.json"))
    coverage_5d = 0
    coverage_20d = 0
    max_points = 0

    for path in shard_files:
        payload = read_json(path, {"stocks": {}})
        for code, item in payload.get("stocks", {}).items():
            rows = [r for r in item.get("history", []) if r.get("close") not in (None, 0)]
            rows = sorted(rows, key=lambda r: r.get("date", ""))[-20:]
            if not rows:
                continue

            closes = [float(r["close"]) for r in rows]
            last5 = rows[-5:]
            last5_closes = [float(r["close"]) for r in last5]
            points = len(rows)
            max_points = max(max_points, points)
            if points >= 5:
                coverage_5d += 1
            if points >= 20:
                coverage_20d += 1

            out["stocks"][code] = {
                "points": points,
                "last_date": rows[-1].get("date"),
                "last_close": closes[-1],
                "high_20d": max(float(r.get("high") or r["close"]) for r in rows),
                "low_20d": min(float(r.get("low") or r["close"]) for r in rows),
                "close_change_5d_pct": (
                    (last5_closes[-1] / last5_closes[0] - 1) * 100
                    if points >= 5 and len(last5_closes) == 5
                    else None
                ),
                "close_change_20d_pct": (
                    (closes[-1] / closes[0] - 1) * 100 if points >= 20 else None
                ),
                "last5": [
                    {"date": r.get("date"), "close": r.get("close")} for r in last5
                ],
            }

    total = len(out["stocks"])
    out["coverage"] = {
        "stocks": total,
        "points_ge_5": coverage_5d,
        "points_ge_20": coverage_20d,
        "max_points": max_points,
        "shard_files": len(shard_files),
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["coverage"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
