from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "data/research/v2/company_research.json"
PRICE = ROOT / "data/research/v2/full_market_price_structure.json"
VALUATION = ROOT / "data/research/v2/valuation_reference.json"
OUT = ROOT / "data/research/v2/price_expectation_gap.json"
TZ = ZoneInfo("Asia/Shanghai")


def load(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def valid_range(v):
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v) and v[0] > 0 and v[1] >= v[0]


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
    valuation = load(VALUATION, {})
    pmap = price.get("companies") or {}
    vmap = valuation.get("companies") or {}
    cmap = company.get("companies") or {}
    codes = company.get("selected_for_valuation_codes") or []

    rows = {}
    state_counts = {}
    valuation_covered = 0
    for code in codes:
        cr = cmap.get(code) or {}
        pr = pmap.get(code) or {}
        vr = vmap.get(code) or {}
        current = pr.get("current_price")
        rng = vr.get("reference_range") if vr.get("status") == "available" and valid_range(vr.get("reference_range")) else None
        if rng and isinstance(current, (int, float)) and current > 0:
            value_state, gap_mid = gap_state(float(current), rng)
            valuation_covered += 1
            ref = [round(float(rng[0]), 2), round(float(rng[1]), 2)]
            independent_anchor_count = int(vr.get("independent_anchor_count") or 0)
            formal_buy_zone_status = "ready_for_cross_anchor_intersection" if independent_anchor_count >= 2 else "blocked_insufficient_independent_v2_anchors"
        else:
            value_state, gap_mid = "valuation_review_required", None
            ref = None
            independent_anchor_count = int(vr.get("independent_anchor_count") or 0)
            formal_buy_zone_status = f"blocked_{vr.get('reason') or 'valuation_reference_unavailable'}"

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
            "valuation_reference_type": vr.get("reference_source"),
            "valuation_reference_range": ref,
            "valuation_reference_blocker": vr.get("reason"),
            "valuation_model_reference": vr.get("valuation_model"),
            "valuation_basis_unit": vr.get("valuation_basis_unit"),
            "consensus_eps_current_year": vr.get("consensus_eps_current_year"),
            "market_forward_pe_current_year": vr.get("market_forward_pe_current_year"),
            "reasonable_multiple_reference": vr.get("reasonable_multiple_reference"),
            "independent_v2_anchor_count": independent_anchor_count,
            "formal_buy_zone": None,
            "formal_buy_zone_status": formal_buy_zone_status,
            "legacy_safe_buy_range_ignored": vr.get("legacy_safe_buy_range_ignored"),
            "legacy_reasonable_buy_range_ignored": vr.get("legacy_reasonable_buy_range_ignored"),
            "value_gap_state": value_state,
            "gap_to_reference_mid_pct": round(gap_mid, 2) if gap_mid is not None else None,
            "structure_type": structure,
            "structure_action": pr.get("action"),
            "chase_risk": pr.get("chase_risk"),
            "relative_strength_20d_vs_market_pct": pr.get("relative_strength_20d_vs_market_pct"),
            "price_discovery": pr.get("price_discovery"),
            "expectation_gap_state": expectation,
            "production_valuation_ready": independent_anchor_count >= 2,
            "method_note": "Value-gap classification reads only the V2 valuation-reference layer. A single numeric reference can support shadow expectation-gap research, but fewer than two independent anchors can never create a formal V2 buy zone."
        }

    payload = {
        "schema_version": 2,
        "mode": "shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "reference_trade_date": price.get("reference_trade_date") or company.get("reference_trade_date"),
        "valuation_queue_count": len(codes),
        "valuation_reference_covered_count": valuation_covered,
        "valuation_reference_missing_count": len(codes) - valuation_covered,
        "valuation_reference_source_counts": valuation.get("source_counts") or {},
        "expectation_gap_state_counts": state_counts,
        "production_valuation_ready_count": sum(1 for x in rows.values() if x.get("production_valuation_ready")),
        "companies": rows,
        "method_note": "This stage closes shadow expectation-gap classification through the V2 valuation-reference layer. Missing or single-anchor valuation is an explicit blocker; V1 buy-zone conclusions cannot leak into formal V2 output."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "valuation_queue": len(codes), "covered": valuation_covered, "missing": len(codes)-valuation_covered, "states": state_counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
