import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))


def test_repo_whitelist_and_public_evidence_are_separate_layers():
    p = load('config/research_runtime_policy.json')
    assert p['schema_version'] == 5
    assert p['research_read_mode'] == 'manifest_repo_data_plus_current_public_evidence'
    assert p['repository_data_policy']['allow_only_manifest_authoritative_data'] is True
    assert p['public_evidence_policy']['allowed'] is True
    assert p['public_evidence_policy']['required_for_1800_research'] is True
    assert p['public_evidence_policy']['not_subject_to_repository_file_whitelist'] is True


def test_weekly_baseline_and_daily_incremental_are_enforced():
    p = load('config/research_runtime_policy.json')
    d = p['discovery_policy']
    s = p['stage_execution_policy']
    assert d['weekly_industry_baseline_may_carry_forward_between_full_scans'] is True
    assert d['previous_state_may_seed_only_industry_baseline_for_daily_incremental'] is True
    assert d['previous_companies_chains_valuations_or_opportunities_may_not_seed_1800_discovery'] is True
    assert d['cross_run_candidate_or_opportunity_pools_forbidden'] is True
    assert s['weekly_full_scan_must_review_all_level3_nodes'] is True
    assert s['daily_incremental_requires_valid_weekly_baseline'] is True
    assert s['generic_weekly_unconfirmed_placeholders_forbidden'] is True
    assert s['deep_trigger_uses_trend_and_breadth_dimensions'] is True


def test_company_comparison_and_valuation_cannot_shortcut():
    s = load('config/research_runtime_policy.json')['stage_execution_policy']
    assert s['peer_comparison_must_finish_before_valuation_when_peers_exist'] is True
    assert s['all_compared_companies_must_enter_valuation_set'] is True
    assert s['every_valuation_set_company_must_be_executed'] is True
    assert s['review_required_is_exception_not_completion_shortcut'] is True
    assert s['important_chain_requires_non_review_complete_valuation'] is True
    assert s['publishable_opportunity_requires_complete_valuation_bridge'] is True


def test_state_schema_match_when_present():
    p = load('config/research_runtime_policy.json')
    m = load(p['manifest_path'])
    assert p['write_policy']['persistent_intermediate_research_outputs_forbidden'] is True
    assert p['write_policy']['weekly_baseline_must_live_inside_research_state'] is True
    assert p['write_policy']['new_state_must_include_coverage_ledger_and_scan_mode'] is True
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
