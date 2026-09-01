import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_market import completed_quarter_ends, parse_financial_row


def test_completed_quarter_ends_uses_latest_completed_reports():
    assert completed_quarter_ends(date(2026, 9, 1), count=2) == [
        "2026-06-30",
        "2026-03-31",
    ]
    assert completed_quarter_ends(date(2027, 1, 15), count=2) == [
        "2026-12-31",
        "2026-09-30",
    ]


def test_parse_financial_row_keeps_filter_fields():
    row = {
        "REPORTDATE": "2026-06-30 00:00:00",
        "NOTICE_DATE": "2026-08-20 00:00:00",
        "WEIGHTAVG_ROE": 12.3,
        "YSTZ": 18.5,
        "SJLTZ": 35.2,
        "KCFJCXSYJLRTZ": 31.8,
        "MGJYXJJE": 1.25,
        "XSMLL": 42.1,
        "TOTAL_OPERATE_INCOME": 1000000000,
        "PARENT_NETPROFIT": 120000000,
        "BASIC_EPS": 0.88,
        "DEDUCT_BASIC_EPS": 0.81,
    }

    parsed = parse_financial_row(row)

    assert parsed["report_date"] == "2026-06-30"
    assert parsed["notice_date"] == "2026-08-20"
    assert parsed["roe"] == 12.3
    assert parsed["revenue_yoy"] == 18.5
    assert parsed["net_profit_yoy"] == 35.2
    assert parsed["deduct_net_profit_yoy"] == 31.8
    assert parsed["operating_cashflow_per_share"] == 1.25
