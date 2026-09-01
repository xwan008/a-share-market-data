import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))


def test_manifest_schema28_and_stage_order():
    m = manifest()
    assert m['schema_version'] == 28
    assert m['mode'] == 'shadow'
    assert m['stage_order'] == [
        'data_health', 'taxonomy_coverage', 'profitability_scan',
        'profit_chain_decomposition', 'chain_company_light_screen',
        'chain_company_comparison_and_dedup', 'valuation', 'price_structure',
        'buy_point_synthesis', 'completion_gate'
    ]
    assert m['coverage_contract']['expected_counts'] == {'level1': 31, 'level2': 134, 'level3': 346}


def test_scan_cadence_is_weekly_full_plus_daily_incremental_not_weekly_pool():
    c = manifest()['scan_cadence_contract']
    assert c['full_scan_unit'] == 'level3'
    assert c['full_scan_expected_level3_nodes'] == 346
    assert c['calendar_anchor_is_authoritative'] is True
    assert c['interval_days_is_max_baseline_age_not_minimum_wait'] is True
    assert 'Friday 18:00' in c['successful_bootstrap_next_full_scan']
    assert c['daily_incremental_between_full_scans'] is True
    assert c['full_scan_is_market_state_baseline_not_candidate_pool'] is True
    assert c['previous_companies_chains_or_opportunities_may_not_seed_discovery'] is True


def test_coverage_uses_four_dimensions_and_no_generic_weekly_placeholder():
    c = manifest()['coverage_contract']['ledger_contract']
    assert c['instantiate_all_taxonomy_nodes_before_profitability_scan'] is True
    assert set(c['allowed_trend']) == {'improving', 'stable', 'deteriorating', 'unconfirmed'}
    assert c['weekly_level3_generic_unconfirmed_placeholder_forbidden'] is True
    assert c['weekly_level3_each_node_requires_real_evidence_review'] is True
    assert c['counts_must_be_derived_from_ledger_not_manually_asserted'] is True


def test_profit_chain_research_admission_cannot_use_top_n():
    p = manifest()['profit_chain_resolution_contract']
    assert p['research_admission_top_n_forbidden'] is True
    assert p['per_level1_chain_cap_forbidden'] is True
    assert p['every_confirmed_improving_chain_requires_company_light_screen'] is True
    assert 'trend=improving' in p['confirmed_improving_chain_definition']


def test_company_light_screen_is_exhaustive_and_dedup_is_lossless():
    c = manifest()['company_comparison_contract']
    s = c['company_light_screen']
    assert s['all_mapped_mainboard_companies_in_confirmed_improving_chain_must_be_screened'] is True
    assert s['top_n_or_score_cutoff_before_screen_forbidden'] is True
    assert s['exclusion_requires_company_specific_evidence'] is True
    assert s['all_survivors_enter_horizontal_comparison'] is True
    assert c['horizontal_comparison_must_cover_all_screen_survivors'] is True
    assert c['cross_chain_dedup_after_comparison'] is True
    assert c['dedup_key'] == 'stock_code'
    assert c['dedup_must_preserve_all_source_chain_ids'] is True
    assert c['valuation_set_must_be_deduplicated_by_stock_code'] is True
    assert c['completion_requires_no_unscreened_confirmed_improving_chains'] is True


def test_valuation_requires_corporate_action_and_extreme_deviation_audits():
    v = manifest()['valuation_resolution_contract']
    assert v['every_valuation_set_company_requires_full_execution'] is True
    assert v['corporate_action_check_required_before_earnings_bridge'] is True
    assert v['historical_eps_direct_scaling_across_material_share_count_change_forbidden'] is True
    assert v['material_share_count_change_threshold_pct'] == 5.0
    assert v['when_share_count_changes_use_aggregate_earnings_and_current_or_forward_diluted_share_count'] is True
    assert v['resource_and_order_cycle_companies_cannot_use_growth_pe_from_current_profit_growth'] is True
    audit = v['extreme_valuation_deviation_audit']
    assert audit['required'] is True
    assert audit['requires_independent_secondary_method'] is True
    assert audit['requires_share_count_and_corporate_action_recheck'] is True
    assert audit['max_method_midpoint_divergence_pct_before_model_instability'] == 30.0


