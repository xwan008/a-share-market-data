from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_cycle_valuation_has_machine_and_anchorless_routes() -> None:
    valuation = read("skills/a-share-low-risk/valuation/SKILL.md")
    orchestrator = read("skills/a-share-low-risk/orchestrator/SKILL.md")

    for text in (valuation, orchestrator):
        assert "machine_commodity_anchor" in text
        assert "conservative_anchorless_cycle" in text
        assert "valuation_incomplete:missing_cycle_inputs" in text

    # Missing a single machine futures anchor must not be a terminal exclusion anymore.
    assert "missing_cycle_anchor" in valuation
    assert "不再是强周期公司退出估值集的充分条件" in valuation
    assert "missing_cycle_anchor" in orchestrator
    assert "静默淘汰" in orchestrator


def test_market_refresh_builds_commodity_health_before_runtime_snapshot() -> None:
    workflow = read(".github/workflows/update-market.yml")
    collector = workflow.index("python scripts/fetch_commodity_anchors.py")
    bridge = workflow.index("python scripts/build_bridge.py")
    assert collector < bridge
    assert "data/commodity/futures_daily.json" in workflow


def test_runtime_snapshot_carries_raw_commodity_audit_data() -> None:
    workflow = read(".github/workflows/runtime-snapshot.yml")
    assert "data/commodity/futures_daily.json" in workflow
    assert "commodity_anchor_status" in workflow
    assert "commodity_reference_trade_date" in workflow
