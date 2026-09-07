#!/usr/bin/env python3
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = ROOT / "config" / "industry_scan_universe.json"
CONTRACT_PATH = ROOT / "config" / "industry_evidence_contract.json"
HEALTH_PATH = ROOT / "data" / "health.json"
INDUSTRY_STATE_PATH = ROOT / "data" / "research" / "industry_state.json"
OUTPUT_PATH = ROOT / "data" / "research" / "industry_evidence.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def current_git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
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
    return {
        "status": "fresh" if 0 <= age <= max_age_days else "stale",
        "age_calendar_days": age,
        "max_age_calendar_days": max_age_days,
    }


def weighted_avg(rows, value_key, weight_key):
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        value = row.get(value_key)
        weight = row.get(weight_key) or 0
        if isinstance(value, (int, float)) and weight > 0:
            numerator += float(value) * float(weight)
            denominator += float(weight)
    return (numerator / denominator) if denominator else None


def l3_rows_for_l1(level3_state, l1_code):
    return [row for code, row in level3_state.items() if str(code).startswith(l1_code)]


def build_earnings_confirmation(l3_rows, industry_state, target_trade_date, contract):
    if not l3_rows:
        return []
    baseline_date = (
        industry_state.get("last_valid_baseline_date")
        or industry_state.get("baseline_trade_date")
        or ""
    )
    max_age = contract["freshness_policy"]["quarterly"]["max_age_calendar_days"]
    trend_counts = {}
    breadth_counts = {}
    for row in l3_rows:
        trend = str(row.get("trend") or "unknown")
        breadth = str(row.get("breadth") or "unknown")
        trend_counts[trend] = trend_counts.get(trend, 0) + 1
        breadth_counts[breadth] = breadth_counts.get(breadth, 0) + 1

    return [{
        "kind": "level3_profitability_breadth",
        "source": "data/research/industry_state.json",
        "reference_date": baseline_date,
        "frequency": "quarterly",
        "freshness": freshness(baseline_date, target_trade_date, max_age),
        "metrics": {
            "level3_count": len(l3_rows),
            "trend_counts": trend_counts,
            "breadth_counts": breadth_counts,
            "weighted_parent_profit_yoy": weighted_avg(
                l3_rows, "aggregate_parent_profit_yoy", "company_count_with_paired_h1"
            ),
            "weighted_revenue_yoy": weighted_avg(
                l3_rows, "aggregate_revenue_yoy", "company_count_with_paired_h1"
            ),
        },
    }]


def build_negative_evidence(l3_rows, industry_state, target_trade_date, contract):
    if not l3_rows:
        return []
    deteriorating = [
        {
            "code": row.get("code"),
            "name": row.get("name"),
            "trend": row.get("trend"),
            "breadth": row.get("breadth"),
        }
        for row in l3_rows
        if row.get("trend") == "deteriorating"
    ]
    uncertain = [
        {
            "code": row.get("code"),
            "name": row.get("name"),
            "trend": row.get("trend"),
            "breadth": row.get("breadth"),
        }
        for row in l3_rows
        if row.get("trend") == "uncertain"
    ]
    if not deteriorating and not uncertain:
        return []

    baseline_date = (
        industry_state.get("last_valid_baseline_date")
        or industry_state.get("baseline_trade_date")
        or ""
    )
    max_age = contract["freshness_policy"]["quarterly"]["max_age_calendar_days"]
    return [{
        "kind": "level3_profitability_falsifiers",
        "source": "data/research/industry_state.json",
        "reference_date": baseline_date,
        "frequency": "quarterly",
        "freshness": freshness(baseline_date, target_trade_date, max_age),
        "metrics": {
            "deteriorating_count": len(deteriorating),
            "uncertain_count": len(uncertain),
            "examples": (deteriorating + uncertain)[:8],
        },
    }]


