from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_runtime_policy_enforces_manifest_only_reads_and_schema_match():
    policy = _load("config/research_runtime_policy.json")
    assert policy["pipeline"] == "a_share_low_risk_v2"
    assert policy["research_read_mode"] == "manifest_authoritative_only"
    assert policy["read_policy"]["allow_only_manifest_authoritative_data"] is True
    assert policy["read_policy"]["do_not_scan_data_research_for_helpful_json"] is True
    assert policy["state_compatibility"]["required_manifest_schema_match"] is True
    assert policy["state_compatibility"]["on_manifest_schema_mismatch"] == "stale_state_do_not_use_as_current"
    assert policy["write_policy"]["never_relabel_old_state_to_new_schema"] is True


def test_legacy_pipeline_outputs_are_not_present_in_active_tree():
    policy = _load("config/research_runtime_policy.json")
    for path in policy["forbidden_active_paths"]:
        assert not (ROOT / path).exists(), f"legacy research output path must stay absent: {path}"


def test_existing_research_state_must_match_current_manifest_schema():
    policy = _load("config/research_runtime_policy.json")
    manifest = _load(policy["manifest_path"])
    state_path = ROOT / policy["active_state_path"]
    if not state_path.exists():
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state.get("manifest_schema") == manifest.get("schema_version"), (
        "research_state is stale: manifest_schema must equal current manifest schema_version"
    )


def test_manifest_authoritative_data_does_not_reference_legacy_pipeline():
    manifest = _load("config/research_pipeline_manifest.json")
    authoritative = manifest["authoritative_data"]
    values = list(authoritative.values())
    assert all("data/research/pipeline" not in value for value in values)
