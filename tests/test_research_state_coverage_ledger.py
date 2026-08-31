import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_persisted_state_schema27_contract_when_present():
    state_path = ROOT / 'data/research/v2/research_state.json'
    if not state_path.exists():
        return

    state = json.loads(state_path.read_text(encoding='utf-8'))
    manifest = load('config/research_pipeline_manifest.json')
    taxonomy = load('config/industry_scan_universe.json')
    assert state['manifest_schema'] == manifest['schema_version']
    assert state['scan_mode'] in {'weekly_full', 'daily_incremental'}
    assert state['weekly_baseline_date']

    ledger = state['coverage_ledger']
    contract = manifest['coverage_contract']['ledger_contract']
    required = set(contract['required_node_fields'])

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
            assert row['trend'] in contract['allowed_trend']
            assert row['strength'] in contract['allowed_strength']
            assert row['breadth'] in contract['allowed_breadth']
            assert row['confidence'] in contract['allowed_confidence']
            assert row['evidence_basis']
            must_deep = row['trend'] in {'improving', 'deteriorating'} or row['breadth'] in {'selective', 'divergent'}
            if must_deep:
                assert row['scan_depth'] == 'deep'
                assert row['needs_profit_chain_research'] is True
                assert row['profit_chain_resolution'] in {'resolved', 'unconfirmed_with_evidence_gap'}

    if state['scan_mode'] == 'weekly_full':
        for row in ledger['level3']:
            assert row['last_full_scan_date'] == state['weekly_baseline_date']
            assert row['evidence_scope'] != 'carried_forward'
            assert '本期已纳入全市场申万节点横截面检查' not in row['evidence_basis']
    else:
        for row in ledger['level3']:
            assert row['baseline_date'] == state['weekly_baseline_date']
            assert isinstance(row['daily_trigger'], bool)

    diagnostics = state['diagnostics']['coverage']
    assert diagnostics['accounted_for_counts'] == taxonomy['expected_counts']
    assert diagnostics['missing_level1'] == []
    assert diagnostics['missing_level2'] == []
    assert diagnostics['missing_level3'] == []
    assert diagnostics['profitability_discovery_gate_passed'] is True

    valuation_set = state['valuation_set']
    valuations = state['valuations']
    assert set(valuation_set) == set(valuations)
    for code in valuation_set:
        v = valuations[code]
        assert v['valuation_attempt_complete'] is True
        if not v.get('review_required', False):
            assert v['reasonable_price_range'] is not None
            assert v['safe_price_range'] is not None
            assert v['valuation_position'] not in {None, 'review_required'}
        else:
            assert v['model_execution_status'] == 'blocked_after_full_attempt'
            assert v['review_exception_code'] in manifest['valuation_resolution_contract']['allowed_review_exception_codes']

    vd = state['diagnostics']['valuation']
    assert vd['valuation_set_count'] == len(valuation_set)
    assert vd['executed_count'] == len(valuation_set)
    assert vd['valuation_gate_passed'] is True
