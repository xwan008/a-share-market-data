from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = ROOT / "config" / "industry_scan_universe.json"
DEFAULT_COMPANY_REGISTRY = ROOT / "data" / "research" / "company_industry_registry.json"
DEFAULT_COMPANY_INDEX = ROOT / "data" / "research" / "company_industry_index.json"
ALLOWED_STATUS = {"T0", "T1", "T2", "unconfirmed", "not_applicable"}
CLASSIFICATION_STATUS = {"exposed", "not_exposed", "uncertain"}
MAIN_BOARD_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003")


class ValidationError(Exception):
    pass


def load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise ValidationError(f"missing_file:{p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid_json:{p}:{exc}") from exc


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_code(value: object) -> str:
    return str(value or "").zfill(6)


def is_main_board_code(code: str) -> bool:
    return len(code) == 6 and code.isdigit() and code.startswith(MAIN_BOARD_PREFIXES)


def validate_industry_scan(scan: dict, universe: dict) -> list[str]:
    errors: list[str] = []
    require(scan.get("weekly_pool_read") is False, "industry_scan_weekly_pool_must_be_false", errors)
    require(bool(parse_iso(scan.get("industry_frozen_at"))), "industry_frozen_at_missing_or_invalid", errors)

    expected = {item["id"]: item for item in universe.get("broad_industries", [])}
    actual_list = scan.get("broad_industries", [])
    actual = {item.get("id"): item for item in actual_list if item.get("id")}
    require(len(actual_list) == len(actual), "duplicate_broad_industry_ids", errors)

    missing_industries = sorted(set(expected) - set(actual))
    require(not missing_industries, f"missing_broad_industries:{missing_industries}", errors)
    for industry_id in sorted(set(actual) - set(expected)):
        require(
            actual[industry_id].get("registry_source") == "dynamic",
            f"extra_broad_industry_without_dynamic_marker:{industry_id}",
            errors,
        )

    for industry_id, spec in expected.items():
        item = actual.get(industry_id)
        if not item:
            continue
        subchains = item.get("subchains", [])
        by_name: dict[str, dict] = {}
        duplicate_names: list[str] = []
        for row in subchains:
            name = row.get("name")
            if not name:
                errors.append(f"subchain_missing_name:{industry_id}")
                continue
            if name in by_name:
                duplicate_names.append(name)
            by_name[name] = row
        require(not duplicate_names, f"duplicate_subchains:{industry_id}:{sorted(set(duplicate_names))}", errors)

        minimum = list(spec.get("minimum_subchains", []))
        missing_subchains = [name for name in minimum if name not in by_name]
        require(not missing_subchains, f"missing_minimum_subchains:{industry_id}:{missing_subchains}", errors)

        for name, row in by_name.items():
            status = row.get("status")
            require(status in ALLOWED_STATUS, f"invalid_status:{industry_id}:{name}:{status}", errors)
            if name in minimum:
                require(row.get("registry_source") in {None, "minimum"}, f"minimum_subchain_bad_source:{industry_id}:{name}", errors)
            else:
                require(row.get("registry_source") == "dynamic", f"dynamic_subchain_missing_marker:{industry_id}:{name}", errors)
            if status in {"T0", "T1", "T2"}:
                require(bool(row.get("direct_profit_driver")), f"missing_profit_driver:{industry_id}:{name}", errors)
                require(bool(row.get("leading_variables")), f"missing_leading_variables:{industry_id}:{name}", errors)
                require(bool(row.get("future_1_2q_transmission")), f"missing_forward_transmission:{industry_id}:{name}", errors)
                require(bool(row.get("invalidation_condition")), f"missing_invalidation:{industry_id}:{name}", errors)
            if status == "T2":
                require(bool(row.get("evidence_for")), f"t2_missing_evidence:{industry_id}:{name}", errors)
        require(isinstance(item.get("coverage_gap", []), list), f"coverage_gap_not_list:{industry_id}", errors)
    return errors


