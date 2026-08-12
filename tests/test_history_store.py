from scripts.history_store import merge_rows, should_append_history


def test_history_only_accepts_closed_market():
    assert should_append_history({"market_status": "closed"}) is True
    assert should_append_history({"market_status": "morning_closed"}) is False
    assert should_append_history({"market_status": "trading"}) is False
    assert should_append_history({}) is False


def test_merge_rows_overwrites_same_date_and_keeps_latest_25():
    existing = [
        {"date": f"2026-07-{day:02d}", "close": float(day)}
        for day in range(1, 26)
    ]
    incoming = [
        {"date": "2026-07-25", "close": 125.0},
        {"date": "2026-07-26", "close": 126.0},
    ]

    rows = merge_rows(existing, incoming, limit=25)

    assert len(rows) == 25
    assert rows[0]["date"] == "2026-07-02"
    assert rows[-1] == {"date": "2026-07-26", "close": 126.0}
    assert next(row for row in rows if row["date"] == "2026-07-25")["close"] == 125.0
