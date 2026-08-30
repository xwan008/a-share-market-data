from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/research_pipeline_manifest.json"
PRICE = ROOT / "data/research/v2/full_market_price_structure.json"
EARNINGS = ROOT / "data/research/v2/earnings_anomaly_recall.json"
CROSS = ROOT / "data/research/v2/shadow_crosscheck.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors = []
    m = load(MANIFEST)
    if m.get("pipeline") != "a_share_low_risk_v2" or m.get("mode") != "shadow": errors.append("manifest_not_v2_shadow")
    skills = m.get("authoritative_skills") or {}
    expected = {"orchestrator","earnings_driver_scan","company_research","price_expectation_gap","opportunity_ranking"}
    if set(skills) != expected: errors.append(f"wrong_authoritative_skill_set:{sorted(skills)}")
    for name, rel in skills.items():
        if not (ROOT / rel).exists(): errors.append(f"missing_skill:{name}:{rel}")
    for old in (m.get("legacy_v1") or {}).get("deprecated_business_skills", []):
        if (ROOT / "skills/a-share-low-risk" / old / "SKILL.md").exists(): errors.append(f"deprecated_skill_still_present:{old}")
    for stage in m.get("stages", []):
        sid = str(stage.get("id") or "").lower()
        if "t1" in sid or "t2" in sid: errors.append(f"tier_stage_forbidden:{sid}")
    if (m.get("validation_policy") or {}).get("case_free") is not True: errors.append("validation_policy_not_case_free")

    sanity_text = "\n".join(m.get("economic_sanity", {}).get("checks") or [])
    for phrase in ["重复折价","valuation_divergence","价格结构扫描","固定股票代码","风险警示","量价确认","相对强度"]:
        if phrase not in sanity_text: errors.append(f"generic_invariant_missing:{phrase}")

    if PRICE.exists():
        p = load(PRICE); companies = p.get("companies") or {}; candidates = p.get("right_candidate_codes") or []
        if p.get("mode") != "shadow": errors.append("price_structure_not_shadow")
        if p.get("universe_source") != "all_mainboard_codes_from_data/latest.json": errors.append("right_universe_not_full_market")
        universe, verified = int(p.get("universe_count") or 0), int(p.get("verified_count") or 0)
        if universe < 3000: errors.append(f"right_universe_suspiciously_small:{universe}")
        if len(companies) != universe: errors.append(f"right_universe_count_mismatch:{len(companies)}!={universe}")
        if verified < 0.95 * max(1, universe): errors.append("right_structure_coverage_below_95pct")
        if any(row.get("price_discovery") and row.get("action") == "avoid" for row in companies.values() if isinstance(row, dict)): errors.append("price_discovery_auto_rejected")
        for code in candidates:
            row = companies.get(code) or {}
            if row.get("low_risk_eligible") is not True: errors.append(f"risk_warning_in_right_candidates:{code}")
            if row.get("structure_type") == "breakout" and row.get("breakout_confirmed") is not True: errors.append(f"unconfirmed_breakout_candidate:{code}")
            if row.get("structure_type") == "pullback":
                rs = row.get("relative_strength_20d_vs_market_pct")
                if rs is None or float(rs) < -2.01: errors.append(f"weak_relative_strength_pullback:{code}")

    if EARNINGS.exists():
        e = load(EARNINGS)
        for item in (e.get("candidates") or [])[:100]:
            if "quality_flags" not in item or "quality_review_required" not in item or "low_risk_eligible" not in item:
                errors.append("earnings_quality_fields_missing"); break

    if CROSS.exists():
        c = load(CROSS)
        for key in ["top_pass_right_low_medium_chase","top_pass_base_or_transition"]:
            if any(row.get("low_risk_eligible") is not True for row in c.get(key) or []): errors.append(f"risk_warning_in_crosscheck:{key}")

    status = "PASS" if not errors else "FAIL"
    print(json.dumps({"status":status,"errors":errors},ensure_ascii=False,indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
