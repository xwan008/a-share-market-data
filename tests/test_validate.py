import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_market import infer_trade_date, positive_number
from validate import validate_price, validate_quote_fields


def test_high_confidence_when_sources_match():
    r = validate_price(primary_price=57.21, secondary_price=57.20)
    assert r.ok
    assert r.confidence == "high"


def test_medium_when_only_one_source():
    r = validate_price(primary_price=57.21, secondary_price=None)
    assert r.ok
    assert r.confidence == "medium"


def test_invalid_when_sources_conflict():
    r = validate_price(primary_price=57.21, secondary_price=58.0)
    assert not r.ok
    assert r.confidence == "invalid"


def test_quote_consistency():
    warnings = validate_quote_fields({"price": 57.21, "prev_close": 55.63, "change_pct": 2.84})
    assert "change_pct_inconsistent" not in warnings


def test_zero_primary_can_fall_back_to_secondary_source():
    assert positive_number(0) is None
    assert positive_number("57.21") == 57.21


def test_trade_date_uses_modal_sina_quote_date():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    quotes = {
        "600000": {"date": "2026-09-30"},
        "000001": {"date": "2026-09-30"},
        "002475": {"date": "2026-09-29"},
    }
    assert infer_trade_date(quotes, now) == "2026-09-30"
