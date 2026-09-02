import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["603268","601168","000783","601899","600546","000975","600489","601225"]

def test_runtime_probe():
    latest = json.loads((ROOT / "data/latest.json").read_text(encoding="utf-8"))
    stocks = latest.get("stocks") or {}
    out = {c: {k:(stocks.get(c) or {}).get(k) for k in ["name","price","prev_close","open","high","low","price_time","confidence"]} for c in TARGETS}
    raise AssertionError("INTRADAY_PROBE=" + json.dumps({"trade_date":latest.get("trade_date"),"market_status":latest.get("market_status"),"targets":out}, ensure_ascii=False, separators=(",",":")))
