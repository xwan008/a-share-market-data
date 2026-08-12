from scripts.history_store import ROLLING_DAYS, merge_rows, should_append_history


def test_history_only_accepts_closed_market():
    assert should_append_history({"market_status": "closed"}) is True
    assert should_append_history({"market_status": "morning_closed"}) is False
    assert should_append_history({"market_status": "trading"}) is False
    assert should_append_history({}) is False


def test_merge_rows_overwrites_same_date_and_keeps_latest_window():
    existing = [
        {"date": f"2026-06-{day:02d}", "close": float(day)}
        for day in range(1, 31)
    ] + [
        {"date": f"2026-07-{day:02d}", "close": float(day + 30)}
        for day in range(1, 31)
    ]
    incoming = [
        {"date": "2026-07-30", "close": 130.0},
        {"date": "2026-07-31", "close": 131.0},
        {"date": "2026-08-01", "close": 132.0},
        {"date": "2026-08-02", "close": 133.0},
        {"date": "2026-08-03", "close": 134.0},
        {"date": "2026-08-04", "close": 135.0},
    ]

    rows = merge_rows(existing, incoming)

    assert len(rows) == ROLLING_DAYS
    assert rows[-1]["date"] == "2026-08-04"
    assert next(row for row in rows if row["date"] == "2026-07-30")["close"] == 130.0
