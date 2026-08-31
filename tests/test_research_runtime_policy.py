import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))


def test_repo_whitelist_and_public_evidence_are_separate_layers():
    p = load('config/research_runtime_policy.json')
    assert p['schema_version'] == 4
    assert p['research_read_mode'] == 'manifest_repo_data_plus_current_public_evidence'
    assert p['repository_data_policy']['allow_only_manifest_authoritative_data'] is True
    assert p['public_evidence_policy']['allowed'] is True
    assert p['public_evidence_policy']['required_for_1800_full_research'] is True
    assert p['public_evidence_policy']['not_subject_to_repository_file_whitelist'] is True


def test_ledger_first_stage_execution_is_enforced():
    p = load('config/research_runtime_policy.json')['stage_execution_policy']
    assert p['coverage_ledger_must_be_instantiated_before_market_discovery'] is True
    assert p['coverage_summary_cannot_substitute_for_node_ledger'] is True
    assert p['coverage_counts_must_be_derived_from_node_ledger'] is True
    assert p['grouped_direction_rows_cannot_account_for_multiple_taxonomy_nodes'] is True
    assert p['deep_status_nodes_must_be_resolved_before_completion_gate'] is True
    assert p['peer_comparison_must_finish_before_final_valuation_when_peers_exist'] is True
    assert p['publishable_opportunity_requires_complete_valuation_bridge'] is True


def test_no_cross_run_research_pool_and_state_schema_match():
    p = load('config/research_runtime_policy.json')
    m = load(p['manifest_path'])
    assert p['discovery_policy']['previous_state_may_not_seed_1800_discovery'] is True
    assert p['discovery_policy']['cross_run_candidate_or_opportunity_pools_forbidden'] is True
    assert p['write_policy']['persistent_intermediate_research_outputs_forbidden'] is True
    assert p['write_policy']['new_full_state_must_include_coverage_ledger'] is True
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
