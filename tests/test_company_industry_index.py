from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scripts.build_company_industry_index import (
    is_main_board,
    is_research_eligible_quote,
    is_stale,
    resolve_sw_levels,
)


def active_quote(trade_date: str, confidence: str = 'high') -> dict:
    return {
        'confidence': confidence,
        'source_dates': {'sina': trade_date, 'tencent': None},
        'open': 10.0,
        'high': 10.5,
        'low': 9.8,
        'volume': 1000,
    }


def test_main_board_filter():
    assert is_main_board('600000')
    assert is_main_board('002475')
    assert not is_main_board('300750')
    assert not is_main_board('688981')


def test_research_universe_excludes_invalid_stale_or_nontradable_quotes():
    trade_date = '2026-09-01'
    assert is_research_eligible_quote(active_quote(trade_date), trade_date)
    assert is_research_eligible_quote(active_quote(trade_date, 'medium'), trade_date)

    invalid = active_quote(trade_date)
    invalid['confidence'] = 'invalid'
    assert not is_research_eligible_quote(invalid, trade_date)

    stale = active_quote(trade_date)
    stale['source_dates'] = {'sina': '2025-09-04', 'tencent': None}
    assert not is_research_eligible_quote(stale, trade_date)

    frozen = active_quote(trade_date)
    frozen.update({'open': 0.0, 'high': 0.0, 'low': 0.0, 'volume': 0})
    assert not is_research_eligible_quote(frozen, trade_date)


def test_taxonomy_walk_resolves_all_three_levels():
    taxonomy = {
        'L1': {'code': 'L1', 'name': '电子', 'parent_code': None, 'level': 1},
        'L2': {'code': 'L2', 'name': '元件', 'parent_code': 'L1', 'level': 2},
        'L3': {'code': 'L3', 'name': '印制电路板', 'parent_code': 'L2', 'level': 3},
    }
    levels = resolve_sw_levels('L3', taxonomy)
    assert levels == {
        'sw_level1_code': 'L1', 'sw_level1_name': '电子',
        'sw_level2_code': 'L2', 'sw_level2_name': '元件',
        'sw_level3_code': 'L3', 'sw_level3_name': '印制电路板',
    }


def test_stale_policy_requires_complete_mapping_and_fresh_timestamp():
    tz = ZoneInfo('Asia/Shanghai')
    now = datetime(2026, 8, 30, 9, 0, tzinfo=tz)
    assert is_stale(None, now, 60)
    fresh = {'mapping_status': 'mapped', 'last_verified_at': (now - timedelta(days=10)).isoformat()}
    assert not is_stale(fresh, now, 60)
    assert is_stale({'mapping_status': 'unmapped', 'last_verified_at': now.isoformat()}, now, 60)
    assert is_stale({'mapping_status': 'mapped', 'last_verified_at': (now - timedelta(days=61)).isoformat()}, now, 60)
