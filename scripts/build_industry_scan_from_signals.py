from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "industry_scan_universe.json"
SIGNALS = ROOT / "config" / "current_industry_scan_signals.json"
OUTPUT = ROOT / "data" / "research" / "pipeline" / "industry_scan.json"


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    signals = json.loads(SIGNALS.read_text(encoding="utf-8"))
    overrides = {(x["broad_industry_id"], x["subchain"]): x for x in signals.get("signals", [])}
    broad_out = []
    seen = set()
    for spec in registry.get("broad_industries", []):
        bid = spec["id"]
        rows = []
        for name in spec.get("minimum_subchains", []):
            key = (bid, name)
            base = {"name": name, "registry_source": "minimum", "status": "unconfirmed", "stage": None, "evidence_for": [], "evidence_against": []}
            if key in overrides:
                value = dict(overrides[key]); value.pop("broad_industry_id", None); value.setdefault("registry_source", "minimum"); base.update(value); seen.add(key)
            rows.append(base)
        for key, value in overrides.items():
            if key[0] != bid or key in seen:
                continue
            row = dict(value); row.pop("broad_industry_id", None); row.setdefault("registry_source", "dynamic")
            rows.append(row); seen.add(key)
        broad_out.append({"id": bid, "name": spec["name"], "subchains": rows, "coverage_gap": []})
    missing_signal_industries = sorted({k[0] for k in overrides if k not in seen})
    if missing_signal_industries:
        raise SystemExit(f"signal industries missing from registry: {missing_signal_industries}")
    payload = {
        "schema_version": 1,
        "scan_as_of": signals["scan_as_of"],
        "weekly_pool_read": signals.get("weekly_pool_read", False),
        "industry_frozen_at": signals["industry_frozen_at"],
        "broad_industries": broad_out,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"ok","broad_industries":len(broad_out),"subchains":sum(len(x["subchains"]) for x in broad_out),"signals":len(overrides)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
