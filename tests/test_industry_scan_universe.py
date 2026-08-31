import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'industry_scan_universe.json'


def test_sw_taxonomy_is_exact_fixed_coverage_without_prefilled_profit_chains():
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    expected = {'level1': 31, 'level2': 134, 'level3': 346}
    assert cfg['schema_version'] >= 3
    assert cfg['taxonomy'] == '申万行业分类标准2021版'
    assert cfg['role'] == 'coverage_only_not_answer_pool'
    assert cfg['expected_counts'] == expected
    assert {key: len(rows) for key, rows in cfg['levels'].items()} == expected
    assert 'broad_industries' not in cfg
    text = CONFIG.read_text(encoding='utf-8')
    assert 'minimum_subchains' not in text


def test_taxonomy_nodes_have_unique_codes_and_valid_parent_links():
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    levels = cfg['levels']
    all_codes = {row['code'] for rows in levels.values() for row in rows}
    assert len(all_codes) == sum(len(rows) for rows in levels.values())
    for row in levels['level2'] + levels['level3']:
        assert row['parent_code'] in all_codes
