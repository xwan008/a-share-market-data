from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "data/research/v2/company_research.json"
GAP = ROOT / "data/research/v2/price_expectation_gap.json"
OUT = ROOT / "data/research/v2/opportunity_ranking.json"
TZ = ZoneInfo("Asia/Shanghai")
STATE_PRIORITY = {"PRIORITY_INFLECTION": 6, "RIGHT_PARTICIPATE": 5, "LEFT_WATCH": 4, "WAIT_BREAKOUT": 3, "WAIT_PULLBACK": 2, "REJECT": 0}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def choose_state(cr: dict, g: dict) -> str:
    rs = cr.get("research_status")
    structure = g.get("structure_type")
    expectation = g.get("expectation_gap_state")
    chase = g.get("chase_risk")
    if not cr.get("low_risk_eligible") or rs in {"ineligible_low_risk", "quality_review_required", "reject"}:
        return "REJECT"
    if structure == "damaged" or expectation == "fundamental_price_conflict":
        return "REJECT"
    if structure == "overheated" or chase == "high":
        return "WAIT_PULLBACK"
    if rs != "pass":
        return "LEFT_WATCH" if expectation in {"large_gap_not_started", "valuation_review_required", "gap_unclear_or_limited"} else "WAIT_BREAKOUT"
    if expectation == "valuation_review_required":
        return "LEFT_WATCH"
    if expectation == "priced_in_or_overheated":
        return "WAIT_PULLBACK" if structure in {"breakout", "trend_continuation", "pullback", "overheated"} else "REJECT"
    if expectation == "large_gap_not_started":
        return "WAIT_BREAKOUT" if structure == "transition" else "LEFT_WATCH"
    if expectation == "gap_just_starting":
        if structure == "breakout":
            return "PRIORITY_INFLECTION"
        if structure == "pullback":
            return "RIGHT_PARTICIPATE"
    if expectation == "trend_confirmed_gap_remaining":
        return "RIGHT_PARTICIPATE"
    if structure in {"base_not_started", "transition"}:
        return "WAIT_BREAKOUT"
    return "LEFT_WATCH"


def score_components(cr: dict, g: dict):
    research = {"pass": 30, "watch": 18, "driver_review_required": 8, "earnings_confirmation_required": 6}.get(cr.get("research_status"), 0)
    triage = clamp(float(cr.get("triage_score") or 0) / 8.0, 0, 15)
    bridge = 15 if cr.get("forward_bridge_valid") else 0
    gap = clamp(float(g.get("gap_to_reference_mid_pct") or 0) / 2.0, -15, 25) if g.get("valuation_reference_status") == "available" else -5
    structure = {"breakout": 15, "pullback": 14, "trend_continuation": 12, "base_not_started": 6, "transition": 4, "overheated": -8, "damaged": -20}.get(g.get("structure_type"), 0)
    chase = {"low": 5, "medium": 0, "high": -10}.get(g.get("chase_risk"), 0)
    quality = -6 if cr.get("deducted_profit_verification_required") else 3
    return {
        "research": round(research + triage, 2),
        "forward_bridge": bridge,
        "expectation_gap": round(gap, 2),
        "price_timing": structure,
        "chase_risk": chase,
        "earnings_quality_evidence": quality,
    }


