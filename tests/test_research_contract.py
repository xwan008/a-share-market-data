import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))


def test_manifest_is_schema24_shadow_and_has_one_rule_owner_per_layer():
    m = manifest()
    assert m['schema_version'] == 24
    assert m['mode'] == 'shadow'
    assert m['production_gate']['enabled'] is False
    assert set(m['authoritative_skills']) == {'orchestrator', 'company_research', 'valuation', 'price_structure'}
    assert m['rule_ownership']['manifest'].startswith('只保存机器契约')


def test_stage_order_and_coverage_gate_are_fixed():
    m = manifest()
    assert m['stage_order'] == [
        'data_health', 'taxonomy_coverage', 'market_profitability_discovery',
        'profit_chain_decomposition', 'chain_company_comparison', 'valuation',
        'price_structure', 'completion_gate_and_opportunity_synthesis'
    ]
    assert m['coverage_contract']['expected_counts'] == {'level1': 31, 'level2': 134, 'level3': 346}
    gate = m['coverage_contract']['completion_gate']
    assert all(gate.values())


def test_incomplete_research_fails_closed_and_output_contract_is_stable():
    m = manifest()
    state = m['research_state_contract']
    assert state['manifest_schema_must_equal_current'] is True
    assert state['on_incomplete'] == 'incomplete_research'
    assert state['incomplete_must_not_publish_new_current_opportunities'] is True
    assert m['public_output']['sections'][-2:] == ['当前机会', '诊断']
    assert m['public_output']['company_columns'][:4] == ['公司', '当前价格', '合理价格', '安全价格（低风险区）']
