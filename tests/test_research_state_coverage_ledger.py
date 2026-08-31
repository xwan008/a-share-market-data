import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_persisted_state_coverage_ledger_matches_taxonomy_when_present():
    # A valid persisted state must be a mechanically auditable projection of the taxonomy.
    state_path = ROOT / 'data/research/v2/research_state.json'
    if not state_path.exists():
        return

    state = json.loads(state_path.read_text(encoding='utf-8'))
    manifest = load('config/research_pipeline_manifest.json')
    taxonomy = load('config/industry_scan_universe.json')
    assert state['manifest_schema'] == manifest['schema_version']

    ledger = state['coverage_ledger']
    required = set(manifest['coverage_contract']['ledger_contract']['required_node_fields'])
    deep_statuses = set(manifest['coverage_contract']['ledger_contract']['deep_research_statuses'])

    for level in ('level1', 'level2', 'level3'):
        expected = {node['code']: node for node in taxonomy['levels'][level]}
        rows = ledger[level]
        assert len(rows) == len(expected)
        by_code = {row['code']: row for row in rows}
        assert set(by_code) == set(expected)
        for code, row in by_code.items():
            assert required.issubset(row)
            assert row['name'] == expected[code]['name']
            assert row['parent_code'] == expected[code]['parent_code']
            assert row['level'] == level
            assert row['accounted_for'] is True
            assert row['status']
            assert row['scan_depth']
            assert row['evidence_scope']
            assert row['evidence_basis']
            if row['status'] in deep_statuses:
                assert row['scan_depth'] == 'deep'
                assert row['needs_profit_chain_research'] is True
                assert row['profit_chain_resolution'] in {'resolved', 'unconfirmed_with_evidence_gap'}

    diagnostics = state['diagnostics']['coverage']
    assert diagnostics['accounted_for_counts'] == taxonomy['expected_counts']
    assert diagnostics['missing_level1'] == []
    assert diagnostics['missing_level2'] == []
    assert diagnostics['missing_level3'] == []
    assert diagnostics['accounted_for_counts']['level1'] is not None
    assert diagnostics['accounted_for_counts']['level2'] is not None
    assert diagnostics['accounted_for_counts']['level3'] is not None
