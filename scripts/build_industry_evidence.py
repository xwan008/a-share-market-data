#!/usr/bin/env python3
import json
import subprocess
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = ROOT / "config" / "industry_scan_universe.json"
CONTRACT_PATH = ROOT / "config" / "industry_evidence_contract.json"
HEALTH_PATH = ROOT / "data" / "health.json"
INDUSTRY_STATE_PATH = ROOT / "data" / "research" / "industry_state.json"
LEADING_ANCHOR_PATH = ROOT / "data" / "research" / "industry_leading_anchors.json"
SHARD_DIR = ROOT / "data" / "shards"
OUTPUT_PATH = ROOT / "data" / "research" / "industry_evidence.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def current_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def parse_date(value):
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def freshness(reference_date, target_date, max_age_days):
    ref = parse_date(reference_date)
    target = parse_date(target_date)
    if not ref or not target:
        return {"status": "unknown", "age_calendar_days": None, "max_age_calendar_days": max_age_days}
    age = (target - ref).days
    return {"status": "fresh" if 0 <= age <= max_age_days else "stale", "age_calendar_days": age, "max_age_calendar_days": max_age_days}


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def weighted_avg(rows, value_key, weight_key):
    numerator = denominator = 0.0
    for row in rows:
        value = row.get(value_key)
        weight = row.get(weight_key) or 0
        if is_number(value) and is_number(weight) and weight > 0:
            numerator += float(value) * float(weight)
            denominator += float(weight)
    return (numerator / denominator) if denominator else None


def l3_rows_for_l1(level3_state, l1_code):
    return [row for code, row in level3_state.items() if str(code).startswith(l1_code)]


def core_growth_from_fundamentals(fundamentals):
    for key in ("deduct_net_profit_yoy", "deduct_basic_eps_yoy"):
        value = fundamentals.get(key)
        if is_number(value):
            return float(value), key
    return None, None


def scan_shard_financial_breadth(target_trade_date, contract):
    shard_files = sorted(SHARD_DIR.glob("*.json"))
    if not shard_files:
        raise RuntimeError("no data/shards/*.json found for industry evidence breadth")
    by_l1 = defaultdict(lambda: {"company_count": 0, "financial_usable": 0, "core_growth_values": [], "core_growth_sources": defaultdict(int), "revenue_growth_values": [], "headline_profit_growth_values": [], "report_dates": []})
    parsed = stock_count = 0
    for path in shard_files:
        payload = read_json(path)
        if str(payload.get("trade_date") or "") != target_trade_date:
            raise RuntimeError(f"shard trade_date mismatch: {path.name}={payload.get('trade_date')} target={target_trade_date}")
        parsed += 1
        for stock in (payload.get("stocks") or {}).values():
            stock_count += 1
            if stock.get("industry_mapping_status") != "mapped":
                continue
            sw3 = str(stock.get("sw_level3_code") or "")
            if len(sw3) < 3 or not sw3.startswith("S"):
                continue
            row = by_l1[sw3[:3]]
            row["company_count"] += 1
            fundamentals = stock.get("fundamentals") or {}
            if fundamentals:
                row["financial_usable"] += 1
            if fundamentals.get("report_date"):
                row["report_dates"].append(str(fundamentals["report_date"])[:10])
            core_growth, core_source = core_growth_from_fundamentals(fundamentals)
            if core_growth is not None:
                row["core_growth_values"].append(core_growth)
                row["core_growth_sources"][core_source] += 1
            if is_number(fundamentals.get("revenue_yoy")):
                row["revenue_growth_values"].append(float(fundamentals["revenue_yoy"]))
            if is_number(fundamentals.get("net_profit_yoy")):
                row["headline_profit_growth_values"].append(float(fundamentals["net_profit_yoy"]))
    max_age = contract["freshness_policy"]["quarterly"]["max_age_calendar_days"]
    evidence = {}
    for l1_code, row in by_l1.items():
        core, revenue, headline = row["core_growth_values"], row["revenue_growth_values"], row["headline_profit_growth_values"]
        reference_date = max(row["report_dates"]) if row["report_dates"] else ""
        def breadth(values, predicate):
            return (sum(1 for value in values if predicate(value)) / len(values)) if values else None
        evidence[l1_code] = {"reference_date": reference_date, "freshness": freshness(reference_date, target_trade_date, max_age), "company_count": row["company_count"], "financial_usable": row["financial_usable"], "core_growth_usable": len(core), "core_growth_sources": dict(row["core_growth_sources"]), "core_improving_breadth": breadth(core, lambda value: value > 0), "core_deteriorating_breadth": breadth(core, lambda value: value < 0), "core_strong_deteriorating_breadth": breadth(core, lambda value: value <= -20), "revenue_growth_usable": len(revenue), "revenue_improving_breadth": breadth(revenue, lambda value: value > 0), "headline_profit_growth_usable": len(headline), "headline_profit_deteriorating_breadth": breadth(headline, lambda value: value < 0)}
    return evidence, {"shard_file_count": len(shard_files), "actual_shard_content_read_count": parsed, "stock_records_read": stock_count}


