#!/usr/bin/env python3
"""Fail-closed validator for an ephemeral A-share research completion ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


COUNT_EQUALITIES = (
    ("shard_file_count", "actual_shard_content_read_count"),
    ("level1_total_count", "level1_terminal_count"),
    ("improving_level1_count", "improving_level1_drilled_count"),
    ("admitted_level3_count", "admitted_level3_industry_state_applied_count"),
    ("company_universe_count", "company_industry_terminal_count"),
    ("mapped_eligible_count", "absolute_price_gate_terminal_count"),
    ("price_gate_pass_count", "gate1_terminal_count"),
    ("gate1_pass_count", "gate2_terminal_count"),
    ("gate2_pass_count", "gate3_terminal_count"),
    ("gate3_pass_count", "gate4_terminal_count"),
    ("gate4_pass_count", "valuation_terminal_count"),
    ("formal_valuation_count", "price_structure_terminal_count"),
    ("formal_valuation_count", "buy_point_terminal_count"),
)

REQUIRED_TRUE = (
    "data_gate_passed",
    "level1_scan_complete",
    "all_improving_level1_drilled",
    "all_admitted_level3_industry_state_applied",
    "all_company_industry_terminals_complete",
    "gate2_public_evidence_complete",
    "gate3_true_comparable_groups_confirmed",
    "gate4_public_evidence_complete",
    "all_cycle_valuations_have_valid_route_or_explicit_incomplete",
    "all_formal_valuations_have_structure",
    "all_formal_valuations_have_buy_point",
    "near_miss_source_legal",
)

REQUIRED_FALSE = (
    "stage_truncation_used",
    "gate2_mechanical_shortcut_used",
    "gate3_sw_level3_proxy_grouping_used",
    "gate4_partial_winner_research_used",
    "valuation_forbidden_shortcut_used",
    "historical_result_fallback_used",
)


def _as_nonnegative_int(value: Any, key: str, errors: list[str]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        errors.append(f"{key}: expected non-negative integer")
        return None
    return value


def validate_completion_ledger(payload: dict[str, Any]) -> list[str]:
    """Return violations. An empty list means the Completion Gate may proceed."""
    errors: list[str] = []

    for key in ("repo_commit_sha", "scan_source"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            errors.append(f"{key}: missing")

    if payload.get("scan_source") not in {
        "local_git_checkout",
        "local_commit_archive",
        "github_actions_runtime_snapshot",
    }:
        errors.append("scan_source: invalid")

    for key in REQUIRED_TRUE:
        if payload.get(key) is not True:
            errors.append(f"{key}: must be true")

    for key in REQUIRED_FALSE:
        if payload.get(key) is not False:
            errors.append(f"{key}: must be false")

    for left, right in COUNT_EQUALITIES:
        lval = _as_nonnegative_int(payload.get(left), left, errors)
        rval = _as_nonnegative_int(payload.get(right), right, errors)
        if lval is not None and rval is not None and lval != rval:
            errors.append(f"count mismatch: {left}={lval} != {right}={rval}")

    gate4 = _as_nonnegative_int(payload.get("gate4_pass_count"), "gate4_pass_count", errors)
    val_complete = _as_nonnegative_int(
        payload.get("valuation_complete_count"), "valuation_complete_count", errors
    )
    val_incomplete = _as_nonnegative_int(
        payload.get("valuation_incomplete_count"), "valuation_incomplete_count", errors
    )
    formal = _as_nonnegative_int(
        payload.get("formal_valuation_count"), "formal_valuation_count", errors
    )
    review = _as_nonnegative_int(payload.get("review_count"), "review_count", errors)
    if None not in (gate4, val_complete, val_incomplete):
        if val_complete + val_incomplete != gate4:
            errors.append(
                "valuation terminal mismatch: valuation_complete_count + "
                "valuation_incomplete_count must equal gate4_pass_count"
            )
    if None not in (val_complete, formal, review):
        if formal + review != val_complete:
            errors.append(
                "valuation disposition mismatch: formal_valuation_count + review_count "
                "must equal valuation_complete_count"
            )

    left_value = payload.get("left_value_codes")
    left_turn = payload.get("left_turn_codes")
    near_miss = payload.get("near_miss_codes")
    if not isinstance(left_value, list) or not all(isinstance(x, str) for x in left_value):
        errors.append("left_value_codes: expected list[str]")
        left_value = []
    if not isinstance(left_turn, list) or not all(isinstance(x, str) for x in left_turn):
        errors.append("left_turn_codes: expected list[str]")
        left_turn = []
    if not isinstance(near_miss, list) or not all(isinstance(x, str) for x in near_miss):
        errors.append("near_miss_codes: expected list[str]")
        near_miss = []

    if not set(left_turn).issubset(set(left_value)):
        errors.append("left_turn_codes must be a subset of left_value_codes")
    if set(left_value) & set(near_miss):
        errors.append("near_miss_codes must exclude left_value_codes")

    if payload.get("near_miss_sorted_by") != "reasonable_buy_range.upper":
        errors.append("near_miss_sorted_by must equal reasonable_buy_range.upper")

    if payload.get("gate3_grouping_basis") != "core_earnings_driver_and_business_model":
        errors.append(
            "gate3_grouping_basis must equal core_earnings_driver_and_business_model"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path, help="ephemeral completion-ledger JSON path")
    args = parser.parse_args()
    payload = json.loads(args.ledger.read_text(encoding="utf-8"))
    errors = validate_completion_ledger(payload)
    if errors:
        print("completion_gate_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("completion_gate_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
