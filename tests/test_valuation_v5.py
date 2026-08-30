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


def test_financial_next_year_upside_cannot_raise_low_risk_roe():
    roe, method = fund_mod.choose_low_risk_forward_roe(0.10, 0.14)
    assert roe == 0.10
    assert method == 'current_year_primary_no_positive_next_year_uplift'


def test_financial_next_year_downside_can_lower_low_risk_roe():
    roe, method = fund_mod.choose_low_risk_forward_roe(0.10, 0.07)
    assert roe == 0.07
    assert method == 'next_year_downside_guard'


def test_low_risk_pe_growth_guardrail_cuts_high_industry_floor_when_growth_is_weak():
    policies = {
        'low_risk_pe_policy': {
            'growth_floor_caps': [
                {'growth_max_pct': 0, 'pe_floor_cap': 13},
                {'growth_max_pct': 20, 'pe_floor_cap': 18},
                {'growth_max_pct': 1000000, 'pe_floor_cap': 24},
            ],
            'derived_range_width': 4,
        }
    }
    low_risk, theoretical, cap, method = fund_mod.choose_low_risk_pe_range(
        {'multiple_range': [18, 25]}, -12.76, policies
    )
    assert theoretical == [18.0, 25.0]
    assert cap == 13.0
    assert low_risk == [13.0, 17.0]
    assert method == 'growth_guarded_low_risk_pe'


def test_company_explicit_low_risk_pe_overrides_theoretical_industry_pe():
    policies = {'low_risk_pe_policy': {'growth_floor_caps': [], 'derived_range_width': 4}}
    low_risk, theoretical, cap, method = fund_mod.choose_low_risk_pe_range(
        {'multiple_range': [20, 28], 'low_risk_multiple_range': [12, 16]}, 14.9, policies
    )
    assert theoretical == [20.0, 28.0]
    assert low_risk == [12.0, 16.0]
    assert cap is None
    assert method == 'company_explicit_low_risk_pe'


def test_focus_company_low_risk_ranges_match_2026_eps_framework():
    cfg = json.loads((ROOT / 'config/valuation_policy_registry.json').read_text(encoding='utf-8'))
    default_band = cfg['default_buy_band']
    cases = {
        '002452': (0.8975, [9.0, 10.6], [10.4, 11.8]),
        '002709': (3.2101, [29.8, 34.9], [34.4, 38.8]),
        '600710': (1.1222, [8.6, 10.3], [9.9, 11.4]),
        '603659': (1.5192, [19.9, 23.5], [23.0, 26.1]),
    }
    for code, (eps_2026, safe_expected, reasonable_expected) in cases.items():
        policy = cfg['company_overrides'][code]
        low_risk, _, _, _ = fund_mod.choose_low_risk_pe_range(policy, None, cfg)
        fair_floor = eps_2026 * low_risk[0]
        safe, reasonable, _ = fund_mod.zone(9999.0, fair_floor, policy, default_band)
        assert safe_expected[0] <= safe[0] <= safe_expected[1]
        assert safe_expected[0] <= safe[1] <= safe_expected[1]
        assert reasonable_expected[0] <= reasonable[0] <= reasonable_expected[1]
        assert reasonable_expected[0] <= reasonable[1] <= reasonable_expected[1]


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
