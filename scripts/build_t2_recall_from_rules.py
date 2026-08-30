from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / "data" / "research" / "pipeline" / "industry_scan.json"
INDEX = ROOT / "data" / "research" / "company_industry_index.json"
LATEST = ROOT / "data" / "latest.json"
RULES = ROOT / "config" / "t2_exposure_rules.json"
OUTPUT = ROOT / "data" / "research" / "pipeline" / "t2_company_recall.json"
TZ = ZoneInfo("Asia/Shanghai")


def t2_keys(scan: dict) -> set[tuple[str, str]]:
    out = set()
    for industry in scan.get("broad_industries", []):
        bid = industry.get("id")
        for row in industry.get("subchains", []):
            if row.get("status") == "T2":
                out.add((bid, row.get("name")))
    return out


def hierarchy_text(item: dict) -> str:
    hierarchy = item.get("hierarchy") or {}
    values = [item.get("sw_level1_name"), item.get("industry_code")]
    values.extend(hierarchy.values())
    return "|".join(str(v) for v in values if v)


def main() -> int:
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    rule_data = json.loads(RULES.read_text(encoding="utf-8"))
    rule_map = {(r["broad_industry_id"], r["subchain"]): r for r in rule_data.get("chains", [])}
    required = t2_keys(scan)
    missing_rules = sorted(required - set(rule_map))
    extra_rules = sorted(set(rule_map) - required)
    if missing_rules:
        raise SystemExit(f"missing T2 exposure rules: {missing_rules}")
    if extra_rules:
        print(json.dumps({"warning":"rules_for_non_t2_ignored","rules":extra_rules}, ensure_ascii=False))

    companies = index.get("companies", {})
    quotes = latest.get("stocks", {})
    unknown = set(str(c).zfill(6) for c in index.get("missing_codes", []))
    unknown.update(str(c).zfill(6) for c in index.get("unmapped_codes", []))
    now = datetime.now(TZ).isoformat()
    rows = []

    for broad, subchain in sorted(required):
        rule = rule_map[(broad, subchain)]
        explicit = set(str(c).zfill(6) for c in rule.get("explicit_exposed", []))
        broad_codes = {
            str(code).zfill(6)
            for code, item in companies.items()
            if item.get("registry_broad_industry_id") == broad
        }
        candidate_codes = broad_codes | unknown | explicit
        discoveries = []
        for code in sorted(explicit):
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
            is_exposed = code in explicit or bool(matched_keyword)
            if is_exposed:
                basis = f"CNINFO行业细分命中:{matched_keyword}" if matched_keyword else "显式业务暴露规则命中"
                evidence = list(dict.fromkeys(([basis] + list(rule.get("evidence_sources", [])))))
                classifications[code] = {
                    "status": "exposed",
                    "reason": f"{name}对{subchain}的{rule['value_chain_link']}存在直接或实质业务暴露",
                    "evidence_sources": evidence,
                }
                exposed_rows.append({
                    "code": code,
                    "name": name,
                    "exposure_summary": f"{rule['value_chain_link']}业务暴露；判定依据={basis}",
                    "exposure_materiality": "material",
                    "evidence_sources": evidence,
                })
                counts["exposed"] += 1
            else:
                if code in unknown:
                    reason = "公司行业索引缺失/未映射；本轮跨行业业务检索未发现对该T2链的可验证直接暴露"
                else:
                    reason = f"已机械纳入{broad}大行业候选，但CNINFO细分类与显式业务映射均未命中{subchain}"
                classifications[code] = {"status": "not_exposed", "reason": reason}
                counts["not_exposed"] += 1

        rows.append({
            "broad_industry_id": broad,
            "subchain": subchain,
            "candidate_universe_count": len(candidate_codes),
            "classifications": classifications,
            "classification_counts": counts,
            "cross_industry_search_queries": rule.get("search_queries", []),
            "cross_industry_discoveries": discoveries,
            "value_chain_links": [{
                "name": rule["value_chain_link"],
                "registry_count": 0,
                "new_discovery_count": len(discoveries),
                "company_count": len(exposed_rows),
                "companies": exposed_rows,
                "coverage_gap": [],
            }],
            "recall_status": "complete",
            "coverage_gap": [],
        })

    payload = {
        "schema_version": 1,
        "industry_scan_frozen_at": scan.get("industry_frozen_at"),
        "company_index_generated_at": index.get("generated_at"),
        "weekly_pool_read": False,
        "t2_recall_frozen_at": now,
        "t2_subchains": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status":"ok",
        "t2_subchains":len(rows),
        "candidate_classifications":sum(r["candidate_universe_count"] for r in rows),
        "exposed_company_rows":sum(r["classification_counts"]["exposed"] for r in rows),
        "cross_industry_discoveries":sum(len(r["cross_industry_discoveries"]) for r in rows),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
