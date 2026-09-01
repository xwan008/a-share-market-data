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
    assert p["failure_may_not_overwrite_previous_valid_state"] is True


def test_every_run_has_full_market_prompt_recall_while_level3_is_incremental():
    p = load("config/research_runtime_policy.json")
    d = p["discovery_policy"]
    l3 = p["level3_refresh_policy"]
    assert d["prompt_full_market_light_recall_required_every_run"] is True
    assert d["daily_run_may_not_limit_prompt_discovery_to_previous_directions"] is True
    assert d["previous_industry_state_may_accelerate_level3_refresh_but_may_not_bound_discovery"] is True
    assert d["previous_companies_chains_valuations_or_opportunities_may_not_seed_discovery"] is True
    assert l3["daily_incremental_between_full_refreshes"] is True
    assert l3["daily_incremental_rechecks_level3_only_when_new_or_changed_evidence_exists"] is True


def test_runtime_bootstraps_before_incremental_when_no_valid_industry_baseline():
    l3 = load("config/research_runtime_policy.json")["level3_refresh_policy"]
    assert l3["bootstrap_full_refresh_required_when_state_missing_invalid_or_requires_full_refresh"] is True
    assert l3["bootstrap_ignores_weekly_anchor"] is True
    assert l3["bootstrap_must_complete_before_daily_incremental_mode"] is True


def test_company_admission_and_mapping_are_hard_runtime_gates():
    s = load("config/research_runtime_policy.json")["stage_execution_policy"]
    assert s["company_admission_accepts_improving"] is True
    assert s["company_admission_accepts_stable_divergent"] is True
    assert s["stable_divergent_does_not_relax_downstream_thresholds"] is True
    assert s["deteriorating_or_unconfirmed_cannot_enter_company_layer"] is True
    assert s["company_mapping_gate_must_run_before_company_screen"] is True
    assert s["all_missing_or_unmapped_company_index_codes_must_be_checked_for_admitted_scope"] is True
    assert s["unresolved_in_scope_company_mapping_fails_completion"] is True
    assert s["every_admitted_chain_must_receive_company_light_screen"] is True


def test_company_valuation_buy_point_flow_cannot_shortcut():
    s = load("config/research_runtime_policy.json")["stage_execution_policy"]
    assert s["all_mapped_mainboard_companies_in_chain_must_be_light_screened_before_any_ranking"] is True
    assert s["all_light_screen_survivors_must_be_horizontally_compared"] is True
    assert s["valuation_set_must_be_deduplicated_by_stock_code"] is True
    assert s["all_compared_companies_must_enter_valuation_set"] is True
    assert s["every_valuation_set_company_must_be_executed"] is True
    assert s["normal_profitable_company_uses_simple_relative_valuation_by_default"] is True
    assert s["exception_trigger_required_before_complex_model"] is True
    assert s["single_margin_of_safety_application_required"] is True
    assert s["every_complete_non_review_company_requires_price_structure"] is True
    assert s["every_complete_non_review_company_requires_buy_point_assessment"] is True
    assert s["current_opportunity_requires_buyable_now"] is True


def test_persistence_is_split_into_compact_industry_memory_and_latest_formal_run():
    p = load("config/research_runtime_policy.json")
    w = p["write_policy"]
    assert p["industry_state_path"] == "data/research/industry_state.json"
    assert p["active_state_path"] == "data/research/research_state.json"
    assert w["industry_state_is_only_cross_run_fundamental_memory"] is True
    assert w["current_research_state_is_latest_valid_formal_run_only"] is True
    assert w["persistent_candidate_or_opportunity_pools_forbidden"] is True
    assert w["standalone_valuation_cache_forbidden"] is True
    assert w["write_only_after_data_gate_and_completion_gate_pass"] is True


def test_authoritative_data_paths_are_explicit_and_legacy_v2_is_not_runtime_input():
    m = load("config/research_pipeline_manifest.json")
    assert m["authoritative_data"]["industry_state"] == "data/research/industry_state.json"
    assert m["authoritative_data"]["research_state"] == "data/research/research_state.json"
    assert m["authoritative_data"]["full_market_price_structure"] == "data/research/full_market_price_structure.json"
    assert load("config/research_runtime_policy.json")["repository_data_policy"]["legacy_v2_research_files_are_not_runtime_input"] is True
