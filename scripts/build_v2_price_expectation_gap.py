from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "data/research/v2/company_research.json"
PRICE = ROOT / "data/research/v2/full_market_price_structure.json"
LEGACY_VAL = ROOT / "data/research/pipeline/left_valuation_scan.json"
OUT = ROOT / "data/research/v2/price_expectation_gap.json"
TZ = ZoneInfo("Asia/Shanghai")


def load(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def valid_range(v):
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v) and v[0] > 0 and v[1] >= v[0]


def reference_range(row: dict):
    if valid_range(row.get("business_fair_value_range")):
        return row["business_fair_value_range"], "legacy_business_fair_value_reference"
    if valid_range(row.get("value_anchor_range")):
        return row["value_anchor_range"], "legacy_value_anchor_reference"
    if valid_range(row.get("scenario_fair_value_range")):
        return row["scenario_fair_value_range"], "legacy_cycle_scenario_reference"
    return None, None


def gap_state(price: float, rng):
    lo, hi = float(rng[0]), float(rng[1])
    mid = (lo + hi) / 2
    gap_mid = (mid / price - 1) * 100 if price > 0 else None
    if gap_mid is None:
        return "valuation_review_required", None
    if gap_mid >= 20:
        return "large", gap_mid
    if gap_mid >= 5:
        return "remaining", gap_mid
    if gap_mid >= -10:
        return "limited", gap_mid
    return "priced_in", gap_mid


def combine(value_state: str, structure: str):
    if value_state == "valuation_review_required":
        return "valuation_review_required"
    if structure == "damaged":
        return "fundamental_price_conflict"
    if structure == "overheated" or value_state == "priced_in":
        return "priced_in_or_overheated"
    if value_state == "large" and structure in {"base_not_started", "transition"}:
        return "large_gap_not_started"
    if value_state in {"large", "remaining"} and structure in {"breakout", "pullback"}:
        return "gap_just_starting"
    if value_state in {"large", "remaining"} and structure == "trend_continuation":
        return "trend_confirmed_gap_remaining"
    return "gap_unclear_or_limited"


def main() -> int:
    company = load(COMPANY, {})
    price = load(PRICE, {})
    legacy = load(LEGACY_VAL, {})
    pmap = price.get("companies") or {}
    vmap = {str(x.get("code") or "").zfill(6): x for x in legacy.get("companies", [])}
    cmap = company.get("companies") or {}
    codes = company.get("selected_for_valuation_codes") or []

    rows = {}
    state_counts = {}
    valuation_covered = 0
    for code in codes:
        cr = cmap.get(code) or {}
        pr = pmap.get(code) or {}
        vr = vmap.get(code) or {}
        current = pr.get("current_price") or vr.get("current_price")
        rng, ref_type = reference_range(vr) if vr.get("valuation_status") == "valid" else (None, None)
        if rng and isinstance(current, (int, float)) and current > 0:
            value_state, gap_mid = gap_state(float(current), rng)
            valuation_covered += 1
            ref = [round(float(rng[0]), 2), round(float(rng[1]), 2)]
            independent_anchor_count = 1
            formal_buy_zone_status = "blocked_insufficient_independent_v2_anchors"
        else:
            value_state, gap_mid = "valuation_review_required", None
            ref = None
            independent_anchor_count = 0
            formal_buy_zone_status = "blocked_valuation_reference_unavailable"

        structure = pr.get("structure_type") or "unavailable"
        expectation = combine(value_state, structure)
        state_counts[expectation] = state_counts.get(expectation, 0) + 1
        rows[code] = {
            "code": code,
            "name": cr.get("name") or pr.get("name") or vr.get("name") or code,
            "current_price": current,
            "research_status": cr.get("research_status"),
            "forward_bridge_valid": cr.get("forward_bridge_valid"),
            "valuation_reference_status": "available" if ref else "review_required",
            "valuation_reference_type": ref_type,
            "valuation_reference_range": ref,
            "valuation_model_reference": vr.get("valuation_model"),
            "valuation_basis_unit": vr.get("valuation_basis_unit"),
            "consensus_eps_current_year": vr.get("consensus_eps_current_year"),
            "market_forward_pe_current_year": vr.get("market_forward_pe_current_year"),
            "reasonable_multiple_reference": vr.get("reasonable_multiple_range"),
            "independent_v2_anchor_count": independent_anchor_count,
            "formal_buy_zone": None,
            "formal_buy_zone_status": formal_buy_zone_status,
            "legacy_safe_buy_range_ignored": vr.get("safe_buy_range"),
            "legacy_reasonable_buy_range_ignored": vr.get("reasonable_buy_range"),
            "value_gap_state": value_state,
            "gap_to_reference_mid_pct": round(gap_mid, 2) if gap_mid is not None else None,
            "structure_type": structure,
            "structure_action": pr.get("action"),
            "chase_risk": pr.get("chase_risk"),
            "relative_strength_20d_vs_market_pct": pr.get("relative_strength_20d_vs_market_pct"),
            "price_discovery": pr.get("price_discovery"),
            "expectation_gap_state": expectation,
            "production_valuation_ready": independent_anchor_count >= 2,
            "method_note": "Legacy V1 valuation is reused only as one numeric reference. Its safe/reasonable buy zones and legacy eligibility conclusions are explicitly ignored; a formal V2 buy zone requires at least two independent anchors."
        }

    payload = {
        "schema_version": 1,
        "mode": "shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "reference_trade_date": price.get("reference_trade_date") or company.get("reference_trade_date"),
        "valuation_queue_count": len(codes),
        "valuation_reference_covered_count": valuation_covered,
        "valuation_reference_missing_count": len(codes) - valuation_covered,
        "expectation_gap_state_counts": state_counts,
        "production_valuation_ready_count": sum(1 for x in rows.values() if x.get("production_valuation_ready")),
        "companies": rows,
        "method_note": "This stage closes shadow expectation-gap classification without resurrecting V1 buy-zone discounts. Missing or single-anchor valuation becomes an explicit blocker, not a fabricated formal entry range."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "valuation_queue": len(codes), "covered": valuation_covered, "missing": len(codes)-valuation_covered, "states": state_counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
