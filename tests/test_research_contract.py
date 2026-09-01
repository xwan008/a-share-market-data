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
        "data_gate",
        "prompt_full_market_discovery",
        "taxonomy_mapping",
        "level3_profitability_refresh",
        "company_admission_gate",
        "profit_chain_resolution",
        "company_mapping_gate",
        "company_light_screen",
        "company_comparison_and_dedup",
        "valuation",
        "price_structure",
        "buy_point_synthesis",
        "completion_gate",
        "publish",
    ]


def test_data_gate_fails_closed_and_preserves_previous_valid_state():
    d = manifest()["data_gate_contract"]
    assert d["expected_trade_date_must_equal_health_trade_date"] is True
    assert d["market_status_must_be_closed"] is True
    assert d["source_errors_must_be_empty"] is True
    assert d["price_structure_must_cover_expected_trade_date"] is True
    assert d["fail_closed"] is True
    assert d["publish_on_failure"] is False
    assert d["mutate_valid_state_on_failure"] is False


def test_prompt_discovery_is_full_market_every_run_not_previous_list_incremental():
    d = manifest()["discovery_contract"]
    l3 = manifest()["level3_state_contract"]
    assert d["method"] == "prompt_full_market_light_recall_every_run"
    assert d["previous_focus_list_may_not_seed_or_bound_discovery"] is True
    assert d["previous_companies_chains_valuations_or_opportunities_may_not_seed_discovery"] is True
    assert d["top_n_or_fixed_count_selection_forbidden"] is True
    assert d["taxonomy_is_routing_after_discovery"] is True
    assert l3["prompt_discovery_is_full_market_even_on_daily_incremental_runs"] is True
    assert l3["daily_refresh_only_deep_rechecks_level3_nodes_with_new_or_changed_evidence"] is True


def test_level3_company_admission_supports_improving_and_stable_divergent():
    c = manifest()["company_admission_contract"]
    assert "trend=improving" in c["admit_if"]
    assert "trend=stable AND breadth=divergent" in c["admit_if"]
    assert "trend=deteriorating" in c["exclude_if"]
    assert c["stable_divergent_only_broadens_research_eligibility"] is True
    assert c["stable_divergent_does_not_lower_valuation_structure_or_buy_point_thresholds"] is True
    assert c["research_admission_top_n_forbidden"] is True


def test_company_mapping_gate_forbids_silent_omissions():
    g = manifest()["company_mapping_gate"]
    assert g["all_missing_or_unmapped_codes_must_be_checked_against_admitted_level3_scope"] is True
    assert g["unresolved_in_scope_mapping_forbidden"] is True
    assert g["silent_omission_forbidden"] is True
    assert g["on_unresolved_in_scope_mapping"] == "incomplete_research"


def test_company_screen_is_exhaustive_after_admission():
    c = manifest()["company_comparison_contract"]
    s = c["company_light_screen"]
    assert s["all_mapped_mainboard_companies_in_admitted_chain_must_be_screened"] is True
    assert s["top_n_or_score_cutoff_before_screen_forbidden"] is True
    assert s["exclusion_requires_company_specific_evidence"] is True
    assert s["all_survivors_enter_horizontal_comparison"] is True
    assert s["core_earnings_evidence_required_for_survive"] is True
    assert s["missing_core_earnings_evidence_cannot_default_to_earnings_quality_match_true"] is True
    assert c["dedup_must_preserve_all_source_chain_ids"] is True


def test_valuation_uses_simple_default_and_one_mos():
    v = manifest()["valuation_contract"]
    assert v["default_path"] == "relative_earnings_valuation"
    assert v["complex_model_is_exception_not_default"] is True
    assert v["fair_pe_construction"]["level3_peer_pe_is_primary_relative_anchor"] is True
    assert v["fair_pe_construction"]["pb_roe_cross_check_required"] is True
    assert v["market_sanity"]["history_window_trading_days"] == 180
    assert v["exception_trigger_required"] is True
    assert v["single_mos_application_required"] is True
    assert v["safe_price_ceiling_formula"] == "base_fair_value * (1 - margin_of_safety_pct)"


def test_buy_point_is_value_and_independent_structure_intersection():
    b = manifest()["buy_point_contract"]
    p = manifest()["price_structure_contract"]
    assert p["independent_from_valuation"] is True
    assert p["structure_entry_range_must_not_reference_fair_value"] is True
    assert b["hard_value_gate"] == "current_price <= safe_price_ceiling"
    assert b["buy_price_range_formula"] == "structure_entry_range intersect (-infinity, safe_price_ceiling]"
    assert b["empty_intersection_means_not_buyable_now"] is True
    assert b["damaged_or_overheated_cannot_be_buyable_now"] is True


def test_completion_and_persistence_fail_closed():
    g = manifest()["completion_gate_contract"]
    p = manifest()["persistence_contract"]
    assert g["company_mapping_gate_passed"] is True
    assert g["all_admitted_chains_company_screened"] is True
    assert g["current_opportunities_must_come_only_from_buyable_now"] is True
    assert g["publish_on_failure"] is False
    assert g["mutate_previous_valid_state_on_failure"] is False
    assert p["industry_state_is_only_cross_run_fundamental_memory"] is True
    assert p["research_state_contains_latest_valid_formal_run_only"] is True
    assert p["persistent_candidate_or_opportunity_pools_forbidden"] is True
    assert p["standalone_valuation_cache_forbidden"] is True
    assert p["old_v2_state_is_legacy_and_not_runtime_input"] is True


def test_near_miss_stays_display_only_without_lowering_buy_gate():
    n = manifest()["buy_point_contract"]["near_miss_ranking_contract"]
    assert n["must_output_when_eligible_universe_nonempty"] is True
    assert n["default_display_limit"] == 10
    assert n["ranking_is_display_only_not_candidate_pool"] is True
    assert "max(value_gap_pct, structure_gap_pct)" in n["action_distance_formula"]
    assert manifest()["public_output"]["near_miss_section_title"] == "【接近买点榜】"
