import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_runtime_is_production_and_forbids_schema_shadow_modes():
    p = load("config/research_runtime_policy.json")
    assert p["contract_id"] == "a-share-low-risk-production"
    assert p["mode"] == "production"
    assert "schema_version" not in p
    assert p["production_policy"]["formal_publish_enabled"] is True
    assert p["production_policy"]["shadow_mode_forbidden"] is True
    assert p["production_policy"]["numeric_schema_versioning_for_research_contract_forbidden"] is True


def test_runtime_data_gate_fails_closed():
    p = load("config/research_runtime_policy.json")["data_gate_policy"]
    assert p["must_run_before_all_formal_research"] is True
    assert p["health_trade_date_must_match_expected_trade_date"] is True
    assert p["health_market_status_must_be_closed"] is True
    assert p["latest_history_and_price_structure_must_match_expected_trade_date"] is True
    assert p["failure_may_not_publish_new_formal_result"] is True
    assert p["failure_may_not_mutate_cross_run_industry_state"] is True


def test_history_window_semantics_are_explicit_and_storage_authoritative():
    h = load("config/research_runtime_policy.json")["history_semantics_policy"]
    assert h["summary_window_days"] == 65
    assert h["summary_structure_window_days"] == 60
    assert h["price_structure_min_points"] == 120
    assert h["price_structure_target_points"] == 180
    assert h["storage_window_days"] == 180
    assert h["authoritative_storage_source"] == "data/history_shards/*.json"
    assert h["summary_window_is_not_storage_length"] is True
    assert h["legacy_health_schema_6_window_days_is_summary_only"] is True
    assert h["legacy_health_schema_6_coverage_max_points_is_summary_only"] is True
    assert h["model_must_not_infer_storage_insufficiency_from_summary_points"] is True
    assert h["storage_sufficiency_must_be_judged_from_history_shards_or_explicit_storage_coverage"] is True


def test_every_run_has_full_market_prompt_recall_and_reuses_only_level3_state():
    p = load("config/research_runtime_policy.json")
    d = p["discovery_policy"]
    l3 = p["level3_refresh_policy"]
    assert d["prompt_full_market_light_recall_required_every_run"] is True
    assert d["daily_run_may_not_limit_prompt_discovery_to_previous_directions"] is True
    assert d["previous_industry_state_may_accelerate_level3_refresh_but_may_not_bound_discovery"] is True
    assert d["previous_companies_chains_valuations_or_opportunities_may_not_seed_discovery"] is True
    assert d["company_chain_valuation_buy_results_are_ephemeral_per_run"] is True
    assert l3["existing_valid_level3_state_must_be_reused"] is True
    assert l3["missing_level3_state_initialized_on_demand"] is True
    assert l3["stale_or_invalid_level3_state_revalidated_individually"] is True
    assert l3["whole_state_rebuild_for_missing_nodes_forbidden"] is True
    assert l3["daily_incremental_rechecks_level3_only_when_new_or_changed_evidence_exists"] is True


def test_company_admission_and_mapping_are_hard_runtime_gates():
    s = load("config/research_runtime_policy.json")["stage_execution_policy"]
    assert s["company_admission_accepts_improving"] is True
    assert s["company_admission_accepts_stable_divergent"] is True
    assert s["stable_divergent_does_not_relax_downstream_thresholds"] is True
    assert s["deteriorating_or_unconfirmed_cannot_enter_company_layer"] is True
    assert s["company_mapping_gate_must_run_before_company_screen"] is True
    assert s["inactive_or_untradable_company_is_runtime_skip"] is True
    assert s["unresolved_in_scope_company_mapping_fails_completion"] is True
    assert s["every_admitted_chain_must_be_fully_recalled_before_filtering"] is True


def test_company_filtering_and_valuation_flow_cannot_shortcut():
    s = load("config/research_runtime_policy.json")["stage_execution_policy"]
    assert s["company_chain_relations_must_preserve_all_memberships"] is True
    assert s["company_level_inputs_must_be_deduplicated_by_stock_code_before_expensive_research"] is True
    assert s["same_company_financial_inputs_are_reused_within_run"] is True
    assert s["financial_hard_screen_must_check_core_earnings_cashflow_nonrecurring_and_business_change"] is True
    assert s["missing_deducted_profit_cannot_silently_pass"] is True
    assert s["driver_quality_requires_company_driver_clear"] is True
    assert s["driver_quality_requires_core_earnings_improving"] is True
    assert s["driver_quality_requires_cashflow_and_earnings_quality_acceptable"] is True
    assert s["driver_quality_requires_sustainability_sufficient"] is True
    assert s["peer_redundancy_may_exclude_only_dominated_by_peer"] is True
    assert s["peer_tradeoff_requires_both_companies_retained"] is True
    assert s["peer_filter_fixed_quota_or_leader_only_forbidden"] is True
    assert s["valuation_precheck_must_run_before_full_valuation"] is True
    assert s["valuation_precheck_may_exclude_only_obviously_expensive"] is True
    assert s["absolute_cross_industry_pe_cap_forbidden"] is True
    assert s["high_pe_must_be_judged_against_peers_and_core_growth"] is True
    assert s["valuation_precheck_uncertain_or_tradeoff_case_must_continue"] is True
    assert s["horizontal_comparison_applies_to_all_companies_remaining_after_filters"] is True
    assert s["horizontal_comparison_top_n_or_fixed_quota_forbidden"] is True
    assert s["valuation_set_must_be_deduplicated_by_stock_code"] is True
    assert s["every_valuation_set_company_must_be_executed"] is True
    assert s["normal_profitable_company_uses_simple_relative_valuation_by_default"] is True
    assert s["exception_trigger_required_before_complex_model"] is True
    assert s["single_margin_of_safety_application_required"] is True
    assert s["every_complete_non_review_company_requires_price_structure"] is True
    assert s["every_complete_non_review_company_requires_buy_point_assessment"] is True
    assert s["current_opportunity_requires_buyable_now"] is True


def test_only_industry_state_is_cross_run_research_memory():
    p = load("config/research_runtime_policy.json")
    w = p["write_policy"]
    assert p["industry_state_path"] == "data/research/industry_state.json"
    assert "active_state_path" not in p
    assert p["repository_data_policy"]["research_state_file_forbidden"] is True
    assert w["industry_state_is_only_cross_run_fundamental_memory"] is True
    assert w["research_run_outputs_are_not_persisted"] is True
    assert w["published_leaderboard_is_current_run_only"] is True
    assert w["persistent_formal_run_state_forbidden"] is True
    assert "current_research_output" not in w
    assert w["persistent_candidate_or_opportunity_pools_forbidden"] is True
    assert w["standalone_valuation_cache_forbidden"] is True
    assert w["industry_state_write_only_after_data_gate_and_completion_gate_pass"] is True


def test_legacy_v2_is_not_runtime_input():
    p = load("config/research_runtime_policy.json")
    assert p["repository_data_policy"]["legacy_v2_research_files_are_not_runtime_input"] is True
    assert p["repository_data_policy"]["git_history_is_audit_only_not_runtime_input"] is True
