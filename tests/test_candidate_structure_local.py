from scripts.build_candidate_structure_260d import dedupe_pressures, summary_status


def test_summary_status_requires_recent_full_year_summary():
    fresh = {"summary_data_date": "2026-08-28", "summary_window_sessions": 252}
    assert summary_status(fresh, "2026-08-28") == ("fresh", 0)

    stale = {"summary_data_date": "2026-08-01", "summary_window_sessions": 252}
    assert summary_status(stale, "2026-08-28")[0] == "stale"

    short = {"summary_data_date": "2026-08-28", "summary_window_sessions": 150}
    assert summary_status(short, "2026-08-28")[0] == "insufficient_window"


def test_pressure_dedup_keeps_nearest_level_and_source_trace():
    rows = [
        {"source": "daily_pivot_120d", "price": 100.0},
        {"source": "weekly_pivot_180d", "price": 100.1},
        {"source": "52week_high_summary", "price": 110.0},
    ]
    result = dedupe_pressures(rows)
    assert len(result) == 2
    assert result[0]["price"] == 100.0
    assert "weekly_pivot_180d" in result[0]["also_from"]
    assert result[1]["price"] == 110.0
