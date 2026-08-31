import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))


def test_manifest_schema27_and_stage_order():
    m = manifest()
    assert m['schema_version'] == 27
    assert m['mode'] == 'shadow'
    assert m['stage_order'] == [
        'data_health', 'taxonomy_coverage', 'profitability_scan',
        'profit_chain_decomposition', 'chain_company_comparison', 'valuation',
        'price_structure', 'completion_gate_and_opportunity_synthesis'
    ]
    assert m['coverage_contract']['expected_counts'] == {'level1': 31, 'level2': 134, 'level3': 346}


def test_scan_cadence_is_weekly_full_plus_daily_incremental_not_weekly_pool():
    c = manifest()['scan_cadence_contract']
    assert c['full_scan_unit'] == 'level3'
    assert c['full_scan_expected_level3_nodes'] == 346
    assert c['weekly_full_scan_interval_days'] == 7
    assert c['daily_incremental_between_full_scans'] is True
    assert c['full_scan_is_market_state_baseline_not_candidate_pool'] is True
    assert c['daily_carry_forward_allowed_only_from_valid_weekly_baseline'] is True
    assert c['previous_companies_chains_or_opportunities_may_not_seed_discovery'] is True


def test_coverage_uses_four_dimensions_and_no_generic_weekly_placeholder():
    c = manifest()['coverage_contract']['ledger_contract']
    assert c['instantiate_all_taxonomy_nodes_before_profitability_scan'] is True
    assert set(c['allowed_trend']) == {'improving', 'stable', 'deteriorating', 'unconfirmed'}
    assert set(c['allowed_strength']) == {'strong', 'normal', 'weak', 'unknown'}
    assert set(c['allowed_breadth']) == {'broad', 'selective', 'divergent', 'unknown'}
    assert set(c['allowed_confidence']) == {'high', 'medium', 'low'}
    assert c['weekly_level3_generic_unconfirmed_placeholder_forbidden'] is True
    assert c['weekly_level3_each_node_requires_real_evidence_review'] is True
    assert c['counts_must_be_derived_from_ledger_not_manually_asserted'] is True


def test_profitability_discovery_gate_is_explicit():
    g = manifest()['coverage_contract']['profitability_discovery_gate']
    assert g['weekly_full_scan_requires_all_346_level3_reviewed'] is True
    assert g['daily_incremental_requires_valid_baseline_not_older_than_days'] == 7
    assert g['daily_incremental_requires_trigger_check_or_explicit_carry_forward_for_every_level3'] is True


def test_all_compared_companies_must_be_valued_and_review_is_not_escape_hatch():
    m = manifest()
    comp = m['company_comparison_contract']
    val = m['valuation_resolution_contract']
    assert comp['all_actually_compared_companies_enter_valuation_set'] is True
    assert val['every_valuation_set_company_requires_full_execution'] is True
    assert val['non_review_company_requires_non_null_reasonable_and_safe_ranges'] is True
    assert val['missing_analyst_consensus_is_not_valid_review_reason'] is True
    assert val['must_build_internal_forward_or_normalized_range_when_consensus_missing'] is True
    assert val['review_required_is_exception_not_successful_valuation'] is True
    assert val['review_required_requires_completed_research_attempt_and_blocker_evidence'] is True
    assert val['important_chain_opportunity_resolution_requires_at_least_one_complete_non_review_valuation'] is True


def test_public_evidence_is_required_but_candidate_pools_remain_forbidden():
    m = manifest()
    e = m['evidence_contract']
    p = m['persistence_contract']
    assert e['repository_whitelist_applies_only_to_persistent_mechanical_data'] is True
    assert e['current_public_research_evidence_allowed'] is True
    assert e['current_public_research_evidence_required_for_1800_research'] is True
    assert p['persistent_intermediate_research_outputs_allowed'] is False
    assert p['cross_run_candidate_or_opportunity_caches_allowed'] is False
    assert p['weekly_profitability_baseline_is_allowed_only_inside_research_state'] is True


def test_incomplete_fails_closed():
    s = manifest()['research_state_contract']
    assert s['manifest_schema_must_equal_current'] is True
    assert s['on_incomplete'] == 'incomplete_research'
    assert s['incomplete_must_not_publish_new_current_opportunities'] is True
    assert 'valuation_set' in s['required_top_level_sections']
    assert 'scan_mode' in s['required_run_fields']
