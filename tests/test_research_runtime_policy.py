import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_runtime_policy_enforces_manifest_only_reads_and_schema_match():
    policy = load('config/research_runtime_policy.json')
    assert policy['research_read_mode'] == 'manifest_authoritative_only'
    assert policy['read_policy']['allow_only_manifest_authoritative_data'] is True
    assert policy['state_compatibility']['required_manifest_schema_match'] is True
    assert policy['state_compatibility']['on_manifest_schema_mismatch'] == 'stale_state_do_not_use_as_current'
    assert policy['write_policy']['never_relabel_old_state_to_new_schema'] is True


def test_forbidden_legacy_research_paths_stay_absent():
    policy = load('config/research_runtime_policy.json')
    for path in policy['forbidden_active_paths']:
        assert not (ROOT / path).exists(), path


def test_existing_research_state_matches_current_manifest_schema():
    policy = load('config/research_runtime_policy.json')
    manifest = load(policy['manifest_path'])
    state_path = ROOT / policy['active_state_path']
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        assert state.get('manifest_schema') == manifest.get('schema_version')


def test_manifest_authoritative_data_is_small_and_explicit():
    manifest = load('config/research_pipeline_manifest.json')
    assert set(manifest['authoritative_data']) == {
        'industry_coverage_taxonomy', 'company_index', 'full_market_price_structure',
        'latest_market', 'bounded_history_store', 'research_state'
    }
