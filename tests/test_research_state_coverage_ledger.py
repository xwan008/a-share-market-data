import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_persisted_state_schema31_contract_when_present():
    state_path = ROOT / 'data/research/v2/research_state.json'
    if not state_path.exists():
        return

    state = json.loads(state_path.read_text(encoding='utf-8'))
    manifest = load('config/research_pipeline_manifest.json')
    taxonomy = load('config/industry_scan_universe.json')
    assert state['manifest_schema'] == manifest['schema_version'] == 32
    assert state['scan_mode'] in {'weekly_full', 'daily_incremental'}
    assert state['weekly_baseline_date']

    # Coverage is taxonomy routing only; prosperity/profitability state lives elsewhere.
    ledger = state['coverage_ledger']
    contract = manifest['coverage_contract']['ledger_contract']
    required = set(contract['required_node_fields'])
    level3_by_code = {}
    for level in ('level1', 'level2', 'level3'):
        expected = {node['code']: node for node in taxonomy['levels'][level]}
        rows = ledger[level]
        assert len(rows) == len(expected)
        by_code = {row['code']: row for row in rows}
        assert set(by_code) == set(expected)
        if level == 'level3': level3_by_code = by_code
        for code, row in by_code.items():
            assert required.issubset(row)
            assert row['name'] == expected[code]['name']
            assert row['parent_code'] == expected[code]['parent_code']
            assert row['level'] == level
            assert row['accounted_for'] is True
            assert row['routing_status'] in contract['allowed_routing_status']

    assert isinstance(state['market_prosperity_search'], (dict, list))
    verified = state['level3_profitability_verification']
    rows = list(verified.values()) if isinstance(verified, dict) else verified
    verified_by_code = {row['code']: row for row in rows}
    for row in rows:
        assert row['trend'] in {'improving','stable','deteriorating','unconfirmed'}
        assert row['evidence_basis']

    # All confirmed improving chains must reach company screening; no Top-N research admission.
    confirmed_improving = set()
    for chain in state['profit_chains']:
        if chain['resolution_status'] != 'resolved':
            continue
        src = chain['source_coverage_codes']
        if any(verified_by_code.get(code, {}).get('trend') == 'improving' for code in src):
            confirmed_improving.add(chain['chain_id'])

    screens = state['company_light_screen']
    assert isinstance(screens, dict)
    assert confirmed_improving.issubset(screens)
    for chain_id in confirmed_improving:
        screen = screens[chain_id]
        assert screen['screen_complete'] is True
        screened = screen['screened_companies']
        assert screened
        codes = [r['code'] for r in screened]
        assert len(codes) == len(set(codes))
        for row in screened:
            assert row['screen_decision'] in {'survive', 'exclude'}
            assert row['source_chain_ids']
            assert row['evidence_basis']
            if row['screen_decision'] == 'exclude':
                assert row['exclusion_reason'] in manifest['company_comparison_contract']['company_light_screen']['allowed_exclusion_reasons']
            else:
                assert row['exclusion_reason'] in {None, ''}

    comparisons = {x['chain_id']: x for x in state['chain_comparisons']}
    for chain_id in confirmed_improving:
        screen = screens[chain_id]
        survivors = {r['code'] for r in screen['screened_companies'] if r['screen_decision'] == 'survive'}
        comp = comparisons[chain_id]
        assert comp['comparison_complete'] is True
        assert set(comp['compared_companies']) == survivors

    diagnostics = state['diagnostics']
    company_diag = diagnostics['company_screen']
    assert company_diag['confirmed_improving_chain_count'] == len(confirmed_improving)
    assert company_diag['company_screened_chain_count'] == len(confirmed_improving)
    assert company_diag['unscreened_confirmed_improving_chains'] == []

    # Dedup only removes repeated valuation work, not source-chain memberships.
    valuation_set = state['valuation_set']
    assert len(valuation_set) == len(set(valuation_set))
    all_compared = {code for comp in state['chain_comparisons'] for code in comp['compared_companies']}
    assert set(valuation_set) == all_compared
    for code in valuation_set:
        company = state['companies'][code]
        assert company['source_chain_ids']

    # Valuation execution and extreme-deviation audit.
    valuations = state['valuations']
    assert set(valuation_set) == set(valuations)
    audit_cfg = manifest['valuation_resolution_contract']['extreme_valuation_deviation_audit']
    for code in valuation_set:
        v = valuations[code]
        assert v['valuation_attempt_complete'] is True
        assert v['current_share_count']
        assert v['share_count_basis']
        assert v['corporate_action_check']
        assert v['earnings_bridge_integrity']
        if not v.get('review_required', False):
            assert v['reasonable_price_range'] is not None
            assert v['safe_price_range'] is not None
            lo, hi = v['reasonable_price_range']
            px = v['current_price']
            extreme = lo >= px * audit_cfg['trigger_if_reasonable_lower_bound_is_at_least_multiple_of_current_price'] or px >= hi * audit_cfg['trigger_if_current_price_is_at_least_multiple_of_reasonable_upper_bound']
            if extreme:
                assert v['secondary_method']
                assert v['extreme_valuation_deviation_audit']['passed'] is True
        else:
            assert v['model_execution_status'] == 'blocked_after_full_attempt'
            assert v['review_exception_code'] in manifest['valuation_resolution_contract']['allowed_review_exception_codes']

    # Every non-review valuation must have an auditable buy-point assessment.
    assessments = state['buy_point_assessments']
    non_review = {code for code, v in valuations.items() if not v.get('review_required', False)}
    assert set(assessments) == non_review
    for code in non_review:
        a = assessments[code]
        assert a['buy_point_status'] in manifest['buy_point_contract']['allowed_buy_point_status']
        if a['buy_point_status'] == 'buyable_now':
            assert a['value_eligible'] is True
            assert a['timing_eligible'] is True
            assert a['buy_price_range'] is not None
            assert state['price_structures'][code]['structure_type'] not in {'damaged', 'overheated'}

    current_ops = state.get('current_opportunities', [])
    for op in current_ops:
        assert assessments[op['code']]['buy_point_status'] == 'buyable_now'

    vd = diagnostics['valuation']
    assert vd['valuation_set_count'] == len(valuation_set)
    assert vd['executed_count'] == len(valuation_set)
    assert vd['valuation_gate_passed'] is True
