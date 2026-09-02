import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / "config/research_pipeline_manifest.json").read_text(encoding="utf-8"))


def test_manifest_is_stable_production_contract_without_numeric_schema():
    m = manifest()
    assert m["contract_id"] == "a-share-low-risk-production"
    assert m["pipeline"] == "a_share_low_risk"
    assert m["mode"] == "production"
    assert "schema_version" not in m
    assert m["public_output"]["formal_publish_enabled"] is True


def test_stage_order_contains_all_hard_gates():
    assert manifest()["stage_order"] == [
        "data_gate", "prompt_full_market_discovery", "taxonomy_mapping",
        "level3_profitability_refresh", "company_admission_gate",
        "profit_chain_resolution", "company_mapping_gate", "company_light_screen",
        "company_comparison_and_dedup", "valuation", "price_structure",
        "buy_point_synthesis", "completion_gate", "publish",
    ]


def test_prompt_discovery_is_full_market_every_run_while_level3_state_is_reused():
    m = manifest()
    d = m["discovery_contract"]
    l3 = m["level3_state_contract"]
    assert d["method"] == "prompt_full_market_light_recall_every_run"
    assert d["previous_focus_list_may_not_seed_or_bound_discovery"] is True
    assert d["previous_companies_chains_valuations_or_opportunities_may_not_seed_discovery"] is True
    assert d["company_chain_valuation_buy_results_are_ephemeral_per_run"] is True
    assert d["top_n_or_fixed_count_selection_forbidden"] is True
    assert l3["existing_valid_level3_state_must_be_reused"] is True
    assert l3["missing_level3_state_initialized_on_demand"] is True
    assert l3["stale_or_invalid_level3_state_revalidated_individually"] is True
    assert l3["whole_state_rebuild_for_missing_nodes_forbidden"] is True
    assert l3["daily_refresh_only_deep_rechecks_level3_nodes_with_new_or_changed_evidence"] is True


def test_both_profit_chain_types_are_admitted_and_share_downstream_rules():
    m = manifest()
    c = m["company_admission_contract"]
    p = m["profit_chain_contract"]
    assert "trend=improving" in c["admit_if"]
    assert "trend=stable AND breadth=divergent" in c["admit_if"]
    assert p["allowed_chain_types"] == ["improving", "stable_divergent"]
    assert p["both_chain_types_follow_same_company_screen_valuation_structure_and_buy_point_rules"] is True
    assert c["stable_divergent_does_not_lower_valuation_structure_or_buy_point_thresholds"] is True


def test_data_and_company_mapping_gates_fail_closed():
    m = manifest()
    d = m["data_gate_contract"]
    g = m["company_mapping_gate"]
    assert d["fail_closed"] is True
    assert d["publish_on_failure"] is False
    assert d["mutate_industry_state_on_failure"] is False
    assert g["inactive_or_untradable_company_is_runtime_skip"] is True
    assert g["inactive_or_untradable_does_not_block_completion"] is True
    assert g["all_missing_or_unmapped_codes_must_be_checked_against_admitted_level3_scope"] is True
    assert g["unresolved_in_scope_mapping_forbidden"] is True
    assert g["silent_omission_forbidden"] is True


def test_company_filtering_funnel_is_exhaustive_without_top_n():
    c = manifest()["company_comparison_contract"]
    assert c["full_chain_recall_required_before_filtering"] is True
    assert c["research_admission_top_n_forbidden"] is True
    assert c["company_level_inputs_dedup_before_expensive_research"] is True
    assert c["dedup_key"] == "stock_code"
    assert c["dedup_must_preserve_all_source_chain_ids"] is True
    assert c["same_company_financial_and_valuation_inputs_must_be_reused_within_run"] is True

    hard = c["financial_hard_screen"]
    assert hard["applies_to_unique_companies"] is True
    assert hard["missing_core_earnings_cannot_default_pass"] is True
    assert hard["nonrecurring_dominance_threshold_of_parent_netprofit"] == 0.30

    driver = c["driver_quality_gate"]
    assert driver["admit_only_if"] == [
        "company_level_driver_clear",
        "core_earnings_improving",
        "cashflow_and_earnings_quality_acceptable",
        "sustainability_sufficient",
    ]
    assert driver["top_n_or_fixed_quota_forbidden"] is True

    peer = c["peer_redundancy_filter"]
    assert peer["exclude_only_if_dominated_by_peer"] is True
    assert peer["material_tradeoff_requires_both_companies_retained"] is True
    assert peer["fixed_per_industry_count_forbidden"] is True
    assert peer["leader_only_rule_forbidden"] is True

    pre = c["valuation_precheck"]
    assert pre["absolute_cross_industry_pe_cap_forbidden"] is True
    assert pre["high_pe_must_be_judged_against_peers_and_core_growth"] is True
    assert pre["uncertain_or_tradeoff_case_must_continue_to_full_valuation"] is True
    assert pre["precheck_cannot_generate_fair_value_or_buy_point"] is True

    comp = c["horizontal_comparison"]
    assert comp["applies_after_financial_driver_peer_and_precheck_filters"] is True
    assert comp["must_cover_all_remaining_companies"] is True
    assert comp["top_n_or_fixed_quota_forbidden"] is True


