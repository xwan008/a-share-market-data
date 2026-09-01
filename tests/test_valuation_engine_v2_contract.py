import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def m(): return json.loads((ROOT/'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))
def r(): return json.loads((ROOT/'config/research_runtime_policy.json').read_text(encoding='utf-8'))

def test_schema31_valuation_engine_v2():
    v=m()['valuation_resolution_contract']
    assert m()['schema_version']==31
    assert v['valuation_engine_version']==2
    assert v['valuation_archetype_required'] is True
    assert v['sw_level1_alone_cannot_determine_valuation_archetype'] is True
    assert v['base_case_required'] and v['downside_case_required']
    assert v['base_fair_value_required'] and v['safe_price_ceiling_required']
    assert v['fixed_discount_from_reasonable_lower_bound_forbidden'] is True
    assert v['repeat_conservatism_across_earnings_multiple_and_mos_forbidden'] is True

def test_resource_and_cycle_models_are_not_fixed_pe_shortcuts():
    v=m()['valuation_resolution_contract']
    assert v['resource_asset_single_fixed_pe_forbidden'] is True
    assert v['resource_asset_requires_asset_or_cashflow_model'] is True
    assert v['spread_cyclical_requires_spread_or_margin_normalization'] is True
    assert 'nav_dcf' in v['archetype_model_contract']['resource_asset']['primary_methods']
    assert 'normalized_ev_ebitda' in v['archetype_model_contract']['spread_cyclical']['primary_methods']

def test_secondary_model_is_genuinely_independent():
    v=m()['valuation_resolution_contract']
    assert v['secondary_method_must_use_independent_value_driver_family'] is True
    assert v['same_earnings_basis_with_different_multiple_is_not_independent_method'] is True
    assert v['extreme_valuation_deviation_audit']['same_eps_different_pe_fails_independence_test'] is True

def test_safe_ceiling_replaces_double_discount_logic():
    b=m()['buy_point_contract']
    assert b['safe_price_ceiling_is_hard_value_boundary'] is True
    assert b['safe_price_range_lower_bound_is_not_hard_eligibility_floor'] is True
    assert b['buy_price_range_must_equal_structure_entry_range_capped_by_safe_price_ceiling'] is True

def test_near_miss_uses_action_distance_and_labels_far_names():
    n=m()['buy_point_contract']['near_miss_ranking_contract']
    assert n['ranking_version']==2
    assert n['action_distance_is_primary_metric'] is True
    assert n['near_threshold_pct']==5.0
    assert n['watch_threshold_pct']==15.0
    assert n['far_names_must_be_labeled_relative_closest_not_near'] is True
    assert n['avoid_excluded_from_primary_near_miss_ranking'] is True
    assert r()['stage_execution_policy']['same_eps_different_pe_is_not_independent_secondary_method'] is True
