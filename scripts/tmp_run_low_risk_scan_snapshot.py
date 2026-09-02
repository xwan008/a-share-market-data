from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
IMPROVING_L1 = {
    "基础化工",
    "有色金属",
    "电子",
    "国防军工",
    "计算机",
    "通信",
    "非银金融",
    "煤炭",
    "石油石化",
}


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def taxonomy_maps():
    payload = read_json(ROOT / "config" / "industry_scan_universe.json", {})
    levels = payload.get("levels") or {}
    nodes = {}
    for level_name, rows in levels.items():
        level = int(level_name.replace("level", ""))
        for row in rows:
            nodes[str(row.get("code"))] = {
                "code": str(row.get("code")),
                "name": row.get("name"),
                "parent_code": row.get("parent_code"),
                "level": level,
            }

    def ancestry(code):
        cur = nodes.get(str(code))
        out = {}
        seen = set()
        while cur and cur["code"] not in seen:
            seen.add(cur["code"])
            out[cur["level"]] = cur
            cur = nodes.get(str(cur.get("parent_code") or ""))
        return out

    l3_map = {}
    for node in nodes.values():
        if node["level"] != 3:
            continue
        anc = ancestry(node["code"])
        l3_map[node["code"]] = {
            "level1_code": (anc.get(1) or {}).get("code"),
            "level1_name": (anc.get(1) or {}).get("name"),
            "level2_code": (anc.get(2) or {}).get("code"),
            "level2_name": (anc.get(2) or {}).get("name"),
            "level3_code": node["code"],
            "level3_name": node["name"],
        }
    return l3_map


def main():
    l3_map = taxonomy_maps()
    state_payload = read_json(DATA / "research" / "industry_state.json", {})
    states = state_payload.get("level3_profitability") or {}

    eligible_l3 = {}
    grouped = {}
    for code, st in states.items():
        meta = l3_map.get(str(code)) or {}
        l1 = meta.get("level1_name")
        if l1 not in IMPROVING_L1:
            continue
        trend = st.get("trend")
        breadth = st.get("breadth")
        eligible = trend == "improving" or (trend == "stable" and breadth == "divergent")
        if not eligible:
            continue
        row = {**meta, **st}
        eligible_l3[str(code)] = row
        grouped.setdefault(l1, []).append(row)

    for rows in grouped.values():
        rows.sort(key=lambda x: (x.get("level2_name") or "", x.get("level3_name") or ""))

    full_structure_payload = read_json(DATA / "research" / "full_market_price_structure.json", {})
    structure_stocks = (
        full_structure_payload.get("stocks")
        or full_structure_payload.get("companies")
        or full_structure_payload.get("structures")
        or {}
    )

    counts = {
        "shard_file_count": 0,
        "company_universe_count": 0,
        "industry_mapped_company_count": 0,
        "industry_unmapped_company_count": 0,
        "industry_eligible_company_count": 0,
        "industry_not_eligible_company_count": 0,
    }
    eligible_companies = []
    by_l3_company_count = {}

    shard_files = sorted((DATA / "shards").glob("*.json"))
    counts["shard_file_count"] = len(shard_files)
    for path in shard_files:
        shard = read_json(path, {"stocks": {}})
        for code, stock in (shard.get("stocks") or {}).items():
            counts["company_universe_count"] += 1
            mapped = (
                stock.get("industry_mapping_status") == "mapped"
                and bool(stock.get("sw_level3_code"))
                and bool(stock.get("sw_level3_name"))
            )
            if not mapped:
                counts["industry_unmapped_company_count"] += 1
                continue
            counts["industry_mapped_company_count"] += 1
            l3 = str(stock.get("sw_level3_code"))
            if l3 not in eligible_l3:
                counts["industry_not_eligible_company_count"] += 1
                continue
            counts["industry_eligible_company_count"] += 1
            by_l3_company_count[l3] = by_l3_company_count.get(l3, 0) + 1
            f = stock.get("fundamentals") or {}
            tr = stock.get("trend") or {}
            s60 = tr.get("structure_60d") or {}
            eligible_companies.append({
                "code": str(code),
                "name": stock.get("name"),
                "price": stock.get("price"),
                "confidence": stock.get("confidence"),
                "sw_level3_code": l3,
                "sw_level3_name": stock.get("sw_level3_name"),
                "industry_meta": eligible_l3[l3],
                "fundamentals": {
                    "valuation_date": f.get("valuation_date"),
                    "pe_dynamic": f.get("pe_dynamic"),
                    "pe_ttm": f.get("pe_ttm"),
                    "pb": f.get("pb"),
                    "market_cap": f.get("market_cap"),
                    "report_date": f.get("report_date"),
                    "roe": f.get("roe"),
                    "revenue_yoy": f.get("revenue_yoy"),
                    "net_profit_yoy": f.get("net_profit_yoy"),
                    "deduct_net_profit_yoy": f.get("deduct_net_profit_yoy"),
                    "operating_cashflow_per_share": f.get("operating_cashflow_per_share"),
                    "gross_margin": f.get("gross_margin"),
                    "revenue": f.get("revenue"),
                    "net_profit": f.get("net_profit"),
                    "basic_eps": f.get("basic_eps"),
                    "deduct_basic_eps": f.get("deduct_basic_eps"),
                    "deduct_basic_eps_prev_year": f.get("deduct_basic_eps_prev_year"),
                    "deduct_basic_eps_yoy": f.get("deduct_basic_eps_yoy"),
                    "warnings": f.get("warnings"),
                },
                "trend": {
                    "history_confidence": tr.get("history_confidence"),
                    "last_close": tr.get("last_close"),
                    "close_change_5d_pct": tr.get("close_change_5d_pct"),
                    "close_change_20d_pct": tr.get("close_change_20d_pct"),
                    "high_20d": tr.get("high_20d"),
                    "low_20d": tr.get("low_20d"),
                    "structure_60d": s60,
                },
                "full_market_price_structure": structure_stocks.get(str(code)),
            })

    assert counts["company_universe_count"] == counts["industry_mapped_company_count"] + counts["industry_unmapped_company_count"]
    assert counts["industry_mapped_company_count"] == counts["industry_eligible_company_count"] + counts["industry_not_eligible_company_count"]

    output = {
        "snapshot_kind": "temporary_current_run_only",
        "improving_level1": sorted(IMPROVING_L1),
        "industry_state_generated_at": state_payload.get("generated_at"),
        "eligible_level3_by_level1": grouped,
        "counts": counts,
        "eligible_level3_company_count": by_l3_company_count,
        "eligible_companies": eligible_companies,
    }
    out_path = ROOT / "tmp_low_risk_scan_snapshot.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "counts": counts,
        "eligible_level3_count": len(eligible_l3),
        "eligible_company_records": len(eligible_companies),
        "output": str(out_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