def test_buy_point_is_value_and_structure_intersection():
    b = manifest()['buy_point_contract']
    assert b['required_for_every_complete_non_review_valuation'] is True
    assert b['buy_price_range_must_equal_intersection_of_safe_price_range_and_structure_entry_range'] is True
    assert b['empty_intersection_means_not_buyable_now'] is True
    assert b['damaged_or_overheated_cannot_be_buyable_now'] is True
    assert b['buyable_now_requires_value_and_timing_true'] is True
    assert b['price_structure_must_not_modify_intrinsic_value'] is True
    near = b['near_miss_ranking_contract']
    assert near['must_output_when_eligible_universe_nonempty'] is True
    assert near['default_display_limit'] == 10
    assert near['ranking_is_display_only_not_candidate_pool'] is True
    assert 'near_miss_ranking' in manifest()['research_state_contract']['required_top_level_sections']
    assert manifest()['public_output']['near_miss_must_be_nonempty_when_eligible_universe_nonempty'] is True
    assert manifest()['public_output']['near_miss_must_be_output_even_when_current_opportunities_empty'] is True
    assert '接近买点榜' in manifest()['public_output']['sections']


def test_completion_gate_guards_research_depth_not_just_formal_sections():
    g = manifest()['completion_gate_contract']
    assert g['all_confirmed_improving_chains_company_screened'] is True
    assert g['no_research_admission_top_n_truncation'] is True
    assert g['all_light_screen_survivors_compared'] is True
    assert g['valuation_set_dedup_complete'] is True
    assert g['all_triggered_extreme_valuation_audits_pass_or_review'] is True
    assert g['all_complete_non_review_companies_have_buy_point_assessment'] is True
    assert g['current_opportunities_must_come_only_from_buyable_now'] is True
    assert g['near_miss_ranking_complete_when_eligible_universe_nonempty'] is True


def test_public_evidence_is_required_but_candidate_pools_remain_forbidden():
    m = manifest()
    assert m['evidence_contract']['current_public_research_evidence_required_for_1800_research'] is True
    assert m['persistence_contract']['persistent_intermediate_research_outputs_allowed'] is False
    assert m['persistence_contract']['cross_run_candidate_or_opportunity_caches_allowed'] is False


def test_incomplete_fails_closed():
    s = manifest()['research_state_contract']
    assert s['manifest_schema_must_equal_current'] is True
    assert s['on_incomplete'] == 'incomplete_research'
    assert s['incomplete_must_not_publish_new_current_opportunities'] is True
    assert 'company_light_screen' in s['required_top_level_sections']
    assert 'buy_point_assessments' in s['required_top_level_sections']


def test_core_earnings_quality_cannot_silently_pass_when_deducted_profit_missing():
    m = manifest()
    ls = m['company_comparison_contract']['company_light_screen']
    val = m['valuation_resolution_contract']
    assert ls['core_earnings_evidence_required_for_survive'] is True
    assert ls['deducted_netprofit_or_equivalent_core_earnings_must_be_checked'] is True
    assert ls['missing_core_earnings_evidence_cannot_default_to_earnings_quality_match_true'] is True
    assert ls['missing_core_earnings_requires_current_public_evidence_supplement_or_data_unavailable'] is True
    assert ls['nonrecurring_dominance_threshold_of_parent_netprofit'] == 0.30
    assert val['core_earnings_preferred_over_parent_netprofit_when_nonrecurring_dominant'] is True
    assert val['parent_netprofit_contaminated_by_material_nonrecurring_items_cannot_feed_forward_bridge'] is True
