from __future__ import annotations

from scripts.fetch_commodity_anchors import (
    MINIMUM_NEUTRAL_SESSIONS,
    percentile,
    summarize_rows,
)


def make_rows(count: int, start: float = 100.0) -> list[dict]:
    # Dates only need to be valid and ordered for the summary test; use one year of
    # consecutive calendar dates so freshness semantics are deterministic.
    from datetime import date, timedelta

    first = date(2025, 12, 1)
    return [
        {
            "date": (first + timedelta(days=i)).isoformat(),
            "close": start + i,
        }
        for i in range(count)
    ]


def test_percentile_interpolates() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5


def test_summarize_rows_builds_neutral_and_trend_metrics() -> None:
    rows = make_rows(MINIMUM_NEUTRAL_SESSIONS)
    summary = summarize_rows(rows, rows[-1]["date"])
    assert summary["history_points"] == MINIMUM_NEUTRAL_SESSIONS
    assert summary["age_days"] == 0
    assert summary["current"] == rows[-1]["close"]
    assert summary["ma20"] > summary["ma60"]
    assert summary["current_to_neutral"] > 1.0


def test_summarize_rows_rejects_short_history() -> None:
    rows = make_rows(MINIMUM_NEUTRAL_SESSIONS - 1)
    try:
        summarize_rows(rows, rows[-1]["date"])
    except RuntimeError as exc:
        assert "insufficient_futures_history" in str(exc)
    else:
        raise AssertionError("short futures history must fail")
