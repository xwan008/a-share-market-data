import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def shape(obj):
    if isinstance(obj, dict):
        keys = list(obj.keys())
        out = {"type": "dict", "len": len(obj), "keys": keys[:12]}
        if keys:
            k = keys[0]
            v = obj[k]
            out["first_key"] = k
            out["first_value_type"] = type(v).__name__
            if isinstance(v, dict):
                out["first_value_keys"] = list(v.keys())[:20]
            elif isinstance(v, list):
                out["first_value_len"] = len(v)
                out["first_value_sample"] = v[:1]
        return out
    if isinstance(obj, list):
        return {"type": "list", "len": len(obj), "sample": obj[:1]}
    return {"type": type(obj).__name__, "value": obj}


def test_runtime_probe():
    idx = load("data/research/company_industry_index.json")
    latest = load("data/latest.json")
    ps = load("data/research/full_market_price_structure.json")
    state = load("data/research/industry_state.json")
    admitted = []
    groups = {}
    for code, row in (state.get("level3_profitability") or {}).items():
        ok = row.get("trend") == "improving" or (row.get("trend") == "stable" and row.get("breadth") == "divergent")
        if ok:
            admitted.append({"code": code, "name": row.get("name"), "trend": row.get("trend"), "breadth": row.get("breadth"), "dirs": row.get("linked_prosperity_directions") or []})
        for d in row.get("linked_prosperity_directions") or ["<none>"]:
            groups[d] = groups.get(d, 0) + 1
    summary = {
        "index": shape(idx),
        "latest": shape(latest),
        "price_structure": shape(ps),
        "state_level3_count": len(state.get("level3_profitability") or {}),
        "state_direction_counts": groups,
        "admitted_count": len(admitted),
        "admitted": admitted,
    }
    raise AssertionError("RUNTIME_PROBE=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
