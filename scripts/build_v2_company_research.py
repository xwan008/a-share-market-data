from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DRIVERS = ROOT / "data/research/v2/earnings_driver_scan.json"
EARNINGS = ROOT / "data/research/v2/earnings_anomaly_recall.json"
REGISTRY = ROOT / "data/research/company_industry_registry.json"
WEEKLY = ROOT / "data/research/weekly_fundamental_opportunity_pool.json"
LATEST = ROOT / "data/latest.json"
OUT = ROOT / "data/research/v2/company_research.json"
TZ = ZoneInfo("Asia/Shanghai")
MAX_PER_DRIVER = 5


def load(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def risk_warning(name: str) -> bool:
    text = str(name or "").upper()
    return "ST" in text or "退" in text


def main() -> int:
    drivers = load(DRIVERS, {})
    earnings = load(EARNINGS, {})
    registry = load(REGISTRY, {})
    weekly = load(WEEKLY, {})
    latest = load(LATEST, {})
    quotes = latest.get("stocks", {})

    driver_map = {d["driver_id"]: d for d in drivers.get("drivers", []) if d.get("active")}
    weekly_map = {
        str(x.get("code") or "").zfill(6): x
        for x in weekly.get("candidates", [])
        if x.get("status") != "移除" and x.get("earnings_direction") in {"up", "inflection_up"}
    }
    anomaly_map = earnings.get("screen_results") or {}
    anomaly_codes = set(earnings.get("candidate_codes") or [])

    exposure = {}
    for code, company in (registry.get("companies") or {}).items():
        code = str(code).zfill(6)
        for m in company.get("mappings", []):
            if m.get("status") != "active":
                continue
            did = f"{m.get('broad_industry_id')}::{m.get('subchain')}"
            if did not in driver_map:
                continue
            exposure.setdefault(code, []).append({
                "driver_id": did,
                "subchain": m.get("subchain"),
                "value_chain_link": m.get("value_chain_link"),
                "exposure_summary": m.get("exposure_summary"),
                "exposure_materiality": m.get("exposure_materiality"),
                "source": "company_industry_registry"
            })

    recall_codes = set(anomaly_codes) | set(weekly_map) | set(exposure)
    companies = {}
    rows = []

    for code in sorted(recall_codes):
        a = anomaly_map.get(code) or {}
        w = weekly_map.get(code)
        reg = (registry.get("companies") or {}).get(code) or {}
        name = a.get("name") or (w or {}).get("name") or reg.get("name") or (quotes.get(code) or {}).get("name") or code
        links = list(exposure.get(code) or [])
        linked_ids = {x["driver_id"] for x in links}
        if w:
            for hint in w.get("industry_t2_tag") or []:
                if hint in driver_map and hint not in linked_ids:
                    links.append({
                        "driver_id": hint,
                        "subchain": driver_map[hint].get("subchain"),
                        "value_chain_link": None,
                        "exposure_summary": "weekly deep-review mapping hint",
                        "exposure_materiality": "unknown",
                        "source": "weekly_deep_review_mapping_hint"
                    })
                    linked_ids.add(hint)

        metrics = dict(a.get("metrics") or {})
        profit = metrics.get("net_profit")
        ocfps = metrics.get("operating_cashflow_per_share")
        anomaly_status = a.get("status")
        flags = list(a.get("quality_flags") or [])
        rw = bool(a.get("risk_warning")) or risk_warning(name)
        if rw and "risk_warning_security" not in flags:
            flags.append("risk_warning_security")

        bridges = []
        invalidations = []
        for link in links:
            d = driver_map.get(link["driver_id"]) or {}
            if d.get("future_1_2q_transmission"):
                bridges.append({"source": "driver", "driver_id": link["driver_id"], "text": d.get("future_1_2q_transmission")})
            if d.get("invalidation_condition"):
                invalidations.append(d.get("invalidation_condition"))
        if w and w.get("forward_bridge"):
            bridges.append({"source": "weekly_deep_review", "driver_id": None, "text": w.get("forward_bridge")})
        if w and w.get("invalidation_condition"):
            invalidations.append(w.get("invalidation_condition"))

        severe_quality = rw or (profit is not None and profit <= 0)
        caution_quality = any(x in flags for x in {
            "negative_operating_cashflow_per_share",
            "profit_growth_far_outpaces_revenue_review_low_base_or_one_off"
        })
        weekly_text = str((w or {}).get("one_off_profit_impact") or "")
        weekly_recurring_support = bool(w and any(k in weekly_text for k in ("扣非", "主营", "不依赖", "核心盈利")))
        if weekly_recurring_support:
            recurring_status = "supported_by_weekly_deep_review"
        elif anomaly_status == "pass" and not severe_quality and not caution_quality:
            recurring_status = "proxy_quality_ok_deducted_profit_still_unverified"
        else:
            recurring_status = "review_required"

        forward_bridge_valid = bool(bridges)
        driver_review_required = not bool(links) and bool(a or w)
        if rw:
            research_status = "ineligible_low_risk"
        elif severe_quality:
            research_status = "quality_review_required"
        elif w and forward_bridge_valid and not caution_quality:
            research_status = "pass"
        elif anomaly_status == "pass" and links and forward_bridge_valid and not caution_quality:
            research_status = "pass"
        elif (anomaly_status in {"pass", "uncertain"} and links) or (w and forward_bridge_valid):
            research_status = "watch"
        elif anomaly_status in {"pass", "uncertain"}:
            research_status = "driver_review_required"
        elif links:
            research_status = "earnings_confirmation_required"
        else:
            research_status = "reject"

        source_flags = []
        if links:
            source_flags.append("driver_exposure")
        if code in anomaly_codes:
            source_flags.append("earnings_anomaly")
        if w:
            source_flags.append("weekly_full_market_recall")

        earnings_direction = (w or {}).get("earnings_direction")
        if not earnings_direction:
            if anomaly_status == "pass":
                earnings_direction = "up"
            elif anomaly_status == "uncertain":
                earnings_direction = "uncertain"
            else:
                earnings_direction = "unknown"

        score = float(a.get("triage_score") or 0.0)
        if w:
            score += 35
        if links:
            score += 15
        if any(x.get("exposure_materiality") == "material" for x in links):
            score += 10
        if ocfps is not None and ocfps >= 0:
            score += 5
        if caution_quality:
            score -= 15

        row = {
            "code": code,
            "name": name,
            "recall_sources": source_flags,
            "research_status": research_status,
            "low_risk_eligible": not rw,
            "risk_warning": rw,
            "driver_links": links,
            "driver_review_required": driver_review_required,
            "earnings_status": anomaly_status,
            "earnings_direction": earnings_direction,
            "triage_score": a.get("triage_score"),
            "metrics": metrics,
            "quality_flags": flags,
            "recurring_profit_status": recurring_status,
            "deducted_profit_verification_required": recurring_status != "supported_by_weekly_deep_review",
            "forward_bridge_valid": forward_bridge_valid,
            "forward_bridges": bridges,
            "weekly_evidence": list((w or {}).get("evidence") or []),
            "one_off_profit_review": (w or {}).get("one_off_profit_impact"),
            "invalidation_conditions": sorted(set(x for x in invalidations if x)),
            "research_priority_score": round(score, 3),
            "production_evidence_ready": bool(research_status == "pass" and weekly_recurring_support and forward_bridge_valid),
            "method_note": "Shadow company-research skeleton. Mechanical headline profit never substitutes for verified deducted/recurring profit; production eligibility remains stricter than shadow research pass."
        }
        companies[code] = row
        rows.append(row)

    def rank_key(x):
        status_rank = {"pass": 3, "watch": 2, "earnings_confirmation_required": 1}.get(x.get("research_status"), 0)
        return (-status_rank, -float(x.get("research_priority_score") or 0), x["code"])

    driver_shortlists = {}
    selected = set()
    for did in sorted(driver_map):
        linked = [x for x in rows if any(l.get("driver_id") == did for l in x.get("driver_links", [])) and x.get("research_status") in {"pass", "watch"}]
        linked.sort(key=rank_key)
        codes = [x["code"] for x in linked[:MAX_PER_DRIVER]]
        driver_shortlists[did] = codes
        selected.update(codes)

    for code, w in weekly_map.items():
        if (companies.get(code) or {}).get("research_status") in {"pass", "watch"}:
            selected.add(code)

    pass_codes = sorted(code for code, x in companies.items() if x.get("research_status") == "pass")
    watch_codes = sorted(code for code, x in companies.items() if x.get("research_status") == "watch")
    payload = {
        "schema_version": 1,
        "mode": "shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "reference_trade_date": earnings.get("reference_trade_date") or latest.get("trade_date"),
        "recall_policy": "driver_exposure UNION earnings_anomaly UNION weekly_full_market_recall",
        "recall_count": len(companies),
        "research_status_counts": {s: sum(1 for x in companies.values() if x.get("research_status") == s) for s in sorted(set(x.get("research_status") for x in companies.values()))},
        "research_pass_codes": pass_codes,
        "research_watch_codes": watch_codes,
        "driver_review_required_codes": sorted(code for code, x in companies.items() if x.get("driver_review_required")),
        "quality_review_required_codes": sorted(code for code, x in companies.items() if x.get("research_status") == "quality_review_required"),
        "production_evidence_ready_codes": sorted(code for code, x in companies.items() if x.get("production_evidence_ready")),
        "driver_shortlists": driver_shortlists,
        "selected_for_valuation_codes": sorted(selected),
        "companies": companies,
        "method_note": "The machine closes the research skeleton and exposes blockers. Missing deducted-profit proof or driver mapping becomes an explicit review state rather than a silent deletion."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "recall": len(companies),
        "pass": len(pass_codes),
        "watch": len(watch_codes),
        "valuation_queue": len(selected),
        "production_evidence_ready": len(payload["production_evidence_ready_codes"])
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
