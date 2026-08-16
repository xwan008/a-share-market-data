from datetime import date, timedelta

from scripts.build_history import structure_evolution


def rows_from_closes(closes):
    start = date(2026, 1, 1)
    return [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": 1000,
        }
        for i, close in enumerate(closes)
    ]


def test_structure_evolution_detects_bullish_hh_hl_sequence():
    rows = rows_from_closes([10, 12, 11, 13, 12, 14, 13, 15, 14])
    result = structure_evolution(rows, rows[-1]["close"], pivot_window=1)

    assert result["trend_state"] == "bullish"
    assert result["break_state"] == "intact"
    assert result["latest_high"]["label"] == "HH"
    assert result["latest_low"]["label"] == "HL"
    assert result["invalidation"]["direction"] == "below"
    assert result["invalidation"]["price"] == 12.9


def test_structure_evolution_marks_unconfirmed_break_as_threat_only():
    rows = rows_from_closes([10, 12, 11, 13, 12, 14, 13, 15, 14, 12.5])
    result = structure_evolution(rows, rows[-1]["close"], pivot_window=1)

    assert result["trend_state"] == "bullish"
    assert result["break_state"] == "bullish_structure_under_threat"
    assert result["latest_low"]["price"] == 12.9


def test_structure_evolution_confirms_break_after_new_ll_is_confirmed():
    rows = rows_from_closes([10, 12, 11, 13, 12, 14, 13, 15, 12, 13])
    result = structure_evolution(rows, rows[-1]["close"], pivot_window=1)

    assert result["trend_state"] == "transition"
    assert result["break_state"] == "bullish_structure_break_confirmed"
    assert result["latest_low"]["label"] == "LL"


def test_structure_evolution_detects_bearish_lh_ll_sequence():
    rows = rows_from_closes([15, 13, 14, 12, 13, 11, 12, 10, 11])
    result = structure_evolution(rows, rows[-1]["close"], pivot_window=1)

    assert result["trend_state"] == "bearish"
    assert result["break_state"] == "intact"
    assert result["latest_high"]["label"] == "LH"
    assert result["latest_low"]["label"] == "LL"
    assert result["invalidation"]["direction"] == "above"
