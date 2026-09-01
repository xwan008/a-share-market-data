import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_near_miss_ranking_contract_is_auditable_and_nonempty_by_rule():
    manifest = json.loads((ROOT / "config/research_pipeline_manifest.json").read_text(encoding="utf-8"))
    c = manifest["buy_point_contract"]["near_miss_ranking_contract"]
    assert c["buyable_now_stays_separate"] is True
    assert c["must_output_when_eligible_universe_nonempty"] is True
    assert c["review_required_excluded_from_distance_ranking"] is True
    assert c["ranking_is_display_only_not_candidate_pool"] is True
    assert c["cross_run_persistence_as_pool_forbidden"] is True
    assert c["default_display_limit"] == 10
    assert c["research_admission_top_n_forbidden"] is True
    assert "action_distance_pct" in c["required_metrics"]
    assert "ceiling_structure_gap_pct" in c["required_metrics"]
    assert manifest["public_output"]["near_miss_section_title"] == "【接近买点榜】"
    assert manifest["public_output"]["near_miss_must_be_nonempty_when_eligible_universe_nonempty"] is True

def test_orchestrator_requires_near_miss_output_without_lowering_buy_gate():
    text = (ROOT / "skills/a-share-low-risk/orchestrator/SKILL.md").read_text(encoding="utf-8")
    assert "## 接近买点榜（Near-miss Ranking V2）" in text
    assert "绝不为了凑榜降低" in text
    assert "Top10仍必须输出" in text
    assert "不得持久化为候选池" in text
