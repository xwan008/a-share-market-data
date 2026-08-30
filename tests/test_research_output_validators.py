from scripts.validate_research_outputs import (
    validate_final_selection,
    validate_fundamental_valuation,
    validate_weekly_scan,
)


def test_weekly_scan_requires_full_universe_coverage():
    scan = {
        "industry_state_modified": False,
        "t2_recall_frozen_at": "2026-08-30T18:10:00+08:00",
        "weekly_pool_read_at": "2026-08-30T18:11:00+08:00",
        "universe_count": 2,
        "screened_count": 2,
        "screen_results": {
            "000001": {"status": "reject", "reason": "no forward inflection"},
            "000338": {"status": "pass", "reason": "forward earnings driver visible"},
        },
        "deep_verified_codes": ["000338"],
        "pool_active_codes": ["000338"],
    }
    assert validate_weekly_scan(scan) == []
    scan["screened_count"] = 1
    assert any("weekly_screened_count_mismatch" in e for e in validate_weekly_scan(scan))


def test_weekly_scan_cannot_precede_t2_freeze_or_modify_industry():
    scan = {
        "industry_state_modified": True,
        "t2_recall_frozen_at": "2026-08-30T18:10:00+08:00",
        "weekly_pool_read_at": "2026-08-30T18:05:00+08:00",
        "universe_count": 0,
        "screened_count": 0,
        "screen_results": {},
        "deep_verified_codes": [],
        "pool_active_codes": [],
    }
    errors = validate_weekly_scan(scan)
    assert "weekly_scan_must_not_modify_industry_state" in errors
    assert "weekly_scan_read_before_t2_recall_freeze" in errors


def test_fundamental_valuation_requires_traceable_ranges():
    output = {
        "common_pool_count": 1,
        "deferred_cycle_codes": [],
        "policy_coverage": {
            "noncycle_count": 1,
            "supported_policy_count": 1,
            "unsupported_policy_count": 0,
            "supported_policy_codes": ["002475"],
            "unsupported_policy_codes": [],
        },
        "companies": [
            {
                "code": "002475",
                "valuation_status": "valid",
                "policy_status": "supported",
                "valuation_model": "multi_engine_precision_manufacturing_forward_pe",
                "valuation_basis_unit": "PE",
                "forecast_source": "analyst_consensus",
                "consensus_eps_current_year": 3.2,
                "forward_earnings_basis": "2026/2027 consensus forward earnings",
                "reasonable_multiple_range": [18, 22],
                "multiple_rationale": "versioned business valuation policy",
                "value_anchor_range": [57.6, 77.0],
                "safe_buy_range": [52, 58],
                "reasonable_buy_range": [58, 68],
                "key_sensitivities": ["AI data-center revenue", "margin"],
                "invalidation_condition": "forward earnings downgrade",
            }
        ],
    }
    assert validate_fundamental_valuation(output) == []
    output["companies"][0].pop("value_anchor_range")
    assert any("valuation_bad_anchor_range" in e for e in validate_fundamental_valuation(output))


def test_final_selection_is_strict_intersection_and_top3_subset():
    final = {
        "left_set_codes": ["000338", "002475"],
        "right_set_codes": ["000338", "600312"],
        "initial_intersection_codes": ["000338"],
        "reviews": {
            "000338": {
                "status": "core",
                "reason": "all gates pass",
                "first_target_upside_pct": 16.0,
                "risk_reward": 2.2,
            }
        },
        "core_codes": ["000338"],
        "top3_codes": ["000338"],
        "upstream_validator_status": {
            "industry_scan": "PASS",
            "t2_recall": "PASS",
            "earnings": "PASS",
            "left": "PASS",
            "right": "PASS",
        },
        "final_frozen_at": "2026-08-30T18:40:00+08:00",
    }
    assert validate_final_selection(final) == []
    final["initial_intersection_codes"] = ["002475"]
    assert any("final_intersection_mismatch" in e for e in validate_final_selection(final))


def test_final_selection_blocks_core_if_upstream_failed():
    final = {
        "left_set_codes": ["000338"],
        "right_set_codes": ["000338"],
        "initial_intersection_codes": ["000338"],
        "reviews": {"000338": {"status": "core", "reason": "test", "first_target_upside_pct": 20, "risk_reward": 2.5}},
        "core_codes": ["000338"],
        "top3_codes": ["000338"],
        "upstream_validator_status": {"right": "FAIL"},
        "final_frozen_at": "2026-08-30T18:40:00+08:00",
    }
    assert any("final_has_core_despite_upstream_fail" in e for e in validate_final_selection(final))
