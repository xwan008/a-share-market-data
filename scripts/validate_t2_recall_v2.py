from __future__ import annotations

import argparse
import copy
import sys

from validate_research_pipeline import (
    ValidationError,
    load_json,
    normalize_code,
    print_result,
    validate_t2_recall,
)


def registry_with_discoveries(registry: dict, recall: dict) -> dict:
    out = copy.deepcopy(registry)
    companies = out.setdefault("companies", {})
    for row in recall.get("t2_subchains", []):
        broad = row.get("broad_industry_id")
        subchain = row.get("subchain")
        discoveries = row.get("cross_industry_discoveries", [])
        for d in discoveries if isinstance(discoveries, list) else []:
            code = normalize_code(d.get("code"))
            name = d.get("name") or code
            link = d.get("value_chain_link")
            if not code or not broad or not subchain or not link:
                continue
            company = companies.setdefault(code, {"name": name, "mappings": []})
            company.setdefault("name", name)
            mappings = company.setdefault("mappings", [])
            key = (broad, subchain, link)
            if any((m.get("broad_industry_id"), m.get("subchain"), m.get("value_chain_link")) == key for m in mappings):
                continue
            mappings.append({
                "broad_industry_id": broad,
                "subchain": subchain,
                "value_chain_link": link,
                "exposure_summary": d.get("exposure_summary") or "cross-industry discovery verified during T2 recall",
                "exposure_materiality": d.get("exposure_materiality") or "material",
                "status": "active",
                "first_verified_at": recall.get("t2_recall_frozen_at"),
                "last_verified_at": recall.get("t2_recall_frozen_at"),
                "evidence_sources": d.get("evidence_sources") or ["cross-industry business search"],
                "invalidation_reason": None,
            })
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recall")
    parser.add_argument("--industry-scan", required=True)
    parser.add_argument("--company-registry", default="data/research/company_industry_registry.json")
    parser.add_argument("--company-index", default="data/research/company_industry_index.json")
    parser.add_argument("--universe", default="config/industry_scan_universe.json")
    args = parser.parse_args()
    try:
        recall = load_json(args.recall)
        registry = registry_with_discoveries(load_json(args.company_registry), recall)
        errors = validate_t2_recall(
            recall,
            load_json(args.industry_scan),
            registry,
            load_json(args.company_index),
            load_json(args.universe),
        )
        return print_result("t2-recall-v2", errors)
    except ValidationError as exc:
        return print_result("t2-recall-v2", [str(exc)])


if __name__ == "__main__":
    sys.exit(main())
