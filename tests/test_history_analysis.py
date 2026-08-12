from scripts.build_history import build_stock_summary, history_quality, structure_zones


def make_rows(n=65):
    from datetime import date, timedelta

    rows = []
    start = date(2026, 5, 1)
    for i in range(n):
        base = 50 + i * 0.1
        if i in {20, 30, 40, 50}:
            low = 55.0
            close = 56.0
        else:
            low = base - 1.0
            close = base
        rows.append(
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "open": close - 0.2,
                "high": close + 1.0,
                "low": low,
                "close": close,
                "volume": 1000 + i,
                "basis": "qfq",
                "source": "tencent",
            }
        )
    return rows


def test_history_quality_requires_60_points_for_high():
    rows = make_rows(65)
    confidence, warnings = history_quality(
        rows,
        expected_trade_date=rows[-1]["date"],
        last_full_refresh=f"{rows[-1]['date']}T16:00:00+08:00",
    )
    assert confidence == "high"
    assert warnings == []

    confidence2, warnings2 = history_quality(
        rows[-20:],
        expected_trade_date=rows[-1]["date"],
        last_full_refresh=f"{rows[-1]['date']}T16:00:00+08:00",
    )
    assert confidence2 == "medium"
    assert "fewer_than_60_points" in warnings2


def test_build_summary_contains_60d_structure():
    rows = make_rows(65)
    item = {
        "history_basis": "tencent_qfq",
        "last_full_refresh": f"{rows[-1]['date']}T16:00:00+08:00",
        "history": rows,
    }
    summary = build_stock_summary(item, expected_trade_date=rows[-1]["date"])
    assert summary is not None
    assert summary["points"] == 65
    assert summary["structure_60d"]["points"] == 60
    assert summary["structure_60d"]["ma20"] > 0
    assert summary["history_confidence"] == "high"


def test_structure_zones_return_bounded_lists():
    rows = make_rows(65)[-60:]
    supports, resistances = structure_zones(rows, rows[-1]["close"])
    assert len(supports) <= 3
    assert len(resistances) <= 3