def test_valuation_migrates_legacy_safe_range_logic_into_fixed_reasonable_buy_range():
    m = manifest()
    v = m["valuation_contract"]
    r = v["reasonable_buy_range_contract"]
    assert v["default_path"] == "relative_earnings_valuation"
    assert v["complex_model_is_exception_not_default"] is True
    assert v["single_mos_application_required"] is True
    assert v["cycle_normalization_check_required"] is True
    assert v["extreme_cycle_peak_earnings_may_not_be_mechanically_extrapolated"] is True
    assert v["safe_price_ceiling_formula"] == "base_fair_value * (1 - margin_of_safety_pct)"
    assert r["required_for_every_complete_non_review_company"] is True
    assert r["valuation_only"] is True
    assert r["must_be_bounded_interval"] is True
    assert r["normal_path_constructor"] == "lower = safe_price_ceiling * 0.95; upper = safe_price_ceiling"
    assert r["normal_path_width_pct"] == 5.0
    assert r["upper_bound_must_equal_safe_price_ceiling"] is True
    assert r["legacy_safe_price_range_core_logic_migrated"] is True
    assert r["legacy_safe_price_range_field_deprecated"] is True
    assert r["execution_width_is_not_second_margin_of_safety"] is True
    assert r["must_not_reference_price_structure"] is True
    assert r["double_margin_of_safety_forbidden"] is True
    assert r["price_position_states"] == [
        "above_buy_range", "inside_buy_range", "deep_discount_review"
    ]
    assert r["deep_discount_requires_fundamental_and_valuation_recheck"] is True
    assert r["deep_discount_is_not_automatic_buy"] is True
    assert r["deep_discount_is_not_near_miss"] is True


def test_buy_point_contract_is_two_left_side_lists_not_single_intersection():
    m = manifest()
    b = m["buy_point_contract"]
    p = m["price_structure_contract"]
    assert b["value_anchor"] == "reasonable_buy_range"
    assert b["left_value_list"]["formula"] == "valuation_position == inside_buy_range"
    assert b["left_value_list"]["equivalent_price_formula"] == (
        "reasonable_buy_range.lower <= current_price <= reasonable_buy_range.upper"
    )
    assert b["left_value_list"]["price_structure_is_not_hard_gate"] is True
    assert b["left_value_list"]["deep_discount_review_not_automatic_buy"] is True
    assert b["left_turn_list"]["formula"] == "left_value_buyable_now AND left_turn_confirmed"
    assert b["left_turn_list"]["must_be_subset_of_left_value_list"] is True
    assert b["left_turn_list"]["requires_price_still_inside_reasonable_buy_range"] is True
    assert b["legacy_single_buyable_now_list_forbidden"] is True
    assert p["independent_from_valuation"] is True
    assert p["price_structure_is_not_hard_gate_for_left_value_list"] is True
    assert p["left_turn_confirmation_is_for_turn_list_only"] is True


def test_completion_persistence_and_near_miss_fail_closed():
    m = manifest()
    g = m["completion_gate_contract"]
    p = m["persistence_contract"]
    n = m["buy_point_contract"]["near_miss_ranking_contract"]
    assert g["all_admitted_chains_company_recalled"] is True
    assert g["unique_company_dedup_complete"] is True
    assert g["all_unique_companies_have_financial_hard_screen_decision"] is True
    assert g["all_financial_screen_survivors_have_driver_quality_decision"] is True
    assert g["all_driver_quality_survivors_have_peer_redundancy_decision"] is True
    assert g["all_peer_filter_survivors_have_valuation_precheck_decision"] is True
    assert g["all_precheck_survivors_horizontally_compared"] is True
    assert g["all_complete_non_review_companies_have_reasonable_buy_range"] is True
    assert g["all_complete_non_review_companies_have_valuation_position"] is True
    assert g["deep_discount_cases_rechecked_or_explicit_review"] is True
    assert g["all_complete_non_review_companies_have_left_value_assessment"] is True
    assert g["all_complete_non_review_companies_have_left_turn_assessment"] is True
    assert g["left_turn_list_is_verified_subset_of_left_value_list"] is True
    assert g["near_miss_contains_only_above_buy_range"] is True
    assert g["near_miss_excludes_current_left_value_list"] is True
    assert g["near_miss_excludes_deep_discount_review"] is True
    assert g["publish_on_failure"] is False
    assert g["mutate_industry_state_on_failure"] is False
    assert p["industry_state_is_only_cross_run_fundamental_memory"] is True
    assert p["run_company_chain_valuation_buy_outputs_are_ephemeral"] is True
    assert p["published_leaderboard_is_current_run_only"] is True
    assert p["persistent_formal_run_state_forbidden"] is True
    assert p["legacy_company_valuation_buy_state_reuse_forbidden"] is True
    assert "research_state_path" not in p
    assert "research_state" not in m["authoritative_data"]
    assert n["ranking_is_display_only_not_candidate_pool"] is True
    assert n["eligible_only_when_price_above_buy_range_upper"] is True
    assert n["deep_discount_review_excluded_from_near_miss"] is True
    assert n["default_display_limit"] == 10


def test_public_output_has_both_left_side_lists():
    o = manifest()["public_output"]
    assert o["left_value_section_title"] == "【左侧价值买点榜】"
    assert o["left_turn_section_title"] == "【左侧拐点买点榜】"
    assert o["left_value_section_title"] in o["sections"]
    assert o["left_turn_section_title"] in o["sections"]
