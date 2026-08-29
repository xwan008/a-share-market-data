from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = ROOT / "config" / "industry_scan_universe.json"
ALLOWED_STATUS = {"T0", "T1", "T2", "unconfirmed", "not_applicable"}


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


def validate_industry_scan(scan: dict, universe: dict) -> list[str]:
    errors: list[str] = []
    require(scan.get("weekly_pool_read") is False, "industry_scan_weekly_pool_must_be_false", errors)
    require(bool(parse_iso(scan.get("industry_frozen_at"))), "industry_frozen_at_missing_or_invalid", errors)

    expected = {item["id"]: item for item in universe.get("broad_industries", [])}
    actual_list = scan.get("broad_industries", [])
    actual = {item.get("id"): item for item in actual_list if item.get("id")}

    duplicates = len(actual_list) - len(actual)
    require(duplicates == 0, f"duplicate_broad_industry_ids:{duplicates}", errors)

    missing_industries = sorted(set(expected) - set(actual))
    extra_industries = sorted(set(actual) - set(expected))
    require(not missing_industries, f"missing_broad_industries:{missing_industries}", errors)
    # Extra broad industries are allowed only if explicitly dynamic.
    for industry_id in extra_industries:
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
        by_name = {}
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

        gaps = item.get("coverage_gap", [])
        require(isinstance(gaps, list), f"coverage_gap_not_list:{industry_id}", errors)

    return errors


def t2_keys_from_scan(scan: dict) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for industry in scan.get("broad_industries", []):
        industry_id = industry.get("id")
        for row in industry.get("subchains", []):
            if row.get("status") == "T2":
                out.add((industry_id, row.get("name")))
    return out


def validate_t2_recall(recall: dict, scan: dict) -> list[str]:
    errors: list[str] = []
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

    expected = t2_keys_from_scan(scan)
    rows = recall.get("t2_subchains", [])
    actual: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.get("broad_industry_id"), row.get("subchain"))
        if key in actual:
            errors.append(f"duplicate_t2_recall:{key}")
        actual[key] = row

    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)
    require(not missing, f"missing_t2_recall_subchains:{missing}", errors)
    require(not extra, f"recall_contains_non_t2_subchains:{extra}", errors)

    for key, row in actual.items():
        links = row.get("value_chain_links", [])
        require(bool(links), f"t2_has_no_value_chain_links:{key}", errors)
        chain_gap = row.get("coverage_gap", [])
        require(isinstance(chain_gap, list), f"t2_coverage_gap_not_list:{key}", errors)

        seen_links: set[str] = set()
        unresolved = False
        for link in links:
            name = link.get("name")
            require(bool(name), f"value_chain_link_missing_name:{key}", errors)
            if name in seen_links:
                errors.append(f"duplicate_value_chain_link:{key}:{name}")
            seen_links.add(name)
            companies = link.get("companies", [])
            count = link.get("company_count")
            require(isinstance(companies, list), f"companies_not_list:{key}:{name}", errors)
            require(count == len(companies), f"company_count_mismatch:{key}:{name}:{count}!={len(companies) if isinstance(companies, list) else 'NA'}", errors)
            gap = link.get("coverage_gap", [])
            require(isinstance(gap, list), f"link_coverage_gap_not_list:{key}:{name}", errors)
            if not companies and not gap:
                errors.append(f"silent_empty_value_chain_link:{key}:{name}")
            if gap:
                unresolved = True

            codes: set[str] = set()
            for company in companies if isinstance(companies, list) else []:
                code = str(company.get("code", "")).zfill(6)
                require(len(code) == 6 and code.isdigit(), f"invalid_company_code:{key}:{name}:{code}", errors)
                require(code not in codes, f"duplicate_company_in_link:{key}:{name}:{code}", errors)
                codes.add(code)
                require(bool(company.get("name")), f"company_missing_name:{key}:{name}:{code}", errors)
                require(bool(company.get("exposure_summary")), f"company_missing_exposure:{key}:{name}:{code}", errors)
                require(bool(company.get("evidence_sources")), f"company_missing_evidence_sources:{key}:{name}:{code}", errors)

        expected_status = "incomplete" if unresolved or chain_gap else "complete"
        require(row.get("recall_status") == expected_status, f"recall_status_mismatch:{key}:expected_{expected_status}", errors)

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

    p_order = sub.add_parser("stage-order")
    p_order.add_argument("run_state")

    args = parser.parse_args()
    try:
        if args.command == "industry-scan":
            errors = validate_industry_scan(load_json(args.scan), load_json(args.universe))
            return print_result("industry-scan", errors)
        if args.command == "t2-recall":
            errors = validate_t2_recall(load_json(args.recall), load_json(args.industry_scan))
            return print_result("t2-recall", errors)
        errors = validate_stage_order(load_json(args.run_state))
        return print_result("stage-order", errors)
    except ValidationError as exc:
        return print_result(args.command, [str(exc)])


if __name__ == "__main__":
    sys.exit(main())
