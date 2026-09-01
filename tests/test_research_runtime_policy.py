import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Schema30 CI checkpoint: run only against a fresh/current state, never stale schema27 output.

def load(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))


def test_repo_whitelist_and_public_evidence_are_separate_layers():
    p = load('config/research_runtime_policy.json')
    assert p['schema_version'] == 10
    assert p['research_read_mode'] == 'manifest_repo_data_plus_current_public_evidence'
    assert p['repository_data_policy']['allow_only_manifest_authoritative_data'] is True
    assert p['public_evidence_policy']['allowed'] is True
    assert p['public_evidence_policy']['required_for_1800_research'] is True


def test_valid_industry_baseline_does_not_depend_on_1800_generation_time():
    p = load('config/research_runtime_policy.json')
    c = p['state_compatibility']
    s = p['stage_execution_policy']
    assert c['valid_industry_baseline_is_independent_of_generation_clock'] is True
    assert c['morning_run_requires_valid_previous_1800_state'] is False
    assert c['morning_run_requires_valid_current_schema_industry_baseline'] is True
    assert c['scheduled_1800_is_refresh_anchor_not_baseline_eligibility_requirement'] is True
    assert s['valid_weekly_baseline_may_be_generated_by_bootstrap_manual_or_scheduled_full_scan'] is True
    assert s['company_research_may_start_from_valid_industry_baseline_regardless_of_baseline_generation_time'] is True


def test_weekly_baseline_and_daily_incremental_are_enforced():
    p = load('config/research_runtime_policy.json')
    d = p['discovery_policy']
    s = p['stage_execution_policy']
    assert d['weekly_industry_baseline_may_carry_forward_between_full_scans'] is True
    assert d['previous_state_may_seed_only_industry_baseline_for_daily_incremental'] is True
    assert d['previous_companies_chains_valuations_or_opportunities_may_not_seed_1800_discovery'] is True
    assert d['previous_companies_chains_valuations_or_opportunities_may_not_seed_manual_or_morning_company_discovery'] is True
    assert d['cross_run_candidate_or_opportunity_pools_forbidden'] is True
    assert d['research_admission_top_n_forbidden'] is True
    assert d['research_admission_per_level1_chain_cap_forbidden'] is True
    assert d['weekly_prompt_full_market_prosperity_search_cannot_be_replaced_by_previous_focus_list'] is True
    assert d['persistent_level1_level2_prosperity_status_forbidden'] is True
    assert s['weekly_full_requires_prompt_full_market_prosperity_search'] is True
    assert s['weekly_full_must_not_build_level1_level2_status_matrix'] is True
    assert s['weekly_full_scan_does_not_require_all_346_level3_profitability_reviews'] is True
    assert s['prosperity_search_must_precede_level3_profitability_verification'] is True
    assert s['prosperity_search_top_n_forbidden'] is True
    assert s['every_selected_direction_must_map_to_relevant_level3'] is True
    assert s['every_mapped_relevant_level3_must_be_profitability_verified'] is True
    assert s['daily_incremental_requires_valid_weekly_baseline'] is True
    assert s['daily_incremental_uses_prompt_search_for_new_or_changed_prosperity_evidence'] is True


def test_full_improving_chain_to_company_flow_cannot_shortcut():
    s = load('config/research_runtime_policy.json')['stage_execution_policy']
    assert s['every_confirmed_improving_chain_must_receive_company_light_screen'] is True
    assert s['all_mapped_mainboard_companies_in_chain_must_be_light_screened_before_any_ranking'] is True
    assert s['light_screen_exclusions_require_company_specific_evidence'] is True
    assert s['all_light_screen_survivors_must_be_horizontally_compared'] is True
    assert s['cross_chain_duplicate_company_must_preserve_all_chain_memberships'] is True
    assert s['valuation_set_must_be_deduplicated_by_stock_code'] is True
    assert s['all_compared_companies_must_enter_valuation_set'] is True


def test_valuation_and_buy_point_cannot_shortcut():
    s = load('config/research_runtime_policy.json')['stage_execution_policy']
    assert s['every_valuation_set_company_must_be_executed'] is True
    assert s['corporate_action_check_must_precede_earnings_bridge'] is True
    assert s['historical_eps_scaling_across_material_share_change_forbidden'] is True
    assert s['resource_and_order_cycle_current_growth_pe_shortcut_forbidden'] is True
    assert s['extreme_valuation_deviation_requires_independent_secondary_method'] is True
    assert s['review_required_is_exception_not_completion_shortcut'] is True
    assert s['every_complete_non_review_company_requires_buy_point_assessment'] is True
    assert s['buy_point_requires_value_and_timing_intersection'] is True
    assert s['current_opportunity_requires_buyable_now'] is True
    assert s['every_complete_non_review_company_requires_near_miss_distance'] is True
    assert s['near_miss_top10_must_be_output_when_eligible_universe_nonempty'] is True
    assert s['empty_current_opportunities_does_not_allow_empty_near_miss_output'] is True


def test_state_schema_match_when_present():
    p = load('config/research_runtime_policy.json')
    m = load(p['manifest_path'])
    assert p['write_policy']['persistent_intermediate_research_outputs_forbidden'] is True
    assert p['write_policy']['weekly_baseline_must_live_inside_research_state'] is True
    assert p['write_policy']['new_state_must_include_coverage_ledger_company_light_screen_buy_points_and_scan_mode'] is True
    sp = ROOT / p['active_state_path']
    if sp.exists():
        assert json.loads(sp.read_text(encoding='utf-8')).get('manifest_schema') == m['schema_version']


def test_authoritative_repository_data_is_small_and_explicit():
    assert set(load('config/research_pipeline_manifest.json')['authoritative_data']) == {
        'industry_coverage_taxonomy', 'company_index', 'full_market_price_structure',
        'latest_market', 'bounded_history_store', 'research_state'
    }


def test_legacy_research_pool_artifacts_stay_absent():
    legacy_paths = [
        'data/research/pipeline',
        'data/research/company_buckets',
        'data/research/company_industry_registry.json',
        'data/research/weekly_fundamental_opportunity_pool.json',
    ]
    for path in legacy_paths:
        assert not (ROOT / path).exists(), path