def t2_keys_from_scan(scan: dict) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for industry in scan.get("broad_industries", []):
        industry_id = industry.get("id")
        for row in industry.get("subchains", []):
            if row.get("status") == "T2":
                out.add((industry_id, row.get("name")))
    return out


def validate_company_registry(registry: dict) -> list[str]:
    errors: list[str] = []
    companies = registry.get("companies", {})
    require(isinstance(companies, dict), "company_registry_companies_must_be_object", errors)
    if not isinstance(companies, dict):
        return errors
    for raw_code, company in companies.items():
        code = normalize_code(raw_code)
        require(is_main_board_code(code), f"registry_invalid_main_board_code:{raw_code}", errors)
        require(bool(company.get("name")), f"registry_company_missing_name:{code}", errors)
        mappings = company.get("mappings", [])
        require(isinstance(mappings, list) and bool(mappings), f"registry_company_missing_mappings:{code}", errors)
        seen: set[tuple[str, str, str]] = set()
        for mapping in mappings if isinstance(mappings, list) else []:
            key = (
                mapping.get("broad_industry_id"),
                mapping.get("subchain"),
                mapping.get("value_chain_link"),
            )
            require(all(key), f"registry_mapping_missing_key_fields:{code}:{key}", errors)
            require(key not in seen, f"registry_duplicate_mapping:{code}:{key}", errors)
            seen.add(key)
            status = mapping.get("status")
            require(status in {"active", "inactive"}, f"registry_invalid_mapping_status:{code}:{key}:{status}", errors)
            require(bool(mapping.get("exposure_summary")), f"registry_mapping_missing_exposure:{code}:{key}", errors)
            require(bool(mapping.get("evidence_sources")), f"registry_mapping_missing_evidence:{code}:{key}", errors)
            if status == "inactive":
                require(bool(mapping.get("invalidation_reason")), f"registry_inactive_without_reason:{code}:{key}", errors)
    return errors


def validate_company_index(index: dict, universe: dict) -> list[str]:
    errors: list[str] = []
    companies = index.get("companies", {})
    require(isinstance(companies, dict), "company_index_companies_must_be_object", errors)
    if not isinstance(companies, dict):
        return errors
    broad_ids = {str(item.get("id")) for item in universe.get("broad_industries", []) if item.get("id")}
    for raw_code, item in companies.items():
        code = normalize_code(raw_code)
        require(is_main_board_code(code), f"company_index_invalid_main_board_code:{raw_code}", errors)
        require(bool(item.get("name")), f"company_index_missing_name:{code}", errors)
        broad_id = item.get("registry_broad_industry_id")
        if broad_id:
            require(str(broad_id) in broad_ids, f"company_index_unknown_broad_id:{code}:{broad_id}", errors)
    missing_codes = {normalize_code(c) for c in index.get("missing_codes", [])}
    unmapped_codes = {normalize_code(c) for c in index.get("unmapped_codes", [])}
    require(all(is_main_board_code(c) for c in missing_codes), "company_index_invalid_missing_code", errors)
    require(all(is_main_board_code(c) for c in unmapped_codes), "company_index_invalid_unmapped_code", errors)
    require(index.get("indexed_count") == len(companies), f"company_index_indexed_count_mismatch:{index.get('indexed_count')}!={len(companies)}", errors)
    expected_unmapped = {normalize_code(c) for c, item in companies.items() if not item.get("registry_broad_industry_id")}
    require(unmapped_codes == expected_unmapped, "company_index_unmapped_codes_mismatch", errors)
    total = index.get("main_board_universe_count")
    if isinstance(total, int):
        require(total == len(companies) + len(missing_codes), f"company_index_universe_count_mismatch:{total}!={len(companies)+len(missing_codes)}", errors)
    require(bool(parse_iso(index.get("generated_at"))), "company_index_generated_at_missing_or_invalid", errors)
    return errors


