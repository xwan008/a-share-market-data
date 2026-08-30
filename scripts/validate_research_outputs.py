from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

MAIN_BOARD_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003")
WEEKLY_STATUS = {"pass", "reject", "uncertain"}
FINAL_STATUS = {"core", "watch", "reject"}
RESOURCE_CYCLE_TAGS = {"nonferrous::铜矿资源", "nonferrous::电解铝"}


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


def normalize_code(value: object) -> str:
    return str(value or "").zfill(6)


def is_main_board(code: str) -> bool:
    return len(code) == 6 and code.isdigit() and code.startswith(MAIN_BOARD_PREFIXES)


def parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_day(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _valid_range(value: object) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(isinstance(x, (int, float)) for x in value) and value[0] <= value[1]


def validate_weekly_scan(scan: dict) -> list[str]:
    errors: list[str] = []
    require(scan.get("industry_state_modified") is False, "weekly_scan_must_not_modify_industry_state", errors)
    recall_time = parse_iso(scan.get("t2_recall_frozen_at"))
    weekly_time = parse_iso(scan.get("weekly_pool_read_at"))
    require(bool(recall_time), "weekly_scan_missing_t2_recall_frozen_at", errors)
    require(bool(weekly_time), "weekly_scan_missing_weekly_pool_read_at", errors)
    if recall_time and weekly_time:
        require(weekly_time >= recall_time, "weekly_scan_read_before_t2_recall_freeze", errors)

    results = scan.get("screen_results", {})
    require(isinstance(results, dict), "weekly_screen_results_must_be_object", errors)
    if not isinstance(results, dict):
        results = {}
    normalized = {normalize_code(code): item for code, item in results.items()}
    require(len(normalized) == len(results), "weekly_screen_duplicate_normalized_codes", errors)
    require(all(is_main_board(code) for code in normalized), "weekly_screen_contains_non_main_board_code", errors)

    universe_count = scan.get("universe_count")
    screened_count = scan.get("screened_count")
    require(isinstance(universe_count, int) and universe_count >= 0, "weekly_invalid_universe_count", errors)
    require(screened_count == len(normalized), f"weekly_screened_count_mismatch:{screened_count}!={len(normalized)}", errors)
    require(universe_count == screened_count, f"weekly_universe_not_fully_screened:{universe_count}!={screened_count}", errors)

    pass_or_uncertain: set[str] = set()
    for code, item in normalized.items():
        status = item.get("status") if isinstance(item, dict) else None
        require(status in WEEKLY_STATUS, f"weekly_invalid_status:{code}:{status}", errors)
        require(bool(item.get("reason")) if isinstance(item, dict) else False, f"weekly_missing_reason:{code}", errors)
        if status in {"pass", "uncertain"}:
            pass_or_uncertain.add(code)

    deep = {normalize_code(code) for code in scan.get("deep_verified_codes", [])}
    active = {normalize_code(code) for code in scan.get("pool_active_codes", [])}
    require(deep <= pass_or_uncertain, f"weekly_deep_codes_not_from_recall:{sorted(deep-pass_or_uncertain)}", errors)
    require(active <= deep, f"weekly_active_codes_not_deep_verified:{sorted(active-deep)}", errors)
    require(all(is_main_board(code) for code in deep | active), "weekly_invalid_deep_or_active_code", errors)
    return errors


def _validate_valuation_rows(rows: object, errors: list[str], prefix: str) -> set[str]:
    require(isinstance(rows, list), f"{prefix}_companies_must_be_list", errors)
    if not isinstance(rows, list):
        return set()
    seen: set[str] = set()
    for row in rows:
        code = normalize_code(row.get("code"))
        require(is_main_board(code), f"{prefix}_invalid_code:{code}", errors)
        require(code not in seen, f"{prefix}_duplicate_code:{code}", errors)
        seen.add(code)
        status = row.get("valuation_status")
        require(status in {"valid", "unavailable"}, f"{prefix}_invalid_status:{code}:{status}", errors)
        require(bool(row.get("valuation_model")), f"{prefix}_missing_model:{code}", errors)
        require(bool(row.get("forward_earnings_basis")), f"{prefix}_missing_forward_basis:{code}", errors)
        require(bool(row.get("invalidation_condition")), f"{prefix}_missing_invalidation:{code}", errors)
        if status == "valid":
            require(_valid_range(row.get("reasonable_multiple_range")), f"{prefix}_bad_multiple_range:{code}", errors)
            require(_valid_range(row.get("value_anchor_range")), f"{prefix}_bad_anchor_range:{code}", errors)
            require(_valid_range(row.get("reasonable_buy_range")), f"{prefix}_bad_reasonable_buy_range:{code}", errors)
            require(_valid_range(row.get("safe_buy_range")), f"{prefix}_bad_safe_buy_range:{code}", errors)
            require(bool(row.get("key_sensitivities")), f"{prefix}_missing_sensitivities:{code}", errors)
    return seen


def validate_fundamental_valuation(output: dict) -> list[str]:
    errors: list[str] = []
    seen = _validate_valuation_rows(output.get("companies", []), errors, "valuation")
    deferred = {normalize_code(x) for x in output.get("deferred_cycle_codes", [])}
    common_count = output.get("common_pool_count")
    require(isinstance(common_count, int), "valuation_missing_common_pool_count", errors)
    if isinstance(common_count, int):
        require(len(seen | deferred) == common_count, f"valuation_fundamental_plus_cycle_count_mismatch:{len(seen | deferred)}!={common_count}", errors)
        require(not (seen & deferred), f"valuation_cycle_codes_leaked_into_fundamental:{sorted(seen & deferred)}", errors)
    for row in output.get("companies", []) if isinstance(output.get("companies"), list) else []:
        if row.get("valuation_status") == "valid":
            source = str(row.get("forecast_source") or "")
            basis = str(row.get("forward_earnings_basis") or "")
            require("profit_forecast" in source or "consensus" in source.lower(), f"valuation_formal_without_consensus_source:{row.get('code')}:{source}", errors)
            require("H1 EPS×2" not in basis and "H1 EPS*2" not in basis, f"valuation_formal_uses_h1_times_two:{row.get('code')}", errors)
            require(bool(row.get("multiple_rationale")), f"valuation_missing_multiple_rationale:{row.get('code')}", errors)
    return errors


def validate_cycle_valuation(output: dict) -> list[str]:
    errors: list[str] = []
    seen = _validate_valuation_rows(output.get("companies", []), errors, "cycle")
    declared = {normalize_code(x) for x in output.get("cycle_codes", [])}
    require(seen == declared, f"cycle_declared_codes_mismatch:seen={sorted(seen)}:declared={sorted(declared)}", errors)
    anchor_errors = output.get("anchor_errors", {}) if isinstance(output.get("anchor_errors"), dict) else {}
    reference_day = parse_day(output.get("reference_trade_date"))
    max_age = output.get("max_anchor_age_days")
    require(reference_day is not None, "cycle_missing_reference_trade_date", errors)
    require(isinstance(max_age, int) and 0 <= max_age <= 14, f"cycle_invalid_max_anchor_age_days:{max_age}", errors)
    for row in output.get("companies", []) if isinstance(output.get("companies"), list) else []:
        code = normalize_code(row.get("code"))
        tag = row.get("cycle_tag")
        if row.get("valuation_status") == "valid":
            anchors = row.get("commodity_anchors")
            require(bool(anchors), f"cycle_valid_without_anchors:{code}", errors)
            if isinstance(anchors, list) and reference_day is not None and isinstance(max_age, int):
                for anchor in anchors:
                    anchor_day = parse_day(anchor.get("last_date")) if isinstance(anchor, dict) else None
                    require(anchor_day is not None, f"cycle_anchor_missing_date:{code}:{anchor}", errors)
                    if anchor_day is not None:
                        age = (reference_day - anchor_day).days
                        require(-1 <= age <= max_age, f"cycle_stale_anchor:{code}:{anchor.get('symbol')}:{anchor_day}:age={age}", errors)
            factors = row.get("bear_base_bull_anchor_factor")
            earnings = row.get("bear_base_bull_forward_eps")
            require(isinstance(factors, list) and len(factors) == 3, f"cycle_missing_scenarios:{code}", errors)
            require(isinstance(earnings, list) and len(earnings) == 3, f"cycle_missing_forward_earnings_scenarios:{code}", errors)
            require(bool(row.get("profit_sensitivity")), f"cycle_missing_profit_sensitivity:{code}", errors)
        elif tag in RESOURCE_CYCLE_TAGS:
            reason = str(row.get("reason") or "")
            allowed = "commodity_anchor_fetch_failed" in reason or "forward_consensus_insufficient" in reason or "current_price_missing" in reason
            require(allowed, f"resource_cycle_silently_unavailable:{code}:{reason}", errors)
            if "commodity_anchor_fetch_failed" in reason:
                require(bool(anchor_errors), f"resource_cycle_claims_anchor_failure_without_error_map:{code}", errors)
    return errors


def validate_left_valuation(output: dict) -> list[str]:
    errors: list[str] = []
    seen = _validate_valuation_rows(output.get("companies", []), errors, "left")
    common_count = output.get("common_pool_count")
    require(isinstance(common_count, int), "left_missing_common_pool_count", errors)
    if isinstance(common_count, int):
        require(len(seen) == common_count, f"left_common_pool_coverage_mismatch:{len(seen)}!={common_count}", errors)
    left = {normalize_code(x) for x in output.get("left_set_codes", [])}
    require(left <= seen, f"left_set_contains_unknown_codes:{sorted(left-seen)}", errors)
    by = {normalize_code(r.get('code')): r for r in output.get('companies', []) if isinstance(r, dict)}
    for code in left:
        require(by[code].get('valuation_status') == 'valid', f"left_set_contains_unavailable:{code}", errors)
        require(by[code].get('left_conclusion') in {'safe_buy_zone','reasonable_buy_zone'}, f"left_set_bad_conclusion:{code}:{by[code].get('left_conclusion')}", errors)
    upstream = output.get('upstream', {})
    require(upstream.get('fundamental_valuation') == 'PASS', 'left_fundamental_upstream_not_pass', errors)
    require(upstream.get('cycle_valuation') == 'PASS', 'left_cycle_upstream_not_pass', errors)
    return errors


def validate_final_selection(final: dict) -> list[str]:
    errors: list[str] = []
    left = {normalize_code(x) for x in final.get("left_set_codes", [])}
    right = {normalize_code(x) for x in final.get("right_set_codes", [])}
    intersection = {normalize_code(x) for x in final.get("initial_intersection_codes", [])}
    core = {normalize_code(x) for x in final.get("core_codes", [])}
    top3_list = [normalize_code(x) for x in final.get("top3_codes", [])]
    top3 = set(top3_list)

    require(intersection == left & right, f"final_intersection_mismatch:expected={sorted(left & right)}:got={sorted(intersection)}", errors)
    require(core <= intersection, f"final_core_not_subset_of_intersection:{sorted(core-intersection)}", errors)
    require(top3 <= core, f"final_top3_not_subset_of_core:{sorted(top3-core)}", errors)
    require(len(top3_list) == len(top3), "final_top3_duplicate_codes", errors)
    require(len(top3_list) <= 3, "final_top3_more_than_three", errors)
    require(bool(parse_iso(final.get("final_frozen_at"))), "final_missing_frozen_at", errors)

    upstream = final.get("upstream_validator_status", {})
    require(isinstance(upstream, dict), "final_upstream_status_must_be_object", errors)
    failed = [name for name, value in upstream.items() if value != "PASS"] if isinstance(upstream, dict) else ["invalid"]
    if failed:
        require(not core and not top3, f"final_has_core_despite_upstream_fail:{failed}", errors)

    reviews = final.get("reviews", {})
    require(isinstance(reviews, dict), "final_reviews_must_be_object", errors)
    if isinstance(reviews, dict):
        review_codes = {normalize_code(code) for code in reviews}
        require(intersection <= review_codes, f"final_missing_reviews:{sorted(intersection-review_codes)}", errors)
        for raw_code, review in reviews.items():
            code = normalize_code(raw_code)
            status = review.get("status") if isinstance(review, dict) else None
            require(status in FINAL_STATUS, f"final_invalid_review_status:{code}:{status}", errors)
            require(bool(review.get("reason")) if isinstance(review, dict) else False, f"final_missing_review_reason:{code}", errors)
            if status == "core":
                require(code in core, f"final_review_core_not_in_core_codes:{code}", errors)
            if code in top3:
                upside = review.get("first_target_upside_pct")
                rr = review.get("risk_reward")
                require(isinstance(upside, (int, float)) and upside >= 15, f"final_top3_upside_below_15:{code}:{upside}", errors)
                require(isinstance(rr, (int, float)) and rr >= 2, f"final_top3_rr_below_2:{code}:{rr}", errors)
    return errors


def print_result(stage: str, errors: list[str]) -> int:
    print(json.dumps({"stage": stage, "status": "PASS" if not errors else "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate modular A-share research stage outputs")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("weekly-scan", "fundamental-valuation", "cycle-valuation", "left-valuation", "final-selection"):
        p = sub.add_parser(name)
        p.add_argument("path")
    args = parser.parse_args()
    try:
        payload = load_json(args.path)
        if args.command == "weekly-scan":
            return print_result(args.command, validate_weekly_scan(payload))
        if args.command == "fundamental-valuation":
            return print_result(args.command, validate_fundamental_valuation(payload))
        if args.command == "cycle-valuation":
            return print_result(args.command, validate_cycle_valuation(payload))
        if args.command == "left-valuation":
            return print_result(args.command, validate_left_valuation(payload))
        return print_result(args.command, validate_final_selection(payload))
    except ValidationError as exc:
        return print_result(args.command, [str(exc)])


if __name__ == "__main__":
    sys.exit(main())