def build_state_earnings_confirmation(l3_rows, industry_state, target_trade_date, contract):
    if not l3_rows:
        return []
    baseline_date = industry_state.get("last_valid_baseline_date") or industry_state.get("baseline_trade_date") or ""
    max_age = contract["freshness_policy"]["quarterly"]["max_age_calendar_days"]
    trend_counts, breadth_counts = {}, {}
    for row in l3_rows:
        trend, breadth = str(row.get("trend") or "unknown"), str(row.get("breadth") or "unknown")
        trend_counts[trend] = trend_counts.get(trend, 0) + 1
        breadth_counts[breadth] = breadth_counts.get(breadth, 0) + 1
    return [{"kind": "level3_profitability_breadth", "source": "data/research/industry_state.json", "reference_date": baseline_date, "frequency": "quarterly", "freshness": freshness(baseline_date, target_trade_date, max_age), "metrics": {"level3_count": len(l3_rows), "trend_counts": trend_counts, "breadth_counts": breadth_counts, "weighted_parent_profit_yoy": weighted_avg(l3_rows, "aggregate_parent_profit_yoy", "company_count_with_paired_h1"), "weighted_revenue_yoy": weighted_avg(l3_rows, "aggregate_revenue_yoy", "company_count_with_paired_h1")}}]


def build_shard_earnings_confirmation(l1_code, shard_breadth):
    row = shard_breadth.get(l1_code)
    if not row or not row.get("financial_usable"):
        return []
    return [{"kind": "full_shard_financial_breadth", "source": "data/shards/*.json", "reference_date": row.get("reference_date"), "frequency": "quarterly", "freshness": row.get("freshness"), "metrics": {"company_count": row.get("company_count"), "financial_usable": row.get("financial_usable"), "core_growth_usable": row.get("core_growth_usable"), "core_growth_sources": row.get("core_growth_sources"), "core_improving_breadth": row.get("core_improving_breadth"), "revenue_growth_usable": row.get("revenue_growth_usable"), "revenue_improving_breadth": row.get("revenue_improving_breadth")}}]


