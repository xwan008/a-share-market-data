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


cycle_mod = load_module('cycle_v5', 'scripts/build_cycle_valuation.py')
fund_mod = load_module('fund_v5', 'scripts/build_forward_valuation.py')
validator_mod = load_module('validator_v5', 'scripts/validate_research_outputs.py')


def test_calendar_forward_eps_uses_next_year_at_late_august():
    now = datetime(2026, 8, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
    value, current_weight, next_weight = cycle_mod.calendar_forward_eps(3.0, 4.0, now)
    assert round(current_weight, 4) == round(4 / 12, 4)
    assert round(next_weight, 4) == round(8 / 12, 4)
    assert round(value, 4) == round(3.0 * 4 / 12 + 4.0 * 8 / 12, 4)


def test_resource_consensus_is_normalized_when_commodity_windfall_is_positive():
    normalized, factor = cycle_mod.normalize_forward_eps(
        4.0,
        weighted_neutral_delta=0.25,
        sensitivity=0.8,
        neutral_policy={'min_normalization_factor': 0.70},
    )
    assert factor < 1.0
    assert normalized < 4.0


def test_weak_commodity_does_not_mechanically_raise_normalized_eps():
    normalized, factor = cycle_mod.normalize_forward_eps(
        4.0,
        weighted_neutral_delta=-0.20,
        sensitivity=0.8,
        neutral_policy={'min_normalization_factor': 0.70},
    )
    assert factor == 1.0
    assert normalized == 4.0


def test_180d_market_anchor_caps_low_risk_buy_zone_even_when_theoretical_fair_is_high():
    market_anchor = {
        'safe_percentile_band': [24.0, 28.0],
        'reasonable_percentile_band': [28.0, 34.0],
        'ma60': 30.0,
    }
    policy = {
        'safe_to_fair_floor': [0.76, 0.88],
        'reasonable_to_fair_floor': [0.88, 1.0],
    }
    market_policy = {
        'macro_uncertainty_haircut': 0.95,
        'max_reasonable_to_ma60': 1.06,
    }
    safe, reasonable, value_anchor, method = cycle_mod.calibrate_low_risk_buy_bands(
        fair_floor=44.0,
        market_anchor=market_anchor,
        policy=policy,
        market_policy=market_policy,
    )
    assert safe == [24.0, 28.0]
    assert reasonable == [28.0, 31.8]
    assert value_anchor == [24.0, 31.8]
    assert method == 'normalized_fundamental_plus_180d_market_calibration'


def test_aluminum_regime_requires_medium_term_normalization():
    regime = json.loads((ROOT / 'config/cycle_regime_registry.json').read_text(encoding='utf-8'))
    aluminum = regime['subchains']['nonferrous::电解铝']
    assert aluminum['regime'] == 'near_term_tight_medium_term_normalizing'
    assert aluminum['bear_base_bull_earnings_factor'][1] < 1.0
    assert aluminum['multiple_range_by_regime'][1] <= 11.0
    assert len(aluminum['evidence']) >= 2


def test_cycle_policy_requires_neutral_and_180d_low_risk_calibration():
    policy = json.loads((ROOT / 'config/cycle_valuation_policy.json').read_text(encoding='utf-8'))
    neutral = policy['neutral_commodity_policy']
    market = policy['low_risk_price_calibration']
    assert neutral['window_sessions'] >= 180
    assert neutral['minimum_sessions'] >= 120
    assert policy['short_term_anchor_policy']['positive_strength_can_raise_low_risk_buy_zone'] is False
    assert market['window_sessions'] == 180
    assert market['safe_percentiles'][1] <= market['reasonable_percentiles'][0]
    assert market['max_reasonable_to_ma60'] <= 1.10


def test_financial_pb_band_is_forward_roe_driven():
    policy = {
        'roe_pb_bands': [
            {'roe_max': 0.08, 'pb_range': [0.8, 1.0]},
            {'roe_max': 0.12, 'pb_range': [1.0, 1.3]},
            {'roe_max': 9.99, 'pb_range': [1.2, 1.6]},
        ]
    }
    assert fund_mod.choose_pb_band(policy, 0.07) == [0.8, 1.0]
    assert fund_mod.choose_pb_band(policy, 0.10) == [1.0, 1.3]
    assert fund_mod.choose_pb_band(policy, 0.18) == [1.2, 1.6]


def test_policy_audit_rejects_unsupported_policy():
    payload = {
        'common_pool_count': 2,
        'fundamental_count': 1,
        'cycle_count': 1,
        'coverage_count': 2,
        'missing_codes': [],
        'extra_codes': [],
        'noncycle_policy_coverage': {
            'noncycle_count': 1,
            'supported_policy_count': 0,
            'unsupported_policy_count': 1,
            'unsupported_policy_codes': ['000001'],
        },
        'hard_gate': {'status': 'FAIL'}
    }
    errors = validator_mod.validate_policy_audit(payload)
    assert any('unsupported_policy' in e for e in errors)
