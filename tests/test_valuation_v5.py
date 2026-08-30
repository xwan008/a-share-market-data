from datetime import datetime
from zoneinfo import ZoneInfo
import json
from pathlib import Path

from scripts.build_cycle_valuation import calendar_forward_eps
from scripts.build_forward_valuation import choose_pb_band
from scripts.validate_research_outputs import validate_policy_audit

ROOT = Path(__file__).resolve().parents[1]


def test_calendar_forward_eps_uses_next_year_at_late_august():
    now = datetime(2026, 8, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
    value, current_weight, next_weight = calendar_forward_eps(3.0, 4.0, now)
    assert round(current_weight, 4) == round(4 / 12, 4)
    assert round(next_weight, 4) == round(8 / 12, 4)
    assert round(value, 4) == round(3.0 * 4 / 12 + 4.0 * 8 / 12, 4)


def test_financial_pb_band_is_forward_roe_driven():
    policy = {
        'roe_pb_bands': [
            {'roe_max': 0.08, 'pb_range': [0.8, 1.0]},
            {'roe_max': 0.12, 'pb_range': [1.0, 1.3]},
            {'roe_max': 9.99, 'pb_range': [1.2, 1.6]},
        ]
    }
    assert choose_pb_band(policy, 0.07) == [0.8, 1.0]
    assert choose_pb_band(policy, 0.10) == [1.0, 1.3]
    assert choose_pb_band(policy, 0.18) == [1.2, 1.6]


def test_aluminum_regime_requires_medium_term_normalization():
    regime = json.loads((ROOT / 'config/cycle_regime_registry.json').read_text(encoding='utf-8'))
    aluminum = regime['subchains']['nonferrous::电解铝']
    assert aluminum['regime'] == 'near_term_tight_medium_term_normalizing'
    assert aluminum['bear_base_bull_earnings_factor'][1] < 1.0
    assert aluminum['multiple_range_by_regime'][1] <= 11.0
    assert len(aluminum['evidence']) >= 2


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
    errors = validate_policy_audit(payload)
    assert any('unsupported_policy' in e for e in errors)
