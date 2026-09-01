import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_industry_state_is_compact_cross_run_baseline():
    state = load("data/research/industry_state.json")
    assert state["contract_id"] == "a-share-low-risk-production"
    assert state["status"] in {"requires_full_refresh", "valid"}
    assert "level3_profitability" in state
    assert "companies" not in state
    assert "valuations" not in state
    assert "near_miss_ranking" not in state
    assert "schema_version" not in state


def test_research_state_is_formal_production_state_not_schema_compatibility_container():
    state = load("data/research/research_state.json")
    assert state["contract_id"] == "a-share-low-risk-production"
    assert state["mode"] == "production"
    assert "manifest_schema" not in state
    assert "schema_version" not in state


def test_initial_state_cannot_be_published_until_first_complete_production_run():
    state = load("data/research/research_state.json")
    if state["status"] == "no_valid_formal_run_yet":
        assert state["publishable"] is False
        assert state["trade_date"] is None


def test_runtime_does_not_read_legacy_v2_state():
    runtime = load("config/research_runtime_policy.json")
    manifest = load("config/research_pipeline_manifest.json")
    assert runtime["active_state_path"] == "data/research/research_state.json"
    assert runtime["industry_state_path"] == "data/research/industry_state.json"
    assert manifest["persistence_contract"]["old_v2_state_is_legacy_and_not_runtime_input"] is True


def test_completed_formal_state_contract_when_present():
    state = load("data/research/research_state.json")
    if state.get("status") != "complete":
        return

    required = {
        "data_gate",
        "market_prosperity_search",
        "level3_profitability_verification",
        "profit_chains",
        "company_mapping_gate",
        "company_light_screen",
        "chain_comparisons",
        "valuation_set",
        "valuations",
        "price_structures",
        "buy_point_assessments",
        "near_miss_ranking",
        "current_opportunities",
        "diagnostics",
    }
    assert required.issubset(state)
    assert state["publishable"] is True
    assert state["data_gate"]["passed"] is True
    assert state["company_mapping_gate"]["passed"] is True
    assert state["diagnostics"]["completion_gate_passed"] is True

    assessments = state["buy_point_assessments"]
    for opportunity in state["current_opportunities"]:
        assert assessments[opportunity["code"]]["buy_point_status"] == "buyable_now"
