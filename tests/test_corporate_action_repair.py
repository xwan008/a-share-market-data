from scripts.repair_corporate_actions import (
    is_corporate_action_suspect,
    mismatch_ratio,
    previous_completed_row,
)


def test_previous_completed_row_ignores_current_trade_date():
    history = [
        {"date": "2026-08-10", "close": 10.0},
        {"date": "2026-08-11", "close": 10.2},
        {"date": "2026-08-12", "close": 10.3},
    ]
    row = previous_completed_row(history, "2026-08-12")
    assert row["date"] == "2026-08-11"
    assert row["close"] == 10.2


def test_small_rounding_difference_is_not_repair_signal():
    assert mismatch_ratio(10.0, 10.01) < 0.004
    assert is_corporate_action_suspect(10.0, 10.01) is False


def test_material_prev_close_reset_is_repair_signal():
    assert is_corporate_action_suspect(10.0, 9.5) is True