def main() -> int:
    company = load(COMPANY)
    gap = load(GAP)
    cmap = company.get("companies") or {}
    grows = gap.get("companies") or {}
    ranked = []

    for code in company.get("selected_for_valuation_codes") or []:
        cr = cmap.get(code) or {}
        g = grows.get(code) or {}
        state = choose_state(cr, g)
        comps = score_components(cr, g)
        total = round(sum(comps.values()), 2)
        primary_driver = (cr.get("driver_links") or [{}])[0].get("driver_id") if cr.get("driver_links") else None
        production_ready = bool(cr.get("production_evidence_ready") and g.get("production_valuation_ready") and state in {"PRIORITY_INFLECTION", "RIGHT_PARTICIPATE", "LEFT_WATCH"})
        shadow_ready = bool(cr.get("research_status") == "pass" and g.get("valuation_reference_status") == "available" and state in {"PRIORITY_INFLECTION", "RIGHT_PARTICIPATE", "LEFT_WATCH"})
        blockers = []
        if cr.get("deducted_profit_verification_required"):
            blockers.append("deducted_profit_verification_required")
        if cr.get("driver_review_required"):
            blockers.append("driver_mapping_review_required")
        if g.get("valuation_reference_status") != "available":
            blockers.append("valuation_reference_required")
        if not g.get("production_valuation_ready"):
            blockers.append("second_independent_valuation_anchor_required")
        row = {
            "code": code,
            "name": cr.get("name") or g.get("name") or code,
            "state": state,
            "current_price": g.get("current_price"),
            "primary_driver": primary_driver,
            "driver_links": cr.get("driver_links") or [],
            "earnings_direction": cr.get("earnings_direction"),
            "research_status": cr.get("research_status"),
            "forward_bridge_valid": cr.get("forward_bridge_valid"),
            "forward_bridges": cr.get("forward_bridges") or [],
            "expectation_gap_state": g.get("expectation_gap_state"),
            "gap_to_reference_mid_pct": g.get("gap_to_reference_mid_pct"),
            "valuation_reference_range": g.get("valuation_reference_range"),
            "formal_buy_zone": None,
            "structure_type": g.get("structure_type"),
            "structure_action": g.get("structure_action"),
            "chase_risk": g.get("chase_risk"),
            "score_components": comps,
            "diagnostic_score": total,
            "shadow_priority_eligible": shadow_ready,
            "production_publish_eligible": production_ready,
            "blockers": sorted(set(blockers)),
            "invalidation_conditions": cr.get("invalidation_conditions") or [],
            "reason": f"research={cr.get('research_status')}; expectation={g.get('expectation_gap_state')}; structure={g.get('structure_type')}; chase={g.get('chase_risk')}"
        }
        ranked.append(row)

    ranked.sort(key=lambda x: (-STATE_PRIORITY.get(x["state"], 0), -float(x.get("diagnostic_score") or 0), x["code"]))
    buckets = {s: [x for x in ranked if x["state"] == s] for s in STATE_PRIORITY}

    shadow_pool = [x for x in ranked if x.get("shadow_priority_eligible")]
    shadow_top3 = []
    driver_counts = {}
    for x in shadow_pool:
        did = x.get("primary_driver") or "unmapped"
        if driver_counts.get(did, 0) >= 2:
            continue
        shadow_top3.append(x)
        driver_counts[did] = driver_counts.get(did, 0) + 1
        if len(shadow_top3) >= 3:
            break

    production_top3 = []
    driver_counts = {}
    for x in ranked:
        if not x.get("production_publish_eligible"):
            continue
        did = x.get("primary_driver") or "unmapped"
        if driver_counts.get(did, 0) >= 2:
            continue
        production_top3.append(x)
        driver_counts[did] = driver_counts.get(did, 0) + 1
        if len(production_top3) >= 3:
            break

    payload = {
        "schema_version": 1,
        "mode": "shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "reference_trade_date": gap.get("reference_trade_date") or company.get("reference_trade_date"),
        "ranked_count": len(ranked),
        "state_counts": {s: len(xs) for s, xs in buckets.items()},
        "shadow_priority_eligible_count": len(shadow_pool),
        "production_publish_eligible_count": sum(1 for x in ranked if x.get("production_publish_eligible")),
        "shadow_top3": shadow_top3,
        "production_top3": production_top3,
        "state_buckets": buckets,
        "ranked_opportunities": ranked,
        "discipline": [
            "diagnostic_score only orders candidates inside explicit eligibility states; it cannot repair missing evidence",
            "legacy V1 buy zones are never published by V2",
            "production publish eligibility requires verified recurring-profit evidence plus at least two independent V2 valuation anchors",
            "Top3 may contain fewer than three names or be empty"
        ]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "ranked": len(ranked), "states": payload["state_counts"], "shadow_top3": [x["code"] for x in shadow_top3], "production_top3": [x["code"] for x in production_top3]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
