import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_near_miss_ranking_is_auditable_and_never_lowers_buy_gate():
    manifest = json.loads((ROOT / "config/research_pipeline_manifest.json").read_text(encoding="utf-8"))
    c = manifest["buy_point_contract"]["near_miss_ranking_contract"]
    assert c["buyable_now_stays_separate"] is True
    assert c["must_output_when_eligible_universe_nonempty"] is True
    assert c["review_required_excluded_from_distance_ranking"] is True
    assert c["ranking_is_display_only_not_candidate_pool"] is True
    assert c["cross_run_persistence_as_pool_forbidden"] is True
    assert c["default_display_limit"] == 10
    assert c["research_admission_top_n_forbidden"] is True
    assert c["required_metrics"] == [
        "missing_hard_conditions",
        "value_gap_pct",
        "structure_gap_pct",
        "action_distance_pct",
        "distance_band",
        "current_missing",
        "next_trigger",
    ]
    assert "max(value_gap_pct, structure_gap_pct)" in c["action_distance_formula"]
    assert manifest["public_output"]["near_miss_section_title"] == "【接近买点榜】"


def test_orchestrator_requires_near_miss_without_versioned_labels():
    text = (ROOT / "skills/a-share-low-risk/orchestrator/SKILL.md").read_text(encoding="utf-8")
    assert "## 9. 接近买点榜" in text
    assert "正式买点只允许 `buyable_now`" in text
    assert "Top10 Near-miss" in text
    assert "不形成跨期候选池" in text
    assert "Ranking V3" not in text