def build_negative_evidence(l1_code, l3_rows, industry_state, target_trade_date, contract, shard_breadth):
    evidence = []
    row = shard_breadth.get(l1_code)
    if row and row.get("core_growth_usable"):
        evidence.append({"kind": "full_shard_profitability_falsifier_scan", "source": "data/shards/*.json", "reference_date": row.get("reference_date"), "frequency": "quarterly", "freshness": row.get("freshness"), "checked_scope": "mapped_main_board_companies_with_core_growth_fields", "metrics": {"core_growth_usable": row.get("core_growth_usable"), "core_deteriorating_breadth": row.get("core_deteriorating_breadth"), "core_strong_deteriorating_breadth": row.get("core_strong_deteriorating_breadth"), "headline_profit_deteriorating_breadth": row.get("headline_profit_deteriorating_breadth")}})
    if l3_rows:
        deteriorating = [{"code": item.get("code"), "name": item.get("name"), "trend": item.get("trend"), "breadth": item.get("breadth")} for item in l3_rows if item.get("trend") == "deteriorating"]
        uncertain = [{"code": item.get("code"), "name": item.get("name"), "trend": item.get("trend"), "breadth": item.get("breadth")} for item in l3_rows if item.get("trend") == "uncertain"]
        baseline_date = industry_state.get("last_valid_baseline_date") or industry_state.get("baseline_trade_date") or ""
        max_age = contract["freshness_policy"]["quarterly"]["max_age_calendar_days"]
        evidence.append({"kind": "level3_profitability_falsifier_scan", "source": "data/research/industry_state.json", "reference_date": baseline_date, "frequency": "quarterly", "freshness": freshness(baseline_date, target_trade_date, max_age), "checked_scope": "available_level3_profitability_state", "checked_none": not deteriorating and not uncertain, "metrics": {"deteriorating_count": len(deteriorating), "uncertain_count": len(uncertain), "examples": (deteriorating + uncertain)[:8]}})
    return evidence


def load_leading_anchors(target_trade_date):
    if not LEADING_ANCHOR_PATH.exists():
        return None
    payload = read_json(LEADING_ANCHOR_PATH)
    if payload.get("contract_id") != "a-share-industry-leading-anchors":
        raise RuntimeError("industry leading-anchor contract mismatch")
    if str(payload.get("reference_trade_date") or "") != target_trade_date:
        raise RuntimeError(f"industry leading-anchor trade_date mismatch: {payload.get('reference_trade_date')} != {target_trade_date}")
    return payload


def build_new_leading_anchor(l1_code, leading_anchors):
    if not leading_anchors:
        return []
    row = (leading_anchors.get("level1") or {}).get(l1_code) or {}
    evidence = []
    for anchor in row.get("anchors") or []:
        if (anchor.get("freshness") or {}).get("status") != "fresh":
            continue
        evidence.append({"kind": "industry_leading_anchor", "source": "data/research/industry_leading_anchors.json", "anchor_id": anchor.get("anchor_id"), "primary": anchor.get("anchor_id") == row.get("primary_anchor_id"), "source_type": anchor.get("source_type"), "source_detail": anchor.get("source"), "proxy_strength": anchor.get("proxy_strength"), "reference_date": anchor.get("reference_date"), "frequency": anchor.get("frequency"), "freshness": anchor.get("freshness"), "metrics": anchor.get("metrics")})
    return evidence


def build_legacy_commodity_fallback(l1_code, health, target_trade_date, contract):
    adapter = (contract.get("machine_adapters") or {}).get(l1_code)
    if not adapter or adapter.get("adapter") != "commodity_anchors":
        return []
    commodity = health.get("commodity_anchors") or {}
    anchors = commodity.get("anchors") or {}
    selected = []
    for symbol in adapter.get("symbols") or []:
        row = anchors.get(symbol)
        if row:
            selected.append({"symbol": symbol, "name": row.get("name"), "role": row.get("role"), "last_date": row.get("last_date"), "current": row.get("current"), "ma20": row.get("ma20"), "ma60": row.get("ma60"), "current_to_neutral": row.get("current_to_neutral"), "trend_20_vs_60_pct": row.get("trend_20_vs_60_pct")})
    if not selected:
        return []
    reference_date = commodity.get("reference_trade_date") or selected[0].get("last_date")
    freq = adapter.get("frequency", "daily")
    max_age = contract["freshness_policy"][freq]["max_age_calendar_days"]
    return [{"kind": "commodity_anchor_set", "source": "data/health.json#commodity_anchors", "reference_date": reference_date, "frequency": freq, "freshness": freshness(reference_date, target_trade_date, max_age), "source_status": commodity.get("status"), "anchors": selected}]


