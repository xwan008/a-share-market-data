import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_market_resilient import normalize_easyquotation_timestamp


def test_tencent_datetime_is_split_into_date_and_time():
    quote_date, quote_time = normalize_easyquotation_timestamp(
        {"datetime": datetime(2026, 9, 3, 15, 0, 1)}
    )
    assert quote_date == "2026-09-03"
    assert quote_time == "15:00:01"


def test_native_date_and_time_take_precedence():
    quote_date, quote_time = normalize_easyquotation_timestamp(
        {
            "date": "2026-09-03",
            "time": "15:00:00",
            "datetime": datetime(2026, 9, 2, 15, 0, 0),
        }
    )
    assert quote_date == "2026-09-03"
    assert quote_time == "15:00:00"
