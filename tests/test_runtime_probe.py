import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def inspect_dict(obj):
    out = {}
    for k, v in obj.items():
        item = {"type": type(v).__name__}
        if isinstance(v, (dict, list, str)):
            item["len"] = len(v)
        if isinstance(v, dict) and v:
            fk = next(iter(v))
            fv = v[fk]
            item["sample_key"] = fk
            item["sample_value_type"] = type(fv).__name__
            if isinstance(fv, dict):
                item["sample_value_keys"] = list(fv.keys())[:30]
            elif isinstance(fv, list):
                item["sample_value"] = fv[:2]
            else:
                item["sample_value"] = fv
        elif isinstance(v, list) and v:
            item["sample_value"] = v[:2]
        else:
            item["value"] = v
        out[k] = item
    return out


def test_runtime_probe():
    idx = load("data/research/company_industry_index.json")
    latest = load("data/latest.json")
    ps = load("data/research/full_market_price_structure.json")
    summary = {
        "index_fields": inspect_dict(idx),
        "latest_fields": inspect_dict({k: v for k, v in latest.items() if k != "stocks"}),
        "latest_stock_count": len(latest.get("stocks") or {}),
        "latest_sample": next(iter((latest.get("stocks") or {}).items()), None),
        "price_structure_fields": inspect_dict({k: v for k, v in ps.items() if k not in {"stocks", "structures"}}),
        "price_structure_stock_container_keys": [k for k in ["stocks", "structures"] if k in ps],
    }
    raise AssertionError("RUNTIME_PROBE=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