def build_leading_anchor(l1_code, health, target_trade_date, contract, leading_anchors):
    evidence = build_new_leading_anchor(l1_code, leading_anchors)
    if evidence:
        return evidence
    return build_legacy_commodity_fallback(l1_code, health, target_trade_date, contract)


def slot_is_fresh(slot):
    return bool(slot) and any((item.get("freshness") or {}).get("status") == "fresh" for item in slot)


def build():
    universe, contract, health, industry_state = read_json(UNIVERSE_PATH), read_json(CONTRACT_PATH), read_json(HEALTH_PATH), read_json(INDUSTRY_STATE_PATH)
    l1_universe = (universe.get("levels") or {}).get("level1") or []
    expected = int((universe.get("expected_counts") or {}).get("level1") or 0)
    if expected != contract.get("required_level1_count") or len(l1_universe) != expected:
        raise RuntimeError(f"level1 count contract mismatch/incomplete: actual={len(l1_universe)} expected={expected} contract={contract.get('required_level1_count')}")
    target_trade_date = str(health.get("trade_date") or "")
    if not target_trade_date:
        raise RuntimeError("data/health.json missing trade_date")
    leading_anchors = load_leading_anchors(target_trade_date)
    shard_breadth, shard_scan = scan_shard_financial_breadth(target_trade_date, contract)
    level3_state = industry_state.get("level3_profitability") or {}
    industries, counts = {}, {"complete": 0, "partial": 0, "missing": 0}
    for l1 in l1_universe:
        code = str(l1["code"])
        l3_rows = l3_rows_for_l1(level3_state, code)
        earnings = build_shard_earnings_confirmation(code, shard_breadth)
        earnings.extend(build_state_earnings_confirmation(l3_rows, industry_state, target_trade_date, contract))
        slots = {"leading_anchor": build_leading_anchor(code, health, target_trade_date, contract, leading_anchors), "earnings_confirmation": earnings, "negative_evidence": build_negative_evidence(code, l3_rows, industry_state, target_trade_date, contract, shard_breadth)}
        required_slots = [key for key, cfg in (contract.get("evidence_slots") or {}).items() if cfg.get("required")]
        fresh_flags = {key: slot_is_fresh(slots.get(key) or []) for key in required_slots}
        present_count = sum(bool(slots.get(key)) for key in required_slots)
        status = "complete" if all(fresh_flags.values()) else ("partial" if present_count else "missing")
        counts[status] += 1
        industries[code] = {"code": code, "name": l1["name"], "evidence_status": status, "required_slot_freshness": fresh_flags, "slots": slots, "level3_profitability_rows": len(l3_rows)}
    leading_collection = (leading_anchors or {}).get("collection") or {"level1_expected": expected, "level1_accounted": 0, "complete": 0, "partial": expected, "source_unavailable": True}
    payload = {"contract_id": "a-share-industry-evidence", "schema_version": 3, "rollout_mode": contract.get("rollout_mode", "shadow"), "generated_at": datetime.now(timezone.utc).isoformat(), "reference_trade_date": target_trade_date, "source_repo_commit_sha": current_git_sha(), "source_health_generated_at": health.get("generated_at"), "source_industry_state_generated_at": industry_state.get("generated_at"), "source_leading_anchor_generated_at": (leading_anchors or {}).get("generated_at"), "universe": {"taxonomy": universe.get("taxonomy"), "expected_level1_count": expected, "actual_level1_count": len(l1_universe)}, "shard_financial_breadth_scan": shard_scan, "leading_anchor_collection": leading_collection, "coverage": counts, "level1": industries, "semantics": {"decision_owner": "ChatGPT Decision Layer", "collection_owner": "GitHub Actions Evidence Layer", "important": "Industry leading anchors are collected independently from stock prices and financial breadth. Evidence Layer prepares inputs but does not mechanically label prosperity."}}
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reference_trade_date": target_trade_date, "level1": len(industries), **counts, **shard_scan, "leading_anchor_complete": leading_collection.get("complete"), "output": str(OUTPUT_PATH.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    build()
