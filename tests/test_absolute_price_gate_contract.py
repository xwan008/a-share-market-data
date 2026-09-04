import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_absolute_price_gate_is_declared_consistently():
    policy = load_json("config/research_runtime_policy.json")["stage_execution_policy"]
    manifest = load_json("config/research_pipeline_manifest.json")
    admission = manifest["company_admission_contract"]
    completion = manifest["completion_gate_contract"]
    orchestrator = (ROOT / "skills/a-share-low-risk/orchestrator/SKILL.md").read_text(encoding="utf-8")

    assert policy["absolute_current_price_cap_cny"] == 100.0
    assert policy["absolute_current_price_cap_inclusive"] is True
    assert policy["absolute_price_gate_must_run_after_company_mapping_and_before_gate1"] is True
    assert policy["current_price_above_cap_exclusion_reason"] == "price_above_100"
    assert policy["every_mapped_eligible_company_requires_absolute_price_gate_decision"] is True

    assert admission["absolute_current_price_cap_cny"] == 100.0
    assert admission["absolute_current_price_cap_inclusive"] is True
    assert admission["price_cap_applies_after_mapping_and_before_gate1"] is True
    assert admission["price_cap_exclusion_formula"] == "current_price > 100"
    assert admission["price_cap_exclusion_reason"] == "price_above_100"

    assert completion["all_mapped_eligible_companies_have_absolute_price_gate_decision"] is True
    assert completion["gate1_inputs_satisfy_current_price_lte_100"] is True

    assert "`current_price > 100` → `exclude:price_above_100`" in orchestrator
    assert "`current_price <= 100` → 通过绝对股价硬门，进入Gate1" in orchestrator
