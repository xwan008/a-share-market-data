import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / "config/research_pipeline_manifest.json").read_text(encoding="utf-8"))


def test_manifest_is_stable_production_contract_without_numeric_schema():
    m = manifest()
    assert m["contract_id"] == "a-share-low-risk-production"
    assert m["pipeline"] == "a_share_low_risk"
    assert m["mode"] == "production"
    assert "schema_version" not in m
    assert m["public_output"]["formal_publish_enabled"] is True


def test_stage_order_contains_all_hard_gates():
    assert manifest()["stage_order"] == [
        "data_gate", "prompt_full_market_discovery", "taxonomy_mapping",
        "level3_profitability_refresh", "company_admission_gate",
        "profit_chain_resolution", "company_mapping_gate", "company_light_screen",
        "company_comparison_and_dedup", "valuation", "price_structure",
        "buy_point_synthesis", "completion_gate", "publish",
    ]


def test_prompt_discovery_is_full_market_every_run_while_level3_state_is_reused():
    m = manifest()
    d = m["discovery_contract"]
    l3 = m["level3_state_contract"]
    assert d["method"] == "prompt_full_market_light_recall_every_run"
    assert d["previous_focus_list_may_not_seed_or_bound_discovery"] is True
    assert d["top_n_or_fixed_count_selection_forbidden"] is True
    assert l3["existing_valid_level3_state_must_be_reused"] is True
    assert l3["missing_level3_state_initialized_on_demand"] is True
    assert l3["stale_or_invalid_level3_state_revalidated_individually"] is True
    assert l3["whole_state_rebuild_for_missing_nodes_forbidden"] is True
    assert l3["daily_refresh_only_deep_rechecks_level3_nodes_with_new_or_changed_evidence"] is True


def test_both_profit_chain_types_are_admitted_and_share_downstream_rules():
    m = manifest()
    c = m["company_admission_contract"]
    p = m["profit_chain_contract"]
    assert "trend=improving" in c["admit_if"]
    assert "trend=stable AND breadth=divergent" in c["admit_if"]
    assert p["allowed_chain_types"] == ["improving", "stable_divergent"]
    assert p["both_chain_types_follow_same_company_screen_valuation_structure_and_buy_point_rules"] is True
    assert c["stable_divergent_does_not_lower_valuation_structure_or_buy_point_thresholds"] is True


def test_data_and_company_mapping_gates_fail_closed():
    m = manifest()
    d = m["data_gate_contract"]
    g = m["company_mapping_gate"]
    assert d["fail_closed"] is True
    assert d["publish_on_failure"] is False
    assert d["mutate_valid_state_on_failure"] is False
    assert g["all_missing_or_unmapped_codes_must_be_checked_against_admitted_level3_scope"] is True
    assert g["unresolved_in_scope_mapping_forbidden"] is True
    assert g["silent_omission_forbidden"] is True


def test_company_screen_is_exhaustive_after_admission():
    c = manifest()["company_comparison_contract"]
    s = c["company_light_screen"]
    assert s["all_mapped_mainboard_companies_in_admitted_chain_must_be_screened"] is True
    assert s["top_n_or_score_cutoff_before_screen_forbidden"] is True
    assert s["exclusion_requires_company_specific_evidence"] is True
    assert s["all_survivors_enter_horizontal_comparison"] is True
    assert s["core_earnings_evidence_required_for_survive"] is True
    assert c["dedup_must_preserve_all_source_chain_ids"] is True


def test_valuation_and_buy_point_contract_remain_strict():
    m = manifest()
    v = m["valuation_contract"]
    b = m["buy_point_contract"]
    p = m["price_structure_contract"]
    assert v["default_path"] == "relative_earnings_valuation"
    assert v["complex_model_is_exception_not_default"] is True
    assert v["single_mos_application_required"] is True
    assert p["independent_from_valuation"] is True
    assert b["hard_value_gate"] == "current_price <= safe_price_ceiling"
    assert b["buy_price_range_formula"] == "structure_entry_range intersect (-infinity, safe_price_ceiling]"
    assert b["damaged_or_overheated_cannot_be_buyable_now"] is True


def test_completion_persistence_and_near_miss_fail_closed():
    m = manifest()
    g = m["completion_gate_contract"]
    p = m["persistence_contract"]
    n = m["buy_point_contract"]["near_miss_ranking_contract"]
    assert g["all_admitted_chains_company_screened"] is True
    assert g["current_opportunities_must_come_only_from_buyable_now"] is True
    assert g["publish_on_failure"] is False
    assert p["industry_state_is_only_cross_run_fundamental_memory"] is True
    assert p["legacy_company_valuation_buy_state_reuse_forbidden"] is True
    assert n["ranking_is_display_only_not_candidate_pool"] is True
    assert n["default_display_limit"] == 10
