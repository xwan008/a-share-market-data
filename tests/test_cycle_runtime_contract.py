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


def test_market_refresh_builds_commodity_health_before_locked_snapshot_dispatch() -> None:
    workflow = read(".github/workflows/update-market.yml")
    collector = workflow.index("python scripts/fetch_commodity_anchors.py")
    bridge = workflow.index("python scripts/build_bridge.py")
    dispatch = workflow.index(
        "bash scripts/dispatch_workflow_and_wait.sh runtime-snapshot.yml main"
    )
    assert collector < bridge < dispatch


def test_runtime_snapshot_carries_raw_commodity_audit_data() -> None:
    workflow = read(".github/workflows/runtime-snapshot.yml")
    assert "actions/upload-artifact@v4" in workflow
    assert "name: a-share-runtime-snapshot" in workflow
    assert "runtime_snapshot_manifest.json" in workflow
    assert "data/commodity/futures_daily.json" in workflow
    assert "commodity_anchor_status" in workflow
    assert "commodity_reference_trade_date" in workflow