def active_registry_mappings_for_t2(registry: dict, scan: dict) -> set[tuple[str, str, str, str]]:
    t2 = t2_keys_from_scan(scan)
    out: set[tuple[str, str, str, str]] = set()
    for raw_code, company in registry.get("companies", {}).items():
        code = normalize_code(raw_code)
        for mapping in company.get("mappings", []):
            pair = (mapping.get("broad_industry_id"), mapping.get("subchain"))
            if mapping.get("status") == "active" and pair in t2:
                out.add((code, pair[0], pair[1], mapping.get("value_chain_link")))
    return out


def active_registry_codes_for_chain(registry: dict, broad_id: str, subchain: str) -> set[str]:
    out: set[str] = set()
    for raw_code, company in registry.get("companies", {}).items():
        for mapping in company.get("mappings", []):
            if (
                mapping.get("status") == "active"
                and mapping.get("broad_industry_id") == broad_id
                and mapping.get("subchain") == subchain
            ):
                out.add(normalize_code(raw_code))
    return out


def expected_candidate_codes(index: dict, registry: dict, broad_id: str, subchain: str) -> set[str]:
    mapped = {
        normalize_code(code)
        for code, item in index.get("companies", {}).items()
        if item.get("registry_broad_industry_id") == broad_id
    }
    unknown = {normalize_code(c) for c in index.get("missing_codes", [])}
    unknown |= {normalize_code(c) for c in index.get("unmapped_codes", [])}
    return mapped | unknown | active_registry_codes_for_chain(registry, broad_id, subchain)


def recalled_mappings(recall: dict) -> set[tuple[str, str, str, str]]:
    out: set[tuple[str, str, str, str]] = set()
    for row in recall.get("t2_subchains", []):
        industry_id = row.get("broad_industry_id")
        subchain = row.get("subchain")
        for link in row.get("value_chain_links", []):
            link_name = link.get("name")
            for company in link.get("companies", []):
                out.add((normalize_code(company.get("code")), industry_id, subchain, link_name))
    return out


def recalled_codes_for_row(row: dict) -> set[str]:
    out: set[str] = set()
    for link in row.get("value_chain_links", []):
        for company in link.get("companies", []):
            out.add(normalize_code(company.get("code")))
    return out


