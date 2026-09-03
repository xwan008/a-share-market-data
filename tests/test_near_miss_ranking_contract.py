import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_near_miss_ranking_is_auditable_and_never_absorbs_buy_lists():
    manifest = json.loads((ROOT / "config/research_pipeline_manifest.json").read_text(encoding="utf-8"))
    c = manifest["buy_point_contract"]["near_miss_ranking_contract"]
    assert c["buyable_lists_stay_separate"] is True
    assert c["left_value_list_excluded_from_near_miss"] is True
    assert c["deep_discount_review_excluded_from_near_miss"] is True
    assert c["eligible_only_when_price_above_buy_range_upper"] is True
    assert c["must_output_when_eligible_universe_nonempty"] is True
    assert c["review_required_excluded_from_distance_ranking"] is True
    assert c["ranking_is_display_only_not_candidate_pool"] is True
    assert c["cross_run_persistence_as_pool_forbidden"] is True
    assert c["default_display_limit"] == 10
    assert c["research_admission_top_n_forbidden"] is True
    assert c["required_metrics"] == [
        "missing_hard_conditions",
        "value_gap_pct",
        "distance_band",
        "current_missing",
        "next_trigger",
    ]
    assert "reasonable_buy_range upper bound" in c["action_distance_formula"]
    assert "above_buy_range only" in c["action_distance_formula"]
    assert manifest["public_output"]["near_miss_section_title"] == "【接近买点榜】"


def test_orchestrator_requires_dual_lists_and_reasonable_buy_based_near_miss():
    text = (ROOT / "skills/a-share-low-risk/orchestrator/SKILL.md").read_text(encoding="utf-8")
    assert "## 8. 两个正式买点榜" in text
    assert "### 8.1 左侧价值买点榜" in text
    assert "### 8.2 左侧拐点买点榜" in text
    assert "左侧拐点买点榜 ⊂ 左侧价值买点榜" in text
    assert "## 9. Near-miss" in text
    assert "current_price > reasonable_buy_range.upper" in text
    assert "low_risk_buy_range.upper" in text
    assert "禁止用 `low_risk_buy_range.upper` 或 `safe_price_ceiling` 排Near-miss" in text
    assert "deep_discount_review" in text
    assert "仅展示，不持久化" in text
    assert "Ranking V3" not in text
