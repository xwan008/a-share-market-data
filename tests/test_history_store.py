from scripts.history_store import ROLLING_DAYS, merge_rows, should_append_history


def test_history_accepts_completed_market_snapshots():
    assert should_append_history({"market_status": "closed"}) is True
    assert should_append_history({"market_status": "closed_or_no_trade"}) is True
    assert should_append_history({"market_status": "morning_closed"}) is False
    assert should_append_history({"market_status": "trading"}) is False
    assert should_append_history({}) is False


def test_merge_rows_overwrites_same_date_and_keeps_latest_window():
    existing = [
        {"date": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "close": float(i + 1)}
        for i in range(220)
    ]
    incoming = [
        {"date": "2026-08-28", "close": 999.0},
        {"date": "2026-08-29", "close": 1000.0},
    ]

    rows = merge_rows(existing, incoming)

    assert ROLLING_DAYS == 180
    assert len(rows) == ROLLING_DAYS
    assert rows[-1]["date"] == "2026-08-29"
    assert rows[-2]["date"] == "2026-08-28"
    assert rows[0]["date"] > existing[0]["date"]
