from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from company_index_fingerprint import company_index_fingerprint

ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / "data" / "research" / "pipeline" / "industry_scan.json"
INDEX = ROOT / "data" / "research" / "company_industry_index.json"
REGISTRY = ROOT / "data" / "research" / "company_industry_registry.json"
LATEST = ROOT / "data" / "latest.json"
RULES = ROOT / "config" / "t2_exposure_rules.json"
OUTPUT = ROOT / "data" / "research" / "pipeline" / "t2_company_recall.json"
TZ = ZoneInfo("Asia/Shanghai")


def scan_status_map(scan: dict) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for industry in scan.get("broad_industries", []):
        bid = industry.get("id")
        for row in industry.get("subchains", []):
            name = row.get("name")
            if bid and name:
                out[(bid, name)] = str(row.get("status") or "unconfirmed")
    return out


def hierarchy_text(item: dict) -> str:
    hierarchy = item.get("hierarchy") or {}
    values = [item.get("sw_level1_name"), item.get("industry_code")]
    values.extend(hierarchy.values())
    return "|".join(str(v) for v in values if v)


def active_registry_mappings(registry: dict, broad: str, subchain: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for raw_code, company in (registry.get("companies") or {}).items():
        code = str(raw_code).zfill(6)
        for mapping in company.get("mappings", []) or []:
            if (
                mapping.get("status") == "active"
                and mapping.get("broad_industry_id") == broad
                and mapping.get("subchain") == subchain
            ):
                out[code] = mapping
                break
    return out


def main() -> int:
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    rule_data = json.loads(RULES.read_text(encoding="utf-8"))
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}

    statuses = scan_status_map(scan)
    rule_map = {(r["broad_industry_id"], r["subchain"]): r for r in rule_data.get("chains", [])}
    delegation_map = {
        (r["broad_industry_id"], r["subchain"]): r
        for r in rule_data.get("t1_coverage_delegations", [])
    }
    t2_required = {key for key, status in statuses.items() if status == "T2"}
    t1_available = {key for key, status in statuses.items() if status == "T1" and key in rule_map}
    t1_delegated = {key for key, status in statuses.items() if status == "T1" and key in delegation_map}
    t1_missing_rules = sorted(
        key for key, status in statuses.items()
        if status == "T1" and key not in rule_map and key not in delegation_map
    )
    required = t2_required | t1_available

    missing_t2_rules = sorted(t2_required - set(rule_map))
    if missing_t2_rules:
        raise SystemExit(f"missing mandatory T2 exposure rules: {missing_t2_rules}")

    for key in sorted(t1_delegated):
        spec = delegation_map[key]
        target = (spec.get("delegate_broad_industry_id"), spec.get("delegate_subchain"))
        if target not in statuses:
            raise SystemExit(f"T1 delegation target missing from industry scan:{key}->{target}")
        if statuses.get(target) not in {"T1", "T2"}:
            raise SystemExit(f"T1 delegation target not active:{key}->{target}:{statuses.get(target)}")
        if target not in rule_map:
            raise SystemExit(f"T1 delegation target has no exposure rule:{key}->{target}")

    inactive_rules = sorted(key for key in rule_map if statuses.get(key) not in {"T1", "T2"})
    if inactive_rules:
        print(json.dumps({"warning": "rules_for_non_active_recall_chain_ignored", "rules": inactive_rules}, ensure_ascii=False))
    if t1_missing_rules:
        print(json.dumps({"warning": "t1_recall_rule_coverage_gap", "subchains": t1_missing_rules}, ensure_ascii=False))

    companies = index.get("companies", {})
    quotes = latest.get("stocks", {})
    unknown = set(str(c).zfill(6) for c in index.get("missing_codes", []))
    unknown.update(str(c).zfill(6) for c in index.get("unmapped_codes", []))
    now = datetime.now(TZ).isoformat()
    rows = []

    for broad, subchain in sorted(required):
        industry_status = statuses[(broad, subchain)]
        recall_mode = "direct_t2" if industry_status == "T2" else "conditional_t1"
        rule = rule_map[(broad, subchain)]
        explicit = set(str(c).zfill(6) for c in rule.get("explicit_exposed", []))
        registry_mappings = active_registry_mappings(registry, broad, subchain)
        registry_codes = set(registry_mappings)
        broad_codes = {
            str(code).zfill(6)
            for code, item in companies.items()
            if item.get("registry_broad_industry_id") == broad
        }
        candidate_codes = broad_codes | unknown | explicit | registry_codes
        discoveries = []
        for code in sorted(explicit - registry_codes):
            item = companies.get(code, {})
            indexed_broad = item.get("registry_broad_industry_id")
            if indexed_broad and indexed_broad != broad:
                discoveries.append({
                    "code": code,
                    "name": item.get("name") or quotes.get(code, {}).get("name") or code,
                    "value_chain_link": rule["value_chain_link"],
                    "exposure_summary": f"跨申万一级行业发现，对{rule['value_chain_link']}存在实质业务暴露",
                    "exposure_materiality": "material",
                    "evidence_sources": rule.get("evidence_sources", []),
                })

        classifications = {}
        exposed_rows = []
        counts = {"exposed": 0, "not_exposed": 0, "uncertain": 0}
        keywords = [str(x) for x in rule.get("hierarchy_keywords", []) if x]
        for code in sorted(candidate_codes):
            item = companies.get(code, {})
            quote = quotes.get(code, {})
            name = item.get("name") or quote.get("name") or code
            htext = hierarchy_text(item)
            matched_keyword = next((kw for kw in keywords if kw in htext), None)
            registry_mapping = registry_mappings.get(code)
            is_exposed = code in explicit or bool(matched_keyword) or bool(registry_mapping)
            if is_exposed:
                if registry_mapping:
                    basis = "active company registry mapping"
                    registry_evidence = list(registry_mapping.get("evidence_sources") or [])
                elif matched_keyword:
                    basis = f"CNINFO行业细分命中:{matched_keyword}"
                    registry_evidence = []
                else:
                    basis = "显式业务暴露规则命中"
                    registry_evidence = []
                evidence = list(dict.fromkeys(registry_evidence + [basis] + list(rule.get("evidence_sources", []))))
                classifications[code] = {
                    "status": "exposed",
                    "reason": f"{name}对{subchain}的{rule['value_chain_link']}存在直接或实质业务暴露",
                    "evidence_sources": evidence,
                    "industry_status": industry_status,
                    "recall_mode": recall_mode,
                }
                exposed_rows.append({
                    "code": code,
                    "name": name,
                    "exposure_summary": f"{rule['value_chain_link']}业务暴露；判定依据={basis}",
                    "exposure_materiality": "material",
                    "evidence_sources": evidence,
                    "industry_status": industry_status,
                    "recall_mode": recall_mode,
                })
                counts["exposed"] += 1
            else:
                if code in unknown:
                    reason = "公司行业索引缺失/未映射；本轮跨行业业务检索未发现对该召回链的可验证直接暴露"
                else:
                    reason = f"已机械纳入{broad}大行业候选，但CNINFO细分类、Registry与显式业务映射均未命中{subchain}"
                classifications[code] = {
                    "status": "not_exposed",
                    "reason": reason,
                    "industry_status": industry_status,
                    "recall_mode": recall_mode,
                }
                counts["not_exposed"] += 1

        coverage_gap = [] if exposed_rows else [f"no verified exposed company for active {industry_status} chain"]
        rows.append({
            "broad_industry_id": broad,
            "subchain": subchain,
            "industry_status": industry_status,
            "recall_mode": recall_mode,
            "candidate_universe_count": len(candidate_codes),
            "classifications": classifications,
            "classification_counts": counts,
            "cross_industry_search_queries": rule.get("search_queries", []),
            "cross_industry_discoveries": discoveries,
            "value_chain_links": [{
                "name": rule["value_chain_link"],
                "registry_count": len(registry_codes),
                "new_discovery_count": len(discoveries),
                "company_count": len(exposed_rows),
                "companies": exposed_rows,
                "coverage_gap": coverage_gap,
            }],
            "recall_status": "incomplete" if coverage_gap else "complete",
            "coverage_gap": coverage_gap,
        })

    delegated_rows = []
    for broad, subchain in sorted(t1_delegated):
        spec = delegation_map[(broad, subchain)]
        delegated_rows.append({
            "broad_industry_id": broad,
            "subchain": subchain,
            "industry_status": "T1",
            "coverage_mode": "delegated_to_more_specific_chain",
            "delegate_broad_industry_id": spec.get("delegate_broad_industry_id"),
            "delegate_subchain": spec.get("delegate_subchain"),
            "reason": spec.get("reason"),
            "residual_policy": spec.get("residual_policy"),
        })

    semantic_unchanged = (
        previous.get("industry_scan_frozen_at") == scan.get("industry_frozen_at")
        and previous.get("t2_subchains") == rows
        and previous.get("t1_delegated_coverage") == delegated_rows
        and previous.get("t1_rule_coverage_gaps") == [list(x) for x in t1_missing_rules]
        and bool(previous.get("t2_recall_frozen_at"))
    )
    frozen_at = previous.get("t2_recall_frozen_at") if semantic_unchanged else now

    payload = {
        "schema_version": 4,
        "industry_scan_frozen_at": scan.get("industry_frozen_at"),
        "company_index_generated_at": index.get("generated_at"),
        "company_index_fingerprint": company_index_fingerprint(index),
        "weekly_pool_read": False,
        "recall_policy": {
            "T2": "mandatory direct company recall; normal company earnings gate downstream",
            "T1": "conditional company recall when an explicit exposure rule exists; aggregate parent chains may delegate to a more specific active child chain; stricter company earnings confirmation and tighter representative cap downstream",
            "unconfirmed": "not automatically promoted; strong company earnings anomalies are audited as reverse triggers for subchain re-review"
        },
        "t1_rule_coverage_gaps": [list(x) for x in t1_missing_rules],
        "t1_delegated_coverage": delegated_rows,
        "t2_recall_frozen_at": frozen_at,
        "t2_subchains": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "schema_version": payload["schema_version"],
        "semantic_unchanged": semantic_unchanged,
        "company_index_fingerprint": payload["company_index_fingerprint"],
        "t2_recall_frozen_at": payload["t2_recall_frozen_at"],
        "recalled_subchains": len(rows),
        "direct_t2_subchains": sum(1 for r in rows if r["industry_status"] == "T2"),
        "conditional_t1_subchains": sum(1 for r in rows if r["industry_status"] == "T1"),
        "delegated_t1_subchains": len(delegated_rows),
        "t1_rule_coverage_gap_count": len(t1_missing_rules),
        "candidate_classifications": sum(r["candidate_universe_count"] for r in rows),
        "exposed_company_rows": sum(r["classification_counts"]["exposed"] for r in rows),
        "cross_industry_discoveries": sum(len(r["cross_industry_discoveries"]) for r in rows),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
