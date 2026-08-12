from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = ROOT / "data" / "history"
OUTPUT = ROOT / "data" / "trend_summary.json"


def main() -> int:
    files = sorted(HISTORY_DIR.glob("*.json"))[-25:]
    series: dict[str, list[dict]] = defaultdict(list)

    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        date = payload["trade_date"]
        for code, quote in payload.get("stocks", {}).items():
            close = quote.get("close")
            if close in (None, 0):
                continue
            series[code].append({"date": date, **quote})

    out = {"generated_from_days": len(files), "stocks": {}}
    for code, rows in series.items():
        rows = rows[-20:]
        closes = [float(r["close"]) for r in rows if r.get("close")]
        if not closes:
            continue
        last5 = rows[-5:]
        last5_closes = [float(r["close"]) for r in last5 if r.get("close")]
        out["stocks"][code] = {
            "points": len(rows),
            "last_date": rows[-1]["date"],
            "last_close": closes[-1],
            "high_20d": max(float(r.get("high") or r["close"]) for r in rows),
            "low_20d": min(float(r.get("low") or r["close"]) for r in rows),
            "close_change_5d_pct": ((last5_closes[-1] / last5_closes[0] - 1) * 100) if len(last5_closes) >= 2 else None,
            "close_change_20d_pct": ((closes[-1] / closes[0] - 1) * 100) if len(closes) >= 2 else None,
            "last5": [{"date": r["date"], "close": r["close"]} for r in last5],
        }

    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT} for {len(out['stocks'])} stocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
