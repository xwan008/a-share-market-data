from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/research_pipeline_manifest.json"
GOLDEN = ROOT / "config/low_risk_v2_golden_tests.json"
PRICE = ROOT / "data/research/v2/full_market_price_structure.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors = []
    m = load(MANIFEST)
    g = load(GOLDEN)

    if m.get("pipeline") != "a_share_low_risk_v2" or m.get("mode") != "shadow":
        errors.append("manifest_not_v2_shadow")

    skills = m.get("authoritative_skills") or {}
    expected = {"orchestrator", "earnings_driver_scan", "company_research", "price_expectation_gap", "opportunity_ranking"}
    if set(skills) != expected:
        errors.append(f"wrong_authoritative_skill_set:{sorted(skills)}")
    for name, rel in skills.items():
        if not (ROOT / rel).exists():
            errors.append(f"missing_skill:{name}:{rel}")

    legacy = m.get("legacy_v1") or {}
    for old in legacy.get("deprecated_business_skills", []):
        p = ROOT / "skills/a-share-low-risk" / old / "SKILL.md"
        if p.exists():
            errors.append(f"deprecated_skill_still_present:{old}")

    constitution = "\n".join(m.get("constitution") or [])
    if "T1/T2" not in json.dumps(m, ensure_ascii=False):
        pass
    # T1/T2 may appear only in explicit deprecation/sanity wording, never as a V2 stage id.
    for stage in m.get("stages", []):
        sid = str(stage.get("id") or "").lower()
        if "t1" in sid or "t2" in sid:
            errors.append(f"tier_stage_forbidden:{sid}")

    invariants = g.get("global_invariants") or []
    required_phrases = ["不得直接乘入", "重复折价", "右侧扫描宇宙", "创新高", "估值方法严重冲突"]
    joined = "\n".join(invariants)
    for phrase in required_phrases:
        if phrase not in joined:
            errors.append(f"golden_invariant_missing:{phrase}")

    if PRICE.exists():
        p = load(PRICE)
        if p.get("mode") != "shadow":
            errors.append("price_structure_not_shadow")
        if p.get("universe_source") != "all_mainboard_codes_from_data/latest.json":
            errors.append("right_universe_not_full_market")
        companies = p.get("companies") or {}
        if "601138" not in companies:
            errors.append("industrial_fulin_not_scanned")
        else:
            row = companies["601138"]
            if row.get("reason") in {"not_in_fundamental_common_pool", "no_resistance_map"}:
                errors.append(f"industrial_fulin_forbidden_rejection:{row.get('reason')}")
            if row.get("price_discovery") and row.get("action") == "avoid":
                errors.append("price_discovery_auto_rejected")

        if p.get("universe_count", 0) < 3000:
            errors.append(f"right_universe_suspiciously_small:{p.get('universe_count')}")
        if p.get("verified_count", 0) < 0.95 * max(1, p.get("universe_count", 0)):
            errors.append("right_structure_coverage_below_95pct")

    status = "PASS" if not errors else "FAIL"
    print(json.dumps({"status": status, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
