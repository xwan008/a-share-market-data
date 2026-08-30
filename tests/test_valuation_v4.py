from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_legacy_weekly_low_pe_table_or_h1_times_two_formal_engine():
    text = (ROOT / 'scripts/build_forward_valuation.py').read_text(encoding='utf-8')
    assert 'WEEKLY_RANGES' not in text
    assert "fwd=e*2" not in text
    assert 'H1 EPS×2只能诊断' in text or 'H1×2只能诊断' in text


def test_weichai_and_luxshare_policy_regression_ranges():
    cfg = json.loads((ROOT / 'config/valuation_policy_registry.json').read_text(encoding='utf-8'))
    weichai = cfg['company_overrides']['000338']
    luxshare = cfg['company_overrides']['002475']

    assert weichai['multiple_range'] == [16, 20]
    assert luxshare['multiple_range'] == [20, 24]

    # Use current public consensus snapshots only as regression fixtures for policy geometry.
    weichai_eps = 1.67
    weichai_floor = weichai_eps * weichai['multiple_range'][0]
    weichai_reasonable = [weichai_floor * x for x in weichai['reasonable_to_fair_floor']]
    assert 23.0 <= weichai_reasonable[0] <= 24.5
    assert 26.0 <= weichai_reasonable[1] <= 27.5

    luxshare_eps = 2.96
    luxshare_floor = luxshare_eps * luxshare['multiple_range'][0]
    luxshare_reasonable = [luxshare_floor * x for x in luxshare['reasonable_to_fair_floor']]
    assert 51.5 <= luxshare_reasonable[0] <= 52.8
    assert 54.0 <= luxshare_reasonable[1] <= 55.0


def test_resource_cycle_policies_are_machine_executable():
    cfg = json.loads((ROOT / 'config/cycle_valuation_policy.json').read_text(encoding='utf-8'))
    copper = cfg['subchain_policies']['nonferrous::铜矿资源']
    aluminum = cfg['subchain_policies']['nonferrous::电解铝']
    zijin = cfg['company_overrides']['601899']

    assert any(x['symbol'] == 'CU0' for x in copper['anchors'])
    assert {x['symbol'] for x in aluminum['anchors']} == {'AL0', 'AO0'}
    assert {x['symbol'] for x in zijin['anchors']} == {'AU0', 'CU0'}
    assert sum(x['weight'] for x in zijin['anchors']) == 1.0


def test_manifest_requires_cycle_validator_and_merge():
    manifest = json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))
    stages = {s['id']: s for s in manifest['stages']}
    assert manifest['schema_version'] >= 4
    assert 'cycle-valuation' in stages['left_value_cycle']['validator']
    assert stages['left_value_merge']['requires'] == ['left_value_fundamental', 'left_value_cycle']
    assert 'left-valuation' in stages['left_value_merge']['validator']