def validate_t2_recall(recall: dict, scan: dict, registry: dict | None = None, company_index: dict | None = None, universe: dict | None = None) -> list[str]:
    errors: list[str] = []
    registry = registry or {"companies": {}}
    require(recall.get("weekly_pool_read") is False, "t2_recall_weekly_pool_must_be_false", errors)
    scan_frozen = parse_iso(scan.get("industry_frozen_at"))
    recall_scan_frozen = parse_iso(recall.get("industry_scan_frozen_at"))
    recall_frozen = parse_iso(recall.get("t2_recall_frozen_at"))
    require(bool(recall_scan_frozen), "t2_recall_industry_scan_frozen_at_missing", errors)
    require(bool(recall_frozen), "t2_recall_frozen_at_missing", errors)
    if scan_frozen and recall_scan_frozen:
        require(recall_scan_frozen == scan_frozen, "t2_recall_points_to_wrong_industry_scan", errors)
    if recall_scan_frozen and recall_frozen:
        require(recall_frozen >= recall_scan_frozen, "t2_recall_frozen_before_industry_scan", errors)

    errors.extend(validate_company_registry(registry))
    if company_index is not None:
        errors.extend(validate_company_index(company_index, universe or {"broad_industries": []}))
        require(
            recall.get("company_index_generated_at") == company_index.get("generated_at"),
            "t2_recall_points_to_wrong_company_index",
            errors,
        )

    expected = t2_keys_from_scan(scan)
    rows = recall.get("t2_subchains", [])
    actual: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.get("broad_industry_id"), row.get("subchain"))
        if key in actual:
            errors.append(f"duplicate_t2_recall:{key}")
        actual[key] = row
    require(not (expected - set(actual)), f"missing_t2_recall_subchains:{sorted(expected-set(actual))}", errors)
    require(not (set(actual) - expected), f"recall_contains_non_t2_subchains:{sorted(set(actual)-expected)}", errors)

    for key, row in actual.items():
        broad_id, subchain = key
        chain_gap = row.get("coverage_gap", [])
        require(isinstance(chain_gap, list), f"t2_coverage_gap_not_list:{key}", errors)
        links = row.get("value_chain_links", [])
        require(bool(links), f"t2_has_no_value_chain_links:{key}", errors)

        unresolved = bool(chain_gap)
        seen_links: set[str] = set()
        for link in links:
            name = link.get("name")
            require(bool(name), f"value_chain_link_missing_name:{key}", errors)
            require(name not in seen_links, f"duplicate_value_chain_link:{key}:{name}", errors)
            seen_links.add(name)
            companies = link.get("companies", [])
            require(isinstance(companies, list), f"companies_not_list:{key}:{name}", errors)
            require(link.get("company_count") == len(companies), f"company_count_mismatch:{key}:{name}", errors)
            gap = link.get("coverage_gap", [])
            require(isinstance(gap, list), f"link_coverage_gap_not_list:{key}:{name}", errors)
            if gap:
                unresolved = True
            if not companies and not gap:
                errors.append(f"silent_empty_value_chain_link:{key}:{name}")
            codes: set[str] = set()
            for company in companies if isinstance(companies, list) else []:
                code = normalize_code(company.get("code"))
                require(is_main_board_code(code), f"invalid_company_code:{key}:{name}:{code}", errors)
                require(code not in codes, f"duplicate_company_in_link:{key}:{name}:{code}", errors)
                codes.add(code)
                require(bool(company.get("name")), f"company_missing_name:{key}:{name}:{code}", errors)
                require(bool(company.get("exposure_summary")), f"company_missing_exposure:{key}:{name}:{code}", errors)
                require(bool(company.get("evidence_sources")), f"company_missing_evidence_sources:{key}:{name}:{code}", errors)

        if company_index is not None:
            expected_codes = expected_candidate_codes(company_index, registry, broad_id, subchain)
            classifications = row.get("classifications", {})
            require(isinstance(classifications, dict), f"classifications_not_object:{key}", errors)
            classification_codes = {normalize_code(c) for c in classifications} if isinstance(classifications, dict) else set()
            require(row.get("candidate_universe_count") == len(expected_codes), f"candidate_universe_count_mismatch:{key}:{row.get('candidate_universe_count')}!={len(expected_codes)}", errors)
            require(classification_codes == expected_codes, f"candidate_classification_coverage_mismatch:{key}:missing={sorted(expected_codes-classification_codes)}:extra={sorted(classification_codes-expected_codes)}", errors)

            derived_counts = {status: 0 for status in sorted(CLASSIFICATION_STATUS)}
            exposed_codes: set[str] = set()
            uncertain_codes: set[str] = set()
            for raw_code, classification in classifications.items() if isinstance(classifications, dict) else []:
                code = normalize_code(raw_code)
                status = classification.get("status")
                require(status in CLASSIFICATION_STATUS, f"invalid_classification_status:{key}:{code}:{status}", errors)
                require(bool(classification.get("reason")), f"classification_missing_reason:{key}:{code}", errors)
                if status in CLASSIFICATION_STATUS:
                    derived_counts[status] += 1
                if status == "exposed":
                    exposed_codes.add(code)
                    require(bool(classification.get("evidence_sources")), f"exposed_classification_missing_evidence:{key}:{code}", errors)
                if status == "uncertain":
                    uncertain_codes.add(code)
                    unresolved = True

            counts = row.get("classification_counts", {})
            require(counts == derived_counts, f"classification_counts_mismatch:{key}:expected={derived_counts}:got={counts}", errors)
            require(sum(derived_counts.values()) == len(expected_codes), f"classification_total_mismatch:{key}", errors)
            recalled_codes = recalled_codes_for_row(row)
            require(not (exposed_codes - recalled_codes), f"exposed_codes_missing_from_value_chain:{key}:{sorted(exposed_codes-recalled_codes)}", errors)
            require(not (recalled_codes - exposed_codes), f"value_chain_codes_not_marked_exposed:{key}:{sorted(recalled_codes-exposed_codes)}", errors)
            queries = row.get("cross_industry_search_queries", [])
            require(isinstance(queries, list) and bool(queries), f"cross_industry_search_not_recorded:{key}", errors)
            discoveries = row.get("cross_industry_discoveries", [])
            require(isinstance(discoveries, list), f"cross_industry_discoveries_not_list:{key}", errors)

        expected_status = "incomplete" if unresolved else "complete"
        require(row.get("recall_status") == expected_status, f"recall_status_mismatch:{key}:expected_{expected_status}", errors)

    missing_registry_mappings = sorted(active_registry_mappings_for_t2(registry, scan) - recalled_mappings(recall))
    require(not missing_registry_mappings, f"active_registry_mappings_missing_from_recall:{missing_registry_mappings}", errors)
    return errors


