import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / "config/research_pipeline_manifest.json").read_text(encoding="utf-8"))


def runtime():
    return json.loads((ROOT / "config/research_runtime_policy.json").read_text(encoding="utf-8"))


def test_normal_path_is_simple_relative_valuation():
    v = manifest()["valuation_contract"]
    assert "valuation_engine_version" not in v
    assert v["default_path"] == "relative_earnings_valuation"
    assert v["complex_model_is_exception_not_default"] is True
    assert v["normal_company_complex_model_forbidden_as_default"] is True


def test_normal_path_has_pe_pb_roe_peer_growth_and_180d_sanity():
    v = manifest()["valuation_contract"]
    req = v["default_path_required_inputs"]
    for key in [
        "core_forward_eps",
        "current_pe_or_ttm_pe",
        "pb",
        "roe",
        "core_profit_growth",
        "level3_peer_pe_median",
        "level3_peer_pb_median",
        "price_180d_median",
        "price_180d_percentile",
    ]:
        assert key in req
    assert v["fair_pe_construction"]["pb_roe_cross_check_required"] is True
    assert v["market_sanity"]["history_window_trading_days"] == 180


def test_complex_model_needs_exception_trigger():
    v = manifest()["valuation_contract"]
    assert "major_restructuring" in v["exception_path_triggers"]
    assert "negative_or_unusable_pe" in v["exception_path_triggers"]
    assert "nav_dcf" in v["exception_path_models"]
    assert v["exception_trigger_required"] is True
    assert runtime()["stage_execution_policy"]["exception_trigger_required_before_complex_model"] is True


def test_single_mos_and_safe_ceiling():
    v = manifest()["valuation_contract"]
    assert v["single_mos_application_required"] is True
    assert v["safe_price_ceiling_formula"] == "base_fair_value * (1 - margin_of_safety_pct)"
    assert v["fixed_discount_from_reasonable_lower_bound_forbidden"] is True


def test_no_numeric_schema_or_engine_sequence_in_contract():
    m = manifest()
    assert "schema_version" not in m
    assert m["mode"] == "production"
