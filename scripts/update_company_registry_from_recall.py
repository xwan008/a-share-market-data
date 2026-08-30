from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RECALL = ROOT / "data" / "research" / "pipeline" / "t2_company_recall.json"
REGISTRY = ROOT / "data" / "research" / "company_industry_registry.json"
TZ = ZoneInfo("Asia/Shanghai")


def main() -> int:
    recall = json.loads(RECALL.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    companies = registry.setdefault("companies", {})
    now = datetime.now(TZ).isoformat()
    added = 0
    refreshed = 0
    for chain in recall.get("t2_subchains", []):
        broad = chain.get("broad_industry_id")
        subchain = chain.get("subchain")
        for link in chain.get("value_chain_links", []):
            link_name = link.get("name")
            for row in link.get("companies", []):
                code = str(row.get("code") or "").zfill(6)
                if not code:
                    continue
                company = companies.setdefault(code, {"name": row.get("name") or code, "mappings": []})
                if row.get("name"):
                    company["name"] = row["name"]
                mappings = company.setdefault("mappings", [])
                key = (broad, subchain, link_name)
                found = None
                for mapping in mappings:
                    if (mapping.get("broad_industry_id"), mapping.get("subchain"), mapping.get("value_chain_link")) == key:
                        found = mapping
                        break
                payload = {
                    "broad_industry_id": broad,
                    "subchain": subchain,
                    "value_chain_link": link_name,
                    "exposure_summary": row.get("exposure_summary") or f"verified exposure to {subchain}",
                    "exposure_materiality": row.get("exposure_materiality") or "material",
                    "status": "active",
                    "first_verified_at": (found or {}).get("first_verified_at") or recall.get("t2_recall_frozen_at") or now,
                    "last_verified_at": recall.get("t2_recall_frozen_at") or now,
                    "evidence_sources": row.get("evidence_sources") or ["validated T2 recall"],
                    "invalidation_reason": None,
                }
                if found is None:
                    mappings.append(payload)
                    added += 1
                else:
                    found.update(payload)
                    refreshed += 1
    registry["updated_at"] = now
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"ok","added":added,"refreshed":refreshed,"company_count":len(companies)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
