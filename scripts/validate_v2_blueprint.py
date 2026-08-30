from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/research_pipeline_manifest.json"
PRICE = ROOT / "data/research/v2/full_market_price_structure.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors = []
    m = load(MANIFEST)

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

    for stage in m.get("stages", []):
        sid = str(stage.get("id") or "").lower()
        if "t1" in sid or "t2" in sid:
            errors.append(f"tier_stage_forbidden:{sid}")

    validation = m.get("validation_policy") or {}
    if validation.get("case_free") is not True:
        errors.append("validation_policy_not_case_free")

    sanity_text = "\n".join(m.get("economic_sanity", {}).get("checks") or [])
    required_phrases = ["重复折价", "valuation_divergence", "价格结构扫描", "固定股票代码"]
    for phrase in required_phrases:
        if phrase not in sanity_text:
            errors.append(f"generic_invariant_missing:{phrase}")

    if PRICE.exists():
        p = load(PRICE)
        if p.get("mode") != "shadow":
            errors.append("price_structure_not_shadow")
        if p.get("universe_source") != "all_mainboard_codes_from_data/latest.json":
            errors.append("right_universe_not_full_market")
        universe_count = int(p.get("universe_count") or 0)
        verified_count = int(p.get("verified_count") or 0)
        companies = p.get("companies") or {}
        if universe_count < 3000:
            errors.append(f"right_universe_suspiciously_small:{universe_count}")
        if len(companies) != universe_count:
            errors.append(f"right_universe_count_mismatch:{len(companies)}!={universe_count}")
        if verified_count < 0.95 * max(1, universe_count):
            errors.append("right_structure_coverage_below_95pct")
        if any(
            row.get("price_discovery") and row.get("action") == "avoid"
            for row in companies.values()
            if isinstance(row, dict)
        ):
            errors.append("price_discovery_auto_rejected")

    status = "PASS" if not errors else "FAIL"
    print(json.dumps({"status": status, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
