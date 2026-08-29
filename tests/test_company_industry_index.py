from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scripts.build_company_industry_index import is_main_board, is_stale, level1_from_code


def test_main_board_filter():
    assert is_main_board("600000")
    assert is_main_board("002475")
    assert not is_main_board("300750")
    assert not is_main_board("688981")


def test_taxonomy_walk_finds_level1_parent():
    taxonomy = {
        "801000": {"name": "电子", "parent": "", "level": 1},
        "801080": {"name": "电子元件", "parent": "801000", "level": 2},
        "801081": {"name": "连接器", "parent": "801080", "level": 3},
    }
    assert level1_from_code("801081", taxonomy) == ("801000", "电子")


def test_stale_policy():
    tz = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 8, 30, 9, 0, tzinfo=tz)
    assert is_stale(None, now, 60)
    assert not is_stale({"last_verified_at": (now - timedelta(days=10)).isoformat()}, now, 60)
    assert is_stale({"last_verified_at": (now - timedelta(days=61)).isoformat()}, now, 60)
