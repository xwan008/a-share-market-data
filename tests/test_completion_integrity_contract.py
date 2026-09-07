import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_research_completion.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("completion_validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_ledger():
    return {
        "repo_commit_sha": "a" * 40,
        "scan_source": "github_actions_runtime_snapshot",
        "shard_file_count": 513,
        "actual_shard_content_read_count": 513,
        "level1_total_count": 31,
        "level1_terminal_count": 31,
        "improving_level1_count": 4,
        "improving_level1_drilled_count": 4,
        "admitted_level3_count": 9,
        "admitted_level3_industry_state_applied_count": 9,
        "company_universe_count": 3177,
        "company_industry_terminal_count": 3177,
        "mapped_eligible_count": 120,
        "absolute_price_gate_terminal_count": 120,
        "price_gate_pass_count": 104,
        "gate1_terminal_count": 104,
        "gate1_pass_count": 70,
        "gate2_terminal_count": 70,
        "gate2_pass_count": 25,
        "gate3_terminal_count": 25,
        "gate3_pass_count": 8,
        "gate4_terminal_count": 8,
        "gate4_pass_count": 6,
        "valuation_terminal_count": 6,
        "valuation_complete_count": 5,
        "valuation_incomplete_count": 1,
        "formal_valuation_count": 4,
        "review_count": 1,
        "price_structure_terminal_count": 4,
        "buy_point_terminal_count": 4,
        "data_gate_passed": True,
        "level1_scan_complete": True,
        "all_improving_level1_drilled": True,
        "all_admitted_level3_industry_state_applied": True,
        "all_company_industry_terminals_complete": True,
        "gate2_public_evidence_complete": True,
        "gate3_true_comparable_groups_confirmed": True,
        "gate4_public_evidence_complete": True,
        "all_cycle_valuations_have_valid_route_or_explicit_incomplete": True,
        "all_formal_valuations_have_structure": True,
        "all_formal_valuations_have_buy_point": True,
        "near_miss_source_legal": True,
        "stage_truncation_used": False,
        "gate2_mechanical_shortcut_used": False,
        "gate3_sw_level3_proxy_grouping_used": False,
        "gate4_partial_winner_research_used": False,
        "valuation_forbidden_shortcut_used": False,
        "historical_result_fallback_used": False,
        "left_value_codes": ["000001"],
        "left_turn_codes": ["000001"],
        "near_miss_codes": ["000002"],
        "near_miss_sorted_by": "reasonable_buy_range.upper",
        "gate3_grouping_basis": "core_earnings_driver_and_business_model",
    }


def test_completion_validator_accepts_conserved_full_run():
    validator = load_validator()
    assert validator.validate_completion_ledger(valid_ledger()) == []


def test_completion_validator_rejects_partial_gate4_and_proxy_grouping():
    validator = load_validator()
    ledger = valid_ledger()
    ledger["gate4_terminal_count"] = 3
    ledger["gate3_sw_level3_proxy_grouping_used"] = True
    ledger["gate3_grouping_basis"] = "sw_level3_code"
    errors = validator.validate_completion_ledger(ledger)
    assert any("gate3_pass_count" in error and "gate4_terminal_count" in error for error in errors)
    assert any("gate3_sw_level3_proxy_grouping_used" in error for error in errors)
    assert any("gate3_grouping_basis" in error for error in errors)


def test_runtime_snapshot_contains_complete_rule_surface():
    text = (ROOT / ".github/workflows/runtime-snapshot.yml").read_text(encoding="utf-8")
    for required in (
        "config/research_runtime_policy.json",
        "config/research_pipeline_manifest.json",
        "skills/a-share-low-risk/orchestrator/SKILL.md",
        "skills/a-share-low-risk/company-research/SKILL.md",
        "skills/a-share-low-risk/valuation/SKILL.md",
        "skills/a-share-low-risk/price-structure/SKILL.md",
        "scripts/validate_research_completion.py",
    ):
        assert required in text


def test_orchestrator_requires_completion_ledger_validator():
    text = (ROOT / "skills/a-share-low-risk/orchestrator/SKILL.md").read_text(encoding="utf-8")
    assert "validate_research_completion.py" in text
    assert "Gate3不得直接以 `sw_level3_code` 作为真正可比组" in text
    assert "Gate2/Gate4不得以机械字段筛选代替公开证据核验" in text
