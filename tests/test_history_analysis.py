from scripts.build_history import (
    build_stock_summary,
    history_quality,
    normalized_volume,
    price_density_zones,
    structure_zones,
    volume_profile_zones,
)


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


def test_intraday_history_may_end_on_prior_completed_session():
    rows = make_rows(65)
    from datetime import date, timedelta

    current_trade_date = (date.fromisoformat(rows[-1]["date"]) + timedelta(days=1)).isoformat()
    confidence, warnings = history_quality(
        rows,
        expected_trade_date=current_trade_date,
        last_full_refresh=f"{current_trade_date}T11:50:00+08:00",
        history_may_end_before_trade_date=True,
    )
    assert confidence == "high"
    assert warnings == []


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
    assert "volume_profile_zones" in summary["structure_60d"]
    assert summary["structure_60d"]["volume_profile_unit"] == "shares"
    assert summary["history_confidence"] == "high"


def test_structure_zones_return_bounded_lists():
    rows = make_rows(65)[-60:]
    supports, resistances = structure_zones(rows, rows[-1]["close"])
    assert len(supports) <= 3
    assert len(resistances) <= 3


def test_density_zones_capture_repeated_closes():
    rows = make_rows(65)[-60:]
    zones = price_density_zones(rows, rows[-1]["close"])
    assert len(zones) <= 5
    assert all(zone["closes"] >= 2 for zone in zones)


def test_volume_unit_normalization_handles_legacy_and_new_rows():
    legacy_qfq = {"volume": 1234, "basis": "qfq", "source": "tencent"}
    normalized_qfq = {
        "volume": 123400,
        "volume_unit": "shares",
        "basis": "qfq",
        "source": "tencent",
    }
    live = {"volume": 123400, "volume_unit": "shares", "basis": "live_close", "source": "sina"}
    assert normalized_volume(legacy_qfq) == 123400
    assert normalized_volume(normalized_qfq) == 123400
    assert normalized_volume(live) == 123400


def test_volume_profile_zones_are_bounded_and_weighted():
    rows = make_rows(65)[-60:]
    zones = volume_profile_zones(rows, rows[-1]["close"])
    assert len(zones) <= 5
    assert zones
    assert all(zone["volume_share_pct"] > 0 for zone in zones)
    assert all(zone["days"] >= 1 for zone in zones)