def build_leading_anchor(l1_code, health, target_trade_date, contract):
    adapter = (contract.get("machine_adapters") or {}).get(l1_code)
    if not adapter:
        return []

    if adapter.get("adapter") == "commodity_anchors":
        commodity = health.get("commodity_anchors") or {}
        anchors = commodity.get("anchors") or {}
        symbols = adapter.get("symbols") or []
        selected = []
        for symbol in symbols:
            row = anchors.get(symbol)
            if row:
                selected.append({
                    "symbol": symbol,
                    "name": row.get("name"),
                    "role": row.get("role"),
                    "last_date": row.get("last_date"),
                    "current": row.get("current"),
                    "ma20": row.get("ma20"),
                    "ma60": row.get("ma60"),
                    "current_to_neutral": row.get("current_to_neutral"),
                    "trend_20_vs_60_pct": row.get("trend_20_vs_60_pct"),
                })
        if not selected:
            return []
        reference_date = commodity.get("reference_trade_date") or selected[0].get("last_date")
        freq = adapter.get("frequency", "daily")
        max_age = contract["freshness_policy"][freq]["max_age_calendar_days"]
        return [{
            "kind": "commodity_anchor_set",
            "source": "data/health.json#commodity_anchors",
            "reference_date": reference_date,
            "frequency": freq,
            "freshness": freshness(reference_date, target_trade_date, max_age),
            "source_status": commodity.get("status"),
            "anchors": selected,
        }]
    return []


def slot_is_fresh(slot):
    return bool(slot) and all((item.get("freshness") or {}).get("status") == "fresh" for item in slot)


def build():
    universe = read_json(UNIVERSE_PATH)
    contract = read_json(CONTRACT_PATH)
    health = read_json(HEALTH_PATH)
    industry_state = read_json(INDUSTRY_STATE_PATH)

    l1_universe = (universe.get("levels") or {}).get("level1") or []
    expected = int((universe.get("expected_counts") or {}).get("level1") or 0)
    if expected != contract.get("required_level1_count"):
        raise RuntimeError(
            f"level1 count contract mismatch: universe={expected} contract={contract.get('required_level1_count')}"
        )
    if len(l1_universe) != expected:
        raise RuntimeError(f"level1 universe incomplete: {len(l1_universe)} != {expected}")

    target_trade_date = str(health.get("trade_date") or "")
    if not target_trade_date:
        raise RuntimeError("data/health.json missing trade_date")

    level3_state = industry_state.get("level3_profitability") or {}
    industries = {}
    counts = {"complete": 0, "partial": 0, "missing": 0}

    for l1 in l1_universe:
        code = str(l1["code"])
        l3_rows = l3_rows_for_l1(level3_state, code)
        slots = {
            "leading_anchor": build_leading_anchor(code, health, target_trade_date, contract),
            "earnings_confirmation": build_earnings_confirmation(
                l3_rows, industry_state, target_trade_date, contract
            ),
            "negative_evidence": build_negative_evidence(
                l3_rows, industry_state, target_trade_date, contract
            ),
        }
        required_slots = [
            key for key, cfg in (contract.get("evidence_slots") or {}).items()
            if cfg.get("required")
        ]
        fresh_flags = {key: slot_is_fresh(slots.get(key) or []) for key in required_slots}
        present_count = sum(bool(slots.get(key)) for key in required_slots)

        if all(fresh_flags.values()):
            status = "complete"
        elif present_count:
            status = "partial"
        else:
            status = "missing"
        counts[status] += 1

        industries[code] = {
            "code": code,
            "name": l1["name"],
            "evidence_status": status,
            "required_slot_freshness": fresh_flags,
            "slots": slots,
            "level3_profitability_rows": len(l3_rows),
        }

    payload = {
        "contract_id": "a-share-industry-evidence",
        "schema_version": 1,
        "rollout_mode": contract.get("rollout_mode", "shadow"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_trade_date": target_trade_date,
        "source_repo_commit_sha": current_git_sha(),
        "source_health_generated_at": health.get("generated_at"),
        "source_industry_state_generated_at": industry_state.get("generated_at"),
        "universe": {
            "taxonomy": universe.get("taxonomy"),
            "expected_level1_count": expected,
            "actual_level1_count": len(l1_universe),
        },
        "coverage": counts,
        "level1": industries,
        "semantics": {
            "decision_owner": "ChatGPT Decision Layer",
            "collection_owner": "GitHub Actions Evidence Layer",
            "important": "This file precomputes evidence inputs. It does not mechanically label an industry improving/neutral/deteriorating.",
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "reference_trade_date": target_trade_date,
        "level1": len(industries),
        **counts,
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    build()
