from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data" / "research" / "company_industry_index.json"
LATEST = ROOT / "data" / "latest.json"
OUT = ROOT / "data" / "research" / "company_buckets"


def main() -> int:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    quotes = latest.get("stocks", {})
    companies = data.get("companies", {})
    buckets: dict[str, list[dict]] = {}
    for code, item in companies.items():
        broad = item.get("registry_broad_industry_id") or "__unmapped__"
        buckets.setdefault(broad, []).append({
            "code": str(code).zfill(6),
            "name": item.get("name"),
            "sw_level1_name": item.get("sw_level1_name"),
            "industry_code": item.get("industry_code"),
            "hierarchy": item.get("hierarchy", {}),
            "mapping_status": item.get("mapping_status"),
        })
    missing_rows = []
    for code in data.get("missing_codes", []):
        q = quotes.get(code, {})
        missing_rows.append({
            "code": code,
            "name": q.get("name"),
            "price": q.get("price"),
            "confidence": q.get("confidence"),
            "mapping_status": "missing",
        })
    buckets["__missing__"] = missing_rows
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 2,
        "source_generated_at": data.get("generated_at"),
        "main_board_universe_count": data.get("main_board_universe_count"),
        "indexed_count": data.get("indexed_count"),
        "missing_codes": data.get("missing_codes", []),
        "unmapped_codes": data.get("unmapped_codes", []),
        "buckets": {},
    }
    live = set()
    for broad, rows in sorted(buckets.items()):
        rows.sort(key=lambda x: x["code"])
        path = OUT / f"{broad}.json"
        payload = {
            "schema_version": 1,
            "broad_industry_id": broad,
            "source_generated_at": data.get("generated_at"),
            "company_count": len(rows),
            "companies": rows,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        live.add(path.name)
        manifest["buckets"][broad] = {"company_count": len(rows), "path": str(path.relative_to(ROOT))}
    for path in OUT.glob("*.json"):
        if path.name != "manifest.json" and path.name not in live:
            path.unlink()
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"ok","bucket_count":len(buckets),"indexed_count":data.get("indexed_count"),"missing_count":len(missing_rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
