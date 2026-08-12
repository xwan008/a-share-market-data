import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_market import infer_trade_date, positive_number, source_is_fresh
from validate import normalize_quote_date, validate_price, validate_quote_fields

def test_high_confidence_when_sources_match():
    assert validate_price(primary_price=57.21, secondary_price=57.20).confidence == "high"

def test_medium_when_only_one_source():
    assert validate_price(primary_price=57.21, secondary_price=None).confidence == "medium"

def test_invalid_when_sources_conflict():
    assert validate_price(primary_price=57.21, secondary_price=58.0).confidence == "invalid"

def test_quote_consistency():
    assert "change_pct_inconsistent" not in validate_quote_fields({"price":57.21,"prev_close":55.63,"change_pct":2.84})

def test_positive_number():
    assert positive_number(0) is None and positive_number("57.21") == 57.21

def test_date_normalization_rejects_ambiguous_two_digit_year():
    assert normalize_quote_date("2026-08-12") == "2026-08-12"
    assert normalize_quote_date("20260812") == "2026-08-12"
    assert normalize_quote_date("06-08-12") is None

def test_trade_date_uses_valid_modal_date_across_sources():
    now = datetime(2026,8,12,12,0,tzinfo=ZoneInfo("Asia/Shanghai"))
    sina={"600000":{"date":"06-08-12"}}
    tencent={"600000":{"date":"2026-08-12"},"000001":{"date":"2026-08-12"}}
    assert infer_trade_date([sina,tencent], now) == "2026-08-12"

def test_source_freshness_requires_valid_date():
    assert source_is_fresh({"price":57.2,"date":"2026-08-12"}, "2026-08-12")
    assert not source_is_fresh({"price":57.2,"date":"06-08-12"}, "2026-08-12")
