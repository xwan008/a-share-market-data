from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
INDUSTRY = ROOT / "data/research/pipeline/industry_scan.json"
WEEKLY = ROOT / "data/research/weekly_fundamental_opportunity_pool.json"
OUT = ROOT / "data/research/v2/earnings_driver_scan.json"
TZ = ZoneInfo("Asia/Shanghai")


def load(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def confidence(evidence_for: list, evidence_against: list) -> str:
    positive = len(evidence_for)
    negative = len(evidence_against)
    if positive >= 2 and negative == 0:
        return "high"
    if positive >= 1 and positive >= negative:
        return "medium"
    return "low"


def main() -> int:
    industry = load(INDUSTRY, {})
    weekly = load(WEEKLY, {})
    drivers = []
    active_ids = []

    for broad in industry.get("broad_industries", []):
        broad_id = str(broad.get("id") or "")
        broad_name = str(broad.get("name") or broad_id)
        for sub in broad.get("subchains", []):
            name = str(sub.get("name") or "")
            if not broad_id or not name:
                continue
            evidence_for = list(sub.get("evidence_for") or [])
            evidence_against = list(sub.get("evidence_against") or [])
            direct_driver = sub.get("direct_profit_driver")
            leading = list(sub.get("leading_variables") or [])
            bridge = sub.get("future_1_2q_transmission")
            invalidation = sub.get("invalidation_condition")
            active = bool(direct_driver and evidence_for)
            if active:
                state = "improving" if not evidence_against else "mixed_improving"
            elif evidence_for:
                state = "evidence_present_driver_incomplete"
            else:
                state = "unconfirmed"
            driver_id = f"{broad_id}::{name}"
            row = {
                "driver_id": driver_id,
                "broad_industry_id": broad_id,
                "broad_industry_name": broad_name,
                "subchain": name,
                "state": state,
                "active": active,
                "confidence": confidence(evidence_for, evidence_against),
                "direct_profit_driver": direct_driver,
                "leading_variables": leading,
                "evidence_for": evidence_for,
                "evidence_against": evidence_against,
                "future_1_2q_transmission": bridge,
                "invalidation_condition": invalidation,
                "source": "pipeline/industry_scan.json",
                "legacy_tier_ignored": True,
            }
            drivers.append(row)
            if active:
                active_ids.append(driver_id)

    active_weekly = []
    for item in weekly.get("candidates", []):
        if item.get("status") == "移除":
            continue
        if item.get("earnings_direction") not in {"up", "inflection_up"}:
            continue
        active_weekly.append({
            "code": str(item.get("code") or "").zfill(6),
            "name": item.get("name"),
            "earnings_driver": item.get("earnings_driver"),
            "forward_bridge": item.get("forward_bridge"),
            "evidence": list(item.get("evidence") or []),
            "key_validation_metric": item.get("key_validation_metric"),
            "invalidation_condition": item.get("invalidation_condition"),
            "mapping_hints": list(item.get("industry_t2_tag") or []),
            "purpose": "reverse_discovery_or_company_specific_supplement; does not change driver eligibility",
        })

    drivers.sort(key=lambda x: (not x["active"], x["broad_industry_id"], x["subchain"]))
    payload = {
        "schema_version": 1,
        "mode": "shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "scan_as_of": industry.get("scan_as_of"),
        "reference_trade_date": weekly.get("market_trade_date"),
        "driver_policy": {
            "research_unit": "direct_profit_driver_chain",
            "active_rule": "direct_profit_driver exists AND at least one positive evidence item",
            "legacy_t1_t2_controls_eligibility": False,
            "confidence_enters_valuation_formula": False,
            "reverse_company_signal_auto_promotes_driver": False
        },
        "driver_count": len(drivers),
        "active_driver_count": len(active_ids),
        "active_driver_ids": sorted(active_ids),
        "drivers": drivers,
        "reverse_company_signals": active_weekly,
        "method_note": "V2 converts the existing evidence registry into driver-level research states without using T1/T2 as an admission cliff. Weekly company evidence is retained only as a reverse-discovery/supplement queue."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "drivers": len(drivers), "active_drivers": len(active_ids), "reverse_company_signals": len(active_weekly)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
