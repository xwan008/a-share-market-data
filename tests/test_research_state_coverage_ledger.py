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


def test_research_state_file_is_forbidden():
    assert not (ROOT / "data/research/research_state.json").exists()


def test_runtime_has_no_active_formal_run_state():
    runtime = load("config/research_runtime_policy.json")
    manifest = load("config/research_pipeline_manifest.json")
    assert runtime["industry_state_path"] == "data/research/industry_state.json"
    assert "active_state_path" not in runtime
    assert runtime["repository_data_policy"]["research_state_file_forbidden"] is True
    assert "research_state" not in manifest["authoritative_data"]
    assert "research_state_path" not in manifest["persistence_contract"]
    assert manifest["persistence_contract"]["persistent_formal_run_state_forbidden"] is True


def test_every_formal_result_is_current_run_only():
    runtime = load("config/research_runtime_policy.json")
    manifest = load("config/research_pipeline_manifest.json")
    assert runtime["write_policy"]["research_run_outputs_are_not_persisted"] is True
    assert runtime["write_policy"]["published_leaderboard_is_current_run_only"] is True
    assert manifest["persistence_contract"]["run_company_chain_valuation_buy_outputs_are_ephemeral"] is True
    assert manifest["persistence_contract"]["published_leaderboard_is_current_run_only"] is True
    assert manifest["public_output"]["current_run_only"] is True


def test_runtime_does_not_read_legacy_v2_state():
    runtime = load("config/research_runtime_policy.json")
    manifest = load("config/research_pipeline_manifest.json")
    assert runtime["repository_data_policy"]["legacy_v2_research_files_are_not_runtime_input"] is True
    assert manifest["persistence_contract"]["old_v2_state_is_legacy_and_not_runtime_input"] is True
