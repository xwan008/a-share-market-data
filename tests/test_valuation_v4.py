from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v2_manifest_is_shadow_and_uses_simplified_research_flow():
    manifest = json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))
    assert manifest['schema_version'] >= 10
    assert manifest['pipeline'] == 'a_share_low_risk_v2'
    assert manifest['mode'] == 'shadow'
    assert set(manifest['authoritative_skills']) == {
        'orchestrator',
        'earnings_driver_scan',
        'company_research',
        'price_expectation_gap',
        'opportunity_ranking',
    }
    stage_ids = [x['id'] for x in manifest['stages']]
    assert stage_ids == [
        'data_health',
        'earnings_driver_scan',
        'company_research',
        'full_market_price_structure',
        'price_expectation_gap',
        'opportunity_ranking',
    ]
    assert all('t1' not in x.lower() and 't2' not in x.lower() for x in stage_ids)


def test_v2_right_structure_is_independent_from_company_research():
    manifest = json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))
    stages = {s['id']: s for s in manifest['stages']}
    right = stages['full_market_price_structure']
    assert right['requires'] == ['data_health']
    assert right['universe'] == 'all_mainboard_codes_with_fresh_180d_history'
    assert 'company_research' not in right['requires']


def test_v2_valuation_rules_forbid_repeated_haircuts_and_require_sanity():
    manifest = json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))
    stage = next(s for s in manifest['stages'] if s['id'] == 'price_expectation_gap')
    rules = set(stage['hard_rules'])
    assert 'industry_or_driver_confidence_never_multiplies_into_value' in rules
    assert 'no_repeated_cycle_haircuts' in rules
    assert 'safe_zone_requires_independent_anchor_overlap' in rules
    assert 'valuation_divergence_blocks_formal_buy_zone' in rules
    assert 'implied_pe_pb_sanity_is_mandatory' in rules


def test_v2_golden_cases_cover_known_failure_modes():
    golden = json.loads((ROOT / 'config/low_risk_v2_golden_tests.json').read_text(encoding='utf-8'))
    values = {x['code']: x for x in golden['valuation_cases']}
    assert '600309' in values  # Wanhua: repeated-discount regression
    assert values['600309']['sanity']['reasonable_zone_should_not_imply_forward_pe_below'] >= 9
    assert '002460' in values  # Ganfeng: lithium anchor / over-discount regression
    assert values['002460']['required_anchor_hint'].startswith('LC0')
    rights = {x['code']: x for x in golden['right_structure_cases']}
    assert rights['601138']['must_be_scanned_even_if_not_in_company_research'] is True
    assert 'no_resistance_map' in rights['601138']['forbidden_rejection_reasons']


def test_v1_business_skills_are_not_authoritative_v2_skills():
    manifest = json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))
    deprecated = set(manifest['legacy_v1']['deprecated_business_skills'])
    assert {'industry-scan', 't2-company-recall', 'fundamental-valuation', 'cycle-valuation', 'technical-structure', 'final-selection'} <= deprecated
    for name in deprecated:
        assert not (ROOT / 'skills/a-share-low-risk' / name / 'SKILL.md').exists()
