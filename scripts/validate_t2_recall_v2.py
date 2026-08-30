from __future__ import annotations

import argparse
import copy
import sys

from company_index_fingerprint import company_index_fingerprint
from validate_research_pipeline import (
    CLASSIFICATION_STATUS,
    ValidationError,
    expected_candidate_codes,
    is_main_board_code,
    load_json,
    normalize_code,
    print_result,
    recalled_codes_for_row,
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
                "exposure_summary": d.get("exposure_summary") or "cross-industry discovery verified during company recall",
                "exposure_materiality": d.get("exposure_materiality") or "material",
                "status": "active",
                "first_verified_at": recall.get("t2_recall_frozen_at"),
                "last_verified_at": recall.get("t2_recall_frozen_at"),
                "evidence_sources": d.get("evidence_sources") or ["cross-industry business search"],
                "invalidation_reason": None,
            })
    return out


def status_map(scan: dict) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for industry in scan.get("broad_industries", []):
        broad = industry.get("id")
        for row in industry.get("subchains", []):
            if broad and row.get("name"):
                out[(broad, row.get("name"))] = row.get("status")
    return out


def validate_conditional_t1_rows(recall: dict, scan: dict, registry: dict, company_index: dict) -> list[str]:
    errors: list[str] = []
    statuses = status_map(scan)
    rows = recall.get("t2_subchains", [])
    all_rows = {
        (row.get("broad_industry_id"), row.get("subchain")): row
        for row in rows
    }
    actual_t1: dict[tuple[str, str], dict] = {}

    for row in rows:
        key = (row.get("broad_industry_id"), row.get("subchain"))
        if row.get("industry_status") != "T1":
            continue
        if key in actual_t1:
            errors.append(f"duplicate_conditional_t1_recall:{key}")
        actual_t1[key] = row
        if statuses.get(key) != "T1":
            errors.append(f"conditional_recall_not_current_t1:{key}:{statuses.get(key)}")
        if row.get("recall_mode") != "conditional_t1":
            errors.append(f"conditional_t1_bad_recall_mode:{key}:{row.get('recall_mode')}")

    expected_t1 = {key for key, status in statuses.items() if status == "T1"}

    raw_delegated = recall.get("t1_delegated_coverage", [])
    if not isinstance(raw_delegated, list):
        errors.append("t1_delegated_coverage_not_list")
        raw_delegated = []
    delegated: set[tuple[str, str]] = set()
    for item in raw_delegated:
        if not isinstance(item, dict):
            errors.append(f"invalid_t1_delegated_coverage:{item}")
            continue
        key = (item.get("broad_industry_id"), item.get("subchain"))
        target = (item.get("delegate_broad_industry_id"), item.get("delegate_subchain"))
        if key in delegated:
            errors.append(f"duplicate_t1_delegated_coverage:{key}")
        delegated.add(key)
        if statuses.get(key) != "T1":
            errors.append(f"t1_delegation_not_current_t1:{key}:{statuses.get(key)}")
        if item.get("coverage_mode") != "delegated_to_more_specific_chain":
            errors.append(f"t1_delegation_bad_mode:{key}:{item.get('coverage_mode')}")
        if statuses.get(target) not in {"T1", "T2"}:
            errors.append(f"t1_delegation_target_not_active:{key}->{target}:{statuses.get(target)}")
        if target not in all_rows:
            errors.append(f"t1_delegation_target_not_recalled:{key}->{target}")
        if not item.get("reason") or not item.get("residual_policy"):
            errors.append(f"t1_delegation_missing_rationale:{key}")

    raw_gaps = recall.get("t1_rule_coverage_gaps", [])
    if not isinstance(raw_gaps, list):
        errors.append("t1_rule_coverage_gaps_not_list")
        raw_gaps = []
    gaps: set[tuple[str, str]] = set()
    for item in raw_gaps:
        if not isinstance(item, list) or len(item) != 2:
            errors.append(f"invalid_t1_rule_coverage_gap:{item}")
            continue
        key = (item[0], item[1])
        if key in gaps:
            errors.append(f"duplicate_t1_rule_coverage_gap:{key}")
        gaps.add(key)
        if statuses.get(key) != "T1":
            errors.append(f"t1_rule_gap_not_current_t1:{key}:{statuses.get(key)}")

    if gaps:
        errors.append(f"t1_recall_rule_coverage_incomplete:{sorted(gaps)}")

    actual_keys = set(actual_t1)
    if actual_keys & delegated:
        errors.append(f"t1_chain_both_recalled_and_delegated:{sorted(actual_keys & delegated)}")
    if actual_keys & gaps:
        errors.append(f"t1_chain_both_recalled_and_gap:{sorted(actual_keys & gaps)}")
    if delegated & gaps:
        errors.append(f"t1_chain_both_delegated_and_gap:{sorted(delegated & gaps)}")
    covered = actual_keys | delegated | gaps
    if covered != expected_t1:
        errors.append(
            f"t1_recall_audit_not_closed:missing={sorted(expected_t1-covered)}:extra={sorted(covered-expected_t1)}"
        )

    for key, row in actual_t1.items():
        broad_id, subchain = key
        classifications = row.get("classifications", {})
        if not isinstance(classifications, dict):
            errors.append(f"t1_classifications_not_object:{key}")
            continue
        expected_codes = expected_candidate_codes(company_index, registry, broad_id, subchain)
        classification_codes = {normalize_code(c) for c in classifications}
        if row.get("candidate_universe_count") != len(expected_codes):
            errors.append(f"t1_candidate_universe_count_mismatch:{key}:{row.get('candidate_universe_count')}!={len(expected_codes)}")
        if classification_codes != expected_codes:
            errors.append(
                f"t1_candidate_classification_coverage_mismatch:{key}:missing={sorted(expected_codes-classification_codes)}:extra={sorted(classification_codes-expected_codes)}"
            )

        derived = {status: 0 for status in sorted(CLASSIFICATION_STATUS)}
        exposed_codes: set[str] = set()
        unresolved = bool(row.get("coverage_gap", []))
        for raw_code, classification in classifications.items():
            code = normalize_code(raw_code)
            status = classification.get("status")
            if not is_main_board_code(code):
                errors.append(f"t1_invalid_company_code:{key}:{code}")
            if status not in CLASSIFICATION_STATUS:
                errors.append(f"t1_invalid_classification_status:{key}:{code}:{status}")
                continue
            derived[status] += 1
            if not classification.get("reason"):
                errors.append(f"t1_classification_missing_reason:{key}:{code}")
            if classification.get("industry_status") != "T1" or classification.get("recall_mode") != "conditional_t1":
                errors.append(f"t1_classification_missing_mode_metadata:{key}:{code}")
            if status == "exposed":
                exposed_codes.add(code)
                if not classification.get("evidence_sources"):
                    errors.append(f"t1_exposed_missing_evidence:{key}:{code}")
            elif status == "uncertain":
                unresolved = True

        if row.get("classification_counts") != derived:
            errors.append(f"t1_classification_counts_mismatch:{key}:expected={derived}:got={row.get('classification_counts')}")
        recalled = recalled_codes_for_row(row)
        if recalled != exposed_codes:
            errors.append(f"t1_value_chain_exposure_mismatch:{key}:recalled={sorted(recalled)}:exposed={sorted(exposed_codes)}")
        queries = row.get("cross_industry_search_queries", [])
        if not isinstance(queries, list) or not queries:
            errors.append(f"t1_cross_industry_search_not_recorded:{key}")
        links = row.get("value_chain_links", [])
        if not isinstance(links, list) or not links:
            errors.append(f"t1_has_no_value_chain_links:{key}")
        else:
            for link in links:
                companies = link.get("companies", [])
                if link.get("company_count") != len(companies):
                    errors.append(f"t1_company_count_mismatch:{key}:{link.get('name')}")
                if not companies and not link.get("coverage_gap"):
                    errors.append(f"t1_silent_empty_value_chain_link:{key}:{link.get('name')}")
        expected_status = "incomplete" if unresolved else "complete"
        if row.get("recall_status") != expected_status:
            errors.append(f"t1_recall_status_mismatch:{key}:expected_{expected_status}")
    return errors


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
        scan = load_json(args.industry_scan)
        company_index = load_json(args.company_index)
        registry = registry_with_discoveries(load_json(args.company_registry), recall)

        errors: list[str] = []
        current_fingerprint = company_index_fingerprint(company_index)
        recall_fingerprint = recall.get("company_index_fingerprint")
        schema_version = int(recall.get("schema_version") or 1)

        if schema_version >= 2:
            if not recall_fingerprint:
                errors.append("t2_recall_company_index_fingerprint_missing")
            elif recall_fingerprint != current_fingerprint:
                errors.append("t2_recall_points_to_wrong_company_index_content")

        statuses = status_map(scan)
        invalid_rows = []
        for row in recall.get("t2_subchains", []):
            key = (row.get("broad_industry_id"), row.get("subchain"))
            status = statuses.get(key)
            if status not in {"T1", "T2"}:
                invalid_rows.append((key, status))
        if invalid_rows:
            errors.append(f"recall_contains_non_t1_t2_subchains:{invalid_rows}")

        t2_only = copy.deepcopy(recall)
        t2_only["t2_subchains"] = [
            row for row in recall.get("t2_subchains", [])
            if statuses.get((row.get("broad_industry_id"), row.get("subchain"))) == "T2"
        ]
        t2_only["company_index_generated_at"] = company_index.get("generated_at")
        errors.extend(validate_t2_recall(
            t2_only,
            scan,
            registry,
            company_index,
            load_json(args.universe),
        ))
        errors.extend(validate_conditional_t1_rows(recall, scan, registry, company_index))
        return print_result("t2-recall-v4", errors)
    except ValidationError as exc:
        return print_result("t2-recall-v4", [str(exc)])


if __name__ == "__main__":
    sys.exit(main())
