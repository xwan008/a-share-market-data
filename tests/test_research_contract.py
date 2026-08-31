import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))


def test_manifest_schema26_and_stage_order():
    m = manifest()
    assert m['schema_version'] == 26
    assert m['mode'] == 'shadow'
    assert m['stage_order'] == [
        'data_health', 'taxonomy_coverage', 'market_profitability_discovery',
        'profit_chain_decomposition', 'chain_company_comparison', 'valuation',
        'price_structure', 'completion_gate_and_opportunity_synthesis'
    ]
    assert m['coverage_contract']['expected_counts'] == {'level1': 31, 'level2': 134, 'level3': 346}


def test_coverage_ledger_is_first_class_and_auditable():
    c = manifest()['coverage_contract']['ledger_contract']
    assert c['instantiate_all_taxonomy_nodes_before_market_discovery'] is True
    assert c['exact_node_counts_must_match_taxonomy'] is True
    assert c['counts_must_be_derived_from_ledger_not_manually_asserted'] is True
    assert c['grouped_placeholder_rows_forbidden'] is True
    assert c['null_accounted_for_counts_forbidden'] is True
    assert c['missing_arrays_must_contain_actual_taxonomy_codes'] is True
    assert set(c['deep_research_statuses']) == {'strong_improving', 'improving', 'deteriorating', 'divergent'}


def test_deep_nodes_peer_comparison_and_valuation_have_resolution_contracts():
    m = manifest()
    chain = m['profit_chain_resolution_contract']
    comp = m['company_comparison_contract']
    val = m['valuation_resolution_contract']
    assert chain['required_for_each_deep_coverage_node'] is True
    assert chain['must_split_or_continue_split_cannot_remain_open'] is True
    assert comp['comparison_occurs_before_final_valuation'] is True
    assert comp['when_two_or_more_comparable_main_board_peers_exist_minimum_companies'] == 2
    assert comp['comparison_complete_required_when_peers_exist'] is True
    assert val['publishable_opportunity_requires_complete_bridge'] is True
    assert val['review_required_is_not_publishable_opportunity'] is True
    assert val['review_required_may_resolve_chain_as_no_current_opportunity_if_reason_is_explicit'] is True


def test_public_evidence_is_required_but_not_persisted_as_pool():
    m = manifest()
    e = m['evidence_contract']
    p = m['persistence_contract']
    assert e['repository_whitelist_applies_only_to_persistent_mechanical_data'] is True
    assert e['current_public_research_evidence_allowed'] is True
    assert e['current_public_research_evidence_required_for_1800_full_research'] is True
    assert p['persistent_intermediate_research_outputs_allowed'] is False
    assert p['cross_run_candidate_or_opportunity_caches_allowed'] is False


def test_incomplete_fails_closed():
    s = manifest()['research_state_contract']
    assert s['manifest_schema_must_equal_current'] is True
    assert s['on_incomplete'] == 'incomplete_research'
    assert s['incomplete_must_not_publish_new_current_opportunities'] is True
    assert 'coverage_ledger' in s['required_top_level_sections']
