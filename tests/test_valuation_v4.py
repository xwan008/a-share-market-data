from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    return json.loads(
        (ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8')
    )


def test_v2_manifest_is_shadow_and_uses_schema23_research_flow():
    manifest = _manifest()

    assert manifest['schema_version'] >= 23
    assert manifest['pipeline'] == 'a_share_low_risk_v2'
    assert manifest['mode'] == 'shadow'
    assert manifest['production_gate']['enabled'] is False

    assert set(manifest['authoritative_skills']) == {
        'orchestrator',
        'company_research',
        'valuation',
        'price_structure',
    }

    stage_ids = [stage['id'] for stage in manifest['stages']]
    assert stage_ids == [
        'data_health',
        'taxonomy_coverage',
        'market_profitability_discovery',
        'profit_chain_decomposition',
        'chain_company_comparison',
        'valuation',
        'price_structure',
        'opportunity_synthesis',
    ]


def test_v2_coverage_contract_is_fixed_and_blocks_incomplete_research():
    manifest = _manifest()
    research_contract = manifest['research_prompt_contract']
    coverage = manifest['coverage_contract']

    expected = {'level1': 31, 'level2': 134, 'level3': 346}
    assert research_contract['coverage_taxonomy'] == '申万行业分类标准2021版'
    assert research_contract['coverage_expected_counts'] == expected
    assert coverage['expected_counts'] == expected

    gates = coverage['completion_gate']
    assert any('31/134/346' in rule for rule in gates)
    assert any('missing_level1/missing_level2/missing_level3' in rule for rule in gates)
    assert any('must_split' in rule for rule in gates)
    assert 'incomplete_research' in coverage['failure_behavior']
    assert '不得生成新的当前机会' in coverage['failure_behavior']


def test_v2_profit_chain_resolution_requires_shared_economic_driver():
    manifest = _manifest()
    contract = manifest['profit_chain_resolution_contract']

    stop_rules = contract['stop_only_if']
    split_rules = contract['must_split_if']

    assert any('直接盈利Driver' in rule for rule in stop_rules)
    assert any('领先变量' in rule for rule in stop_rules)
    assert any('利润传导' in rule for rule in stop_rules)
    assert any('横向可比' in rule for rule in stop_rules)
    assert len(split_rules) >= 4
    assert '只是在公司名称层面做分类' in contract['anti_over_split']


def test_v2_price_structure_is_independent_from_company_research_and_valuation():
    manifest = _manifest()
    stages = {stage['id']: stage for stage in manifest['stages']}

    structure = stages['price_structure']
    assert structure['executor'] == 'code+prompt'
    assert 'requires' not in structure or 'chain_company_comparison' not in structure['requires']
    assert '只判断交易时机' in structure['purpose']
    assert '不进入内在价值计算' in structure['purpose']

    synthesis_requires = set(stages['opportunity_synthesis']['requires'])
    assert {'taxonomy_coverage', 'chain_company_comparison', 'valuation', 'price_structure'} <= synthesis_requires


def test_v2_valuation_keeps_market_price_separate_from_intrinsic_value():
    manifest = _manifest()
    output = manifest['valuation_output_contract']
    principles = manifest['valuation_principles']

    assert output['public_labels'] == {
        'current_price': '当前价格',
        'reasonable_price_range': '合理价格',
        'safe_price_range': '安全价格（低风险区）',
    }
    assert '当前价格与价格结构不得反向修改合理价格或安全价格。' in output['rules']
    assert '当前价格必须作为独立市场输入展示' in principles['bridge_required']
    assert '禁止直接资本化周期顶部利润' in principles['resource_or_strong_cycle']
    assert principles['unreliable'].endswith('review_required。')


def test_obsolete_v2_answer_files_are_explicitly_quarantined():
    manifest = _manifest()
    obsolete = set(manifest['obsolete_v2_inputs_and_outputs'])

    assert {
        'data/research/v2/earnings_driver_scan.json',
        'data/research/v2/price_expectation_gap.json',
        'data/research/v2/opportunity_ranking.json',
    } <= obsolete