def validate_stage_order(run: dict) -> list[str]:
    errors: list[str] = []
    industry = parse_iso(run.get("industry_frozen_at"))
    recall = parse_iso(run.get("t2_recall_frozen_at"))
    weekly = parse_iso(run.get("weekly_pool_read_at"))
    require(bool(industry), "stage_order_missing_industry_frozen_at", errors)
    require(bool(recall), "stage_order_missing_t2_recall_frozen_at", errors)
    require(bool(weekly), "stage_order_missing_weekly_pool_read_at", errors)
    if industry and recall:
        require(recall >= industry, "t2_recall_before_industry_freeze", errors)
    if recall and weekly:
        require(weekly >= recall, "weekly_pool_read_before_t2_recall_freeze", errors)
    return errors


def print_result(stage: str, errors: list[str]) -> int:
    payload = {"stage": stage, "status": "PASS" if not errors else "FAIL", "errors": errors}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate A-share research pipeline hard contracts")
    sub = parser.add_subparsers(dest="command", required=True)

    p_industry = sub.add_parser("industry-scan")
    p_industry.add_argument("scan")
    p_industry.add_argument("--universe", default=str(DEFAULT_UNIVERSE))

    p_recall = sub.add_parser("t2-recall")
    p_recall.add_argument("recall")
    p_recall.add_argument("--industry-scan", required=True)
    p_recall.add_argument("--company-registry", default=str(DEFAULT_COMPANY_REGISTRY))
    p_recall.add_argument("--company-index", default=str(DEFAULT_COMPANY_INDEX))
    p_recall.add_argument("--universe", default=str(DEFAULT_UNIVERSE))

    p_registry = sub.add_parser("company-registry")
    p_registry.add_argument("registry", nargs="?", default=str(DEFAULT_COMPANY_REGISTRY))

    p_index = sub.add_parser("company-index")
    p_index.add_argument("index", nargs="?", default=str(DEFAULT_COMPANY_INDEX))
    p_index.add_argument("--universe", default=str(DEFAULT_UNIVERSE))

    p_order = sub.add_parser("stage-order")
    p_order.add_argument("run_state")

    args = parser.parse_args()
    try:
        if args.command == "industry-scan":
            return print_result("industry-scan", validate_industry_scan(load_json(args.scan), load_json(args.universe)))
        if args.command == "t2-recall":
            return print_result(
                "t2-recall",
                validate_t2_recall(
                    load_json(args.recall),
                    load_json(args.industry_scan),
                    load_json(args.company_registry),
                    load_json(args.company_index),
                    load_json(args.universe),
                ),
            )
        if args.command == "company-registry":
            return print_result("company-registry", validate_company_registry(load_json(args.registry)))
        if args.command == "company-index":
            return print_result("company-index", validate_company_index(load_json(args.index), load_json(args.universe)))
        return print_result("stage-order", validate_stage_order(load_json(args.run_state)))
    except ValidationError as exc:
        return print_result(args.command, [str(exc)])


if __name__ == "__main__":
    sys.exit(main())
