from datetime import datetime
from zoneinfo import ZoneInfo
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


cycle_mod = load_module('cycle_v4', 'scripts/build_cycle_valuation.py')


def test_calendar_forward_eps_weights_current_and_next_year():
    now = datetime(2026, 8, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
    value, current_weight, next_weight = cycle_mod.calendar_forward_eps(3.0, 4.0, now)
    assert round(current_weight, 4) == round(4 / 12, 4)
    assert round(next_weight, 4) == round(8 / 12, 4)
    assert round(value, 4) == round(3.0 * 4 / 12 + 4.0 * 8 / 12, 4)


def test_cycle_policy_has_machine_anchors_for_resource_chains():
    cfg = json.loads((ROOT / 'config/cycle_valuation_policy.json').read_text(encoding='utf-8'))
    copper = cfg['subchain_policies']['nonferrous::铜矿资源']
    aluminum = cfg['subchain_policies']['nonferrous::电解铝']
    zijin = cfg['company_overrides']['601899']
    assert any(x['symbol'] == 'CU0' for x in copper['anchors'])
    assert {x['symbol'] for x in aluminum['anchors']} == {'AL0', 'AO0'}
    assert {x['symbol'] for x in zijin['anchors']} == {'AU0', 'CU0'}
    assert sum(x['weight'] for x in zijin['anchors']) == 1.0


def test_manifest_requires_cycle_validator_audit_coverage_health_and_merge():
    manifest = json.loads((ROOT / 'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))
    stages = {s['id']: s for s in manifest['stages']}
    assert manifest['schema_version'] >= 8
    assert 'validate_cycle_valuation_v2.py' in stages['left_value_cycle']['validator']
    assert 'valuation_policy_audit' in stages
    assert 't2_valuation_coverage_health' in stages
    assert set(stages['left_value_merge']['requires']) == {
        'left_value_fundamental',
        'left_value_cycle',
        'valuation_policy_audit',
        't2_valuation_coverage_health',
    }
    assert 'left-valuation' in stages['left_value_merge']['validator']
