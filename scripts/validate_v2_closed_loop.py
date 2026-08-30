from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVERS = ROOT / "data/research/v2/earnings_driver_scan.json"
COMPANY = ROOT / "data/research/v2/company_research.json"
VALUATION = ROOT / "data/research/v2/valuation_reference.json"
PRICE = ROOT / "data/research/v2/full_market_price_structure.json"
GAP = ROOT / "data/research/v2/price_expectation_gap.json"
RANK = ROOT / "data/research/v2/opportunity_ranking.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors = []
    outputs = (DRIVERS, COMPANY, VALUATION, PRICE, GAP, RANK)
    for path in outputs:
        if not path.exists():
            errors.append(f"missing_output:{path.name}")
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 2

    d, c, v, p, g, r = map(load, outputs)
    if any(x.get("mode") != "shadow" for x in (d, c, v, p, g, r)):
        errors.append("non_shadow_output_detected")

    ref = p.get("reference_trade_date")
    for name, x in (("company", c), ("valuation", v), ("gap", g), ("ranking", r)):
        if x.get("reference_trade_date") != ref:
            errors.append(f"reference_trade_date_mismatch:{name}:{x.get('reference_trade_date')}!={ref}")

    active = [x for x in d.get("drivers", []) if x.get("active")]
    for x in active:
        if not x.get("direct_profit_driver") or not x.get("evidence_for"):
            errors.append(f"active_driver_without_profit_evidence:{x.get('driver_id')}")
    if (d.get("driver_policy") or {}).get("legacy_t1_t2_controls_eligibility") is not False:
        errors.append("legacy_tier_still_controls_driver_eligibility")

    cmap = c.get("companies") or {}
    for code in c.get("research_pass_codes") or []:
        row = cmap.get(code) or {}
        if row.get("risk_warning") or not row.get("low_risk_eligible"):
            errors.append(f"risk_warning_in_research_pass:{code}")
        if not row.get("forward_bridge_valid"):
            errors.append(f"research_pass_without_forward_bridge:{code}")
    selected = set(c.get("selected_for_valuation_codes") or [])
    if not selected.issubset(set(cmap)):
        errors.append("valuation_queue_not_subset_of_company_research")

    vrows = v.get("companies") or {}
    if set(vrows) != selected:
        errors.append(f"valuation_reference_company_set_mismatch:{len(vrows)}!={len(selected)}")
    for code, row in vrows.items():
        anchors = int(row.get("independent_anchor_count") or 0)
        if anchors < 0 or anchors > 1:
            errors.append(f"unexpected_valuation_reference_anchor_count:{code}:{anchors}")
        if row.get("status") == "available" and anchors != 1:
            errors.append(f"available_reference_without_one_anchor:{code}:{anchors}")
        if row.get("status") != "available" and anchors != 0:
            errors.append(f"review_reference_with_nonzero_anchor:{code}:{anchors}")

    grows = g.get("companies") or {}
    if set(grows) != selected:
        errors.append(f"gap_company_set_mismatch:{len(grows)}!={len(selected)}")
    for code, row in grows.items():
        anchors = int(row.get("independent_v2_anchor_count") or 0)
        expected = int((vrows.get(code) or {}).get("independent_anchor_count") or 0)
        if anchors != expected:
            errors.append(f"gap_anchor_count_mismatch:{code}:{anchors}!={expected}")
        if anchors < 2 and row.get("formal_buy_zone") is not None:
            errors.append(f"formal_buy_zone_without_two_independent_anchors:{code}")
        if row.get("legacy_safe_buy_range_ignored") and row.get("formal_buy_zone") == row.get("legacy_safe_buy_range_ignored"):
            errors.append(f"legacy_buy_zone_leaked_into_v2:{code}")

    ranked = r.get("ranked_opportunities") or []
    by_code = {x.get("code"): x for x in ranked}
    if set(by_code) != selected:
        errors.append(f"ranking_company_set_mismatch:{len(by_code)}!={len(selected)}")
    for x in r.get("shadow_top3") or []:
        code = x.get("code")
        row = by_code.get(code) or {}
        cr = cmap.get(code) or {}
        if not row.get("shadow_priority_eligible"):
            errors.append(f"shadow_top3_not_eligible:{code}")
        if cr.get("risk_warning"):
            errors.append(f"risk_warning_in_shadow_top3:{code}")
        if row.get("state") not in {"PRIORITY_INFLECTION", "RIGHT_PARTICIPATE", "LEFT_WATCH"}:
            errors.append(f"invalid_shadow_top3_state:{code}:{row.get('state')}")
    for x in r.get("production_top3") or []:
        if not x.get("production_publish_eligible"):
            errors.append(f"production_top3_without_publish_eligibility:{x.get('code')}")

    status = "PASS" if not errors else "FAIL"
    print(json.dumps({
        "status": status,
        "errors": errors,
        "counts": {
            "active_drivers": len(active),
            "company_recall": len(cmap),
            "research_pass": len(c.get("research_pass_codes") or []),
            "valuation_queue": len(selected),
            "valuation_reference_available": v.get("available_count"),
            "valuation_reference_review_required": v.get("review_required_count"),
            "valuation_covered": g.get("valuation_reference_covered_count"),
            "ranked": len(ranked),
            "shadow_top3": len(r.get("shadow_top3") or []),
            "production_top3": len(r.get("production_top3") or [])
        }
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
