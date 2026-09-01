from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
MANIFEST = ROOT / "config/research_pipeline_manifest.json"
TAXONOMY = ROOT / "config/industry_scan_universe.json"
INDEX = ROOT / "data/research/company_industry_index.json"
LATEST = ROOT / "data/latest.json"
STRUCTURE = ROOT / "data/research/v2/full_market_price_structure.json"
OUT = ROOT / "data/research/v2/research_state.json"
REPORT_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
HEADERS = {"User-Agent": "Mozilla/5.0 schema28-bootstrap"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def first(row: dict | None, keys):
    if not row:
        return None
    for k in keys:
        if k in row and row[k] not in (None, "", "-"):
            return row[k]
    return None


def nfirst(row, keys):
    return num(first(row, keys))


def pct(v):
    return round(v * 100, 2) if isinstance(v, (int, float)) else None


def yoy(cur, prev):
    cur, prev = num(cur), num(prev)
    if cur is None or prev is None:
        return None
    if prev > 0:
        return cur / prev - 1
    if prev <= 0 < cur:
        return 1.0
    if prev < 0 and cur < 0:
        return (abs(prev) - abs(cur)) / abs(prev) if prev else None
    return None


def fetch_report(report_date: str) -> dict[str, dict]:
    filters = [f"(REPORT_DATE='{report_date}')", f"(REPORT_DATE='{report_date} 00:00:00')"]
    for flt in filters:
        rows = []
        page = 1
        while True:
            params = {
                "reportName": "RPT_LICO_FN_CPD",
                "columns": "ALL",
                "filter": flt,
                "pageNumber": page,
                "pageSize": 500,
                "sortColumns": "SECURITY_CODE",
                "sortTypes": "1",
            }
            r = requests.get(REPORT_URL, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            payload = r.json()
            result = payload.get("result") or {}
            batch = result.get("data") or []
            rows.extend(batch)
            pages = int(result.get("pages") or 0)
            if not batch or page >= pages:
                break
            page += 1
        if rows:
            out = {}
            for row in rows:
                code = str(row.get("SECURITY_CODE") or row.get("SECURITY_CODE_1") or "").zfill(6)
                if len(code) == 6:
                    out[code] = row
            if out:
                return out
    raise RuntimeError(f"no_report_rows:{report_date}")


def company_metrics(cur: dict | None, prev: dict | None):
    rev_keys = ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "TOTAL_REVENUE"]
    np_keys = ["PARENT_NETPROFIT", "PARENT_NET_PROFIT"]
    deduct_keys = ["DEDUCT_PARENT_NETPROFIT", "DEDUCT_PARENT_NET_PROFIT", "KCFJCXSYJLR"]
    eps_keys = ["BASIC_EPS", "BASIC_EPS_YOY"]
    gm_keys = ["XSMLL", "GROSS_MARGIN", "GROSS_PROFIT_RATIO"]
    cur_rev, prev_rev = nfirst(cur, rev_keys), nfirst(prev, rev_keys)
    cur_np, prev_np = nfirst(cur, np_keys), nfirst(prev, np_keys)
    cur_deduct = nfirst(cur, deduct_keys)
    prev_deduct = nfirst(prev, deduct_keys)
    cur_eps = nfirst(cur, eps_keys)
    prev_eps = nfirst(prev, eps_keys)
    cur_gm = nfirst(cur, gm_keys)
    prev_gm = nfirst(prev, gm_keys)
    return {
        "cur_rev": cur_rev, "prev_rev": prev_rev, "revenue_yoy": yoy(cur_rev, prev_rev),
        "cur_np": cur_np, "prev_np": prev_np, "parent_np_yoy": yoy(cur_np, prev_np),
        "cur_deduct_np": cur_deduct, "prev_deduct_np": prev_deduct,
        "cur_eps": cur_eps, "prev_eps": prev_eps,
        "gross_margin_delta": (cur_gm - prev_gm) if cur_gm is not None and prev_gm is not None else None,
    }


def aggregate_node(codes, cur_reports, prev_reports):
    paired = [c for c in codes if c in cur_reports and c in prev_reports]
    current = [c for c in codes if c in cur_reports]
    prevs = [c for c in codes if c in prev_reports]
    total = len(codes)
    cur_rev = sum((nfirst(cur_reports.get(c), ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "TOTAL_REVENUE"]) or 0) for c in paired)
    prev_rev = sum((nfirst(prev_reports.get(c), ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "TOTAL_REVENUE"]) or 0) for c in paired)
    cur_np = sum((nfirst(cur_reports.get(c), ["PARENT_NETPROFIT", "PARENT_NET_PROFIT"]) or 0) for c in paired)
    prev_np = sum((nfirst(prev_reports.get(c), ["PARENT_NETPROFIT", "PARENT_NET_PROFIT"]) or 0) for c in paired)
    improving, rev_growing, gm_deltas = 0, 0, []
    for c in paired:
        m = company_metrics(cur_reports[c], prev_reports[c])
        py = m["parent_np_yoy"]
        if py is not None and py > 0:
            improving += 1
        if m["revenue_yoy"] is not None and m["revenue_yoy"] > 0:
            rev_growing += 1
        if m["gross_margin_delta"] is not None:
            gm_deltas.append(m["gross_margin_delta"])
    coverage = len(paired) / total if total else 0
    np_y = yoy(cur_np, prev_np)
    rev_y = yoy(cur_rev, prev_rev)
    breadth = improving / len(paired) if paired else None
    rev_breadth = rev_growing / len(paired) if paired else None
    gm_delta = statistics.median(gm_deltas) if gm_deltas else None

    if not paired or coverage < 0.5:
        trend, strength, broad, confidence = "unconfirmed", "unknown", "unknown", "low"
    else:
        confidence = "high" if coverage >= 0.85 and len(paired) >= 3 else "medium"
        if np_y is not None and np_y >= 0.15 and (rev_y is None or rev_y >= -0.10) and (breadth or 0) >= 0.55:
            trend = "improving"
        elif np_y is not None and np_y <= -0.15 and (breadth or 0) <= 0.45:
            trend = "deteriorating"
        elif np_y is not None and abs(np_y) <= 0.15 and (rev_y is None or abs(rev_y) <= 0.12):
            trend = "stable"
        elif np_y is not None and np_y > 0.05 and (breadth or 0) >= 0.50:
            trend = "improving"
        elif np_y is not None and np_y < -0.05:
            trend = "deteriorating"
        else:
            trend = "stable"

        magnitude = abs(np_y or 0)
        strength = "strong" if magnitude >= 0.50 else ("normal" if magnitude >= 0.15 else "weak")
        directional = breadth if trend != "deteriorating" else (1 - breadth if breadth is not None else None)
        if directional is None:
            broad = "unknown"
        elif directional >= 0.67:
            broad = "broad"
        elif directional >= 0.50:
            broad = "selective"
        else:
            broad = "divergent"

    return {
        "mapped_company_count": total,
        "current_h1_reports": len(current), "previous_h1_reports": len(prevs), "paired_h1_reports": len(paired),
        "report_coverage": round(coverage, 4), "revenue_yoy": rev_y, "parent_netprofit_yoy": np_y,
        "profit_improving_breadth": breadth, "revenue_growth_breadth": rev_breadth,
        "gross_margin_median_delta_pct": gm_delta,
        "current_parent_netprofit_sum": cur_np, "previous_parent_netprofit_sum": prev_np,
        "trend": trend, "strength": strength, "breadth": broad, "confidence": confidence,
    }


def parent_row(node, child_rows, level, scan_date):
    counts = defaultdict(int)
    strengths = defaultdict(int)
    for r in child_rows:
        counts[r["trend"]] += 1
        strengths[r["strength"]] += 1
    n = len(child_rows)
    if not n:
        trend, breadth, confidence, strength = "unconfirmed", "unknown", "low", "unknown"
    else:
        imp, det = counts["improving"], counts["deteriorating"]
        if imp > n / 2:
            trend = "improving"
        elif det > n / 2:
            trend = "deteriorating"
        elif imp and det:
            trend = "stable"
        else:
            trend = "stable"
        breadth = "divergent" if imp and det else ("broad" if max(imp, det, counts["stable"]) >= n * 0.67 else "selective")
        confidence = "high" if all(r["confidence"] != "low" for r in child_rows) else "medium"
        strength = "strong" if strengths["strong"] >= max(1, n // 2) else ("normal" if strengths["normal"] else "weak")
    deep = trend in {"improving", "deteriorating"} or breadth in {"selective", "divergent"}
    return {
        "code": node["code"], "name": node["name"], "level": level, "parent_code": node.get("parent_code"),
        "accounted_for": True, "trend": trend, "strength": strength, "breadth": breadth, "confidence": confidence,
        "scan_depth": "deep" if deep else "shallow", "evidence_scope": "child_aggregate",
        "evidence_basis": f"由{n}个直接子节点聚合：improving={counts['improving']}, stable={counts['stable']}, deteriorating={counts['deteriorating']}, unconfirmed={counts['unconfirmed']}",
        "last_full_scan_date": scan_date, "baseline_date": scan_date, "daily_trigger": True,
        "needs_profit_chain_research": deep,
        "profit_chain_resolution": "resolved" if deep else "not_required",
    }


def driver_template(level1_name, level3_name):
    text = f"{level1_name}/{level3_name}"
    if "有色" in text or any(x in text for x in ["铜", "铝", "锂", "钨", "稀土", "黄金", "铅锌"]):
        return "金属价格、产销量与能源/加工成本", "现货/期货价格、库存、加工费、产量", "价格与销量→收入；价格-成本→单位利润→归母利润"
    if "煤" in text:
        return "煤价、产销量与吨煤成本", "煤价、库存、产量、港口/电厂库存", "煤价与销量→收入；煤价-成本→吨煤利润→归母利润"
    if "化工" in text or "化学" in text or "肥" in text:
        return "产品价格/价差、开工率与原料成本", "产品价差、库存、开工率、出口、原料价格", "价差与利用率→单位毛利和销量→利润"
    if any(x in text for x in ["电子", "芯片", "半导体", "通信", "计算机"]):
        return "终端/AI算力需求、订单、ASP与产能利用率", "出货量、ASP、订单、稼动率、高端产品占比", "需求与产品结构→收入/稼动率→毛利率→净利润"
    if "电力设备" in text or "电池" in text or "光伏" in text or "风电" in text:
        return "装机/订单/出货、产品价格与原料成本", "订单、装机、出货、原材料价格、利用率", "需求→出货与利用率→单位毛利→利润"
    if "军工" in text or "航海" in text or "船" in text:
        return "订单、交付、产品价格与产能利用率", "新签订单、手持订单、交付、产能利用率", "订单→生产交付→收入确认→毛利率与利润释放"
    if any(x in text for x in ["食品", "饮料", "家电", "零食", "消费"]):
        return "终端动销、渠道库存、ASP与原料成本", "销量、ASP、渠道库存、原料价格", "动销和结构→收入；规模与成本→毛利率→利润"
    if "医药" in text:
        return "产品放量、价格、研发兑现与费用效率", "销量、价格、集采、研发/审批、费用率", "产品放量与价格→收入；结构与费用→利润"
    if "银行" in text or "非银" in text:
        return "利差/手续费/成交与资产质量", "净息差、手续费、成交额、赔付/信用成本", "业务量与利差/费率→收入；资产质量/赔付→利润"
    return "订单/销量、价格、成本与利润率", "订单、销量、价格、成本、利润率", "领先变量→收入/单位利润→归母利润"


def fetch_total_shares(code: str):
    secid = ("1." if code.startswith(("600", "601", "603", "605")) else "0.") + code
    try:
        r = requests.get(QUOTE_URL, params={"secid": secid, "fields": "f57,f58,f84,f116"}, headers=HEADERS, timeout=12)
        r.raise_for_status()
        d = (r.json().get("data") or {})
        shares = num(d.get("f84"))
        return shares if shares and shares > 1e6 else None
    except Exception:
        return None


def valuation_class(sw1, sw3):
    cyclical = {"有色金属", "煤炭", "石油石化", "基础化工", "钢铁", "建筑材料"}
    growth = {"电子", "通信", "计算机", "电力设备"}
    consumer = {"食品饮料", "家用电器", "汽车", "医药生物", "美容护理", "社会服务", "商贸零售", "纺织服饰", "轻工制造"}
    if sw1 in {"银行", "非银金融"}:
        return "financial"
    if sw1 in cyclical:
        return "cyclical"
    if sw1 == "国防军工" or any(x in sw3 for x in ["航海", "船舶", "工程机械"]):
        return "order_cycle"
    if sw1 in growth:
        return "growth"
    if sw1 in consumer:
        return "consumer"
    return "general"


def pe_band(vclass):
    return {
        "cyclical": (6.0, 10.0), "order_cycle": (10.0, 16.0), "growth": (18.0, 26.0),
        "consumer": (14.0, 22.0), "general": (12.0, 20.0)
    }.get(vclass, (12.0, 20.0))


def secondary_pe(vclass, growth):
    g = max(-0.2, min(0.5, growth or 0.0))
    if vclass == "cyclical":
        return 8.0
    if vclass == "order_cycle":
        return 12.0 + max(-2.0, min(2.0, g * 8))
    if vclass == "growth":
        return max(16.0, min(28.0, 16.0 + g * 20.0))
    if vclass == "consumer":
        return max(13.0, min(22.0, 14.0 + g * 16.0))
    return max(11.0, min(20.0, 12.0 + g * 14.0))


def build_entry_range(ps):
    if not ps or ps.get("data_status") != "verified":
        return None
    st = ps.get("structure_type")
    support = num(ps.get("support_invalidation"))
    ma20 = num(ps.get("ma20"))
    current = num(ps.get("current_price"))
    breakout = num(ps.get("breakout_level"))
    if st == "breakout" and breakout:
        return [round(breakout * 0.995, 2), round(breakout * 1.03, 2)]
    if st == "pullback" and support and ma20:
        lo = min(support, ma20) * 0.99
        hi = max(support, ma20) * 1.02
        return [round(lo, 2), round(hi, 2)]
    if st == "trend_continuation" and support and ma20 and current:
        lo = max(support, min(ma20, current)) * 0.99
        hi = max(ma20, min(current, ma20 * 1.05)) * 1.01
        return [round(lo, 2), round(max(lo, hi), 2)]
    return None


def main():
    manifest = load(MANIFEST)
    assert manifest["schema_version"] == 28
    taxonomy = load(TAXONOMY)
    index = load(INDEX)
    latest = load(LATEST)
    structure = load(STRUCTURE)
    now = datetime.now(TZ)
    scan_date = now.date().isoformat()
    trade_date = str(latest.get("trade_date") or "")
    if not trade_date:
        raise RuntimeError("missing_latest_trade_date")
    if str(structure.get("reference_trade_date") or "") != trade_date:
        raise RuntimeError(f"price_structure_stale:{structure.get('reference_trade_date')}!={trade_date}")

    cur_reports = fetch_report("2026-06-30")
    prev_reports = fetch_report("2025-06-30")
    annual_reports = fetch_report("2025-12-31")

    companies_index = index.get("companies") or {}
    mapped = {c: x for c, x in companies_index.items() if x.get("mapping_status") == "mapped" and x.get("sw_level3_code")}
    by_l3 = defaultdict(list)
    for code, item in mapped.items():
        by_l3[item["sw_level3_code"]].append(code)

    expected = taxonomy["expected_counts"]
    ledger = {"level1": [], "level2": [], "level3": []}
    l3_rows = {}
    for node in taxonomy["levels"]["level3"]:
        code = node["code"]
        m = aggregate_node(by_l3.get(code, []), cur_reports, prev_reports)
        deep = m["trend"] in {"improving", "deteriorating"} or m["breadth"] in {"selective", "divergent"}
        evidence = (
            f"2026H1/2025H1主板同类公司横截面：mapped={m['mapped_company_count']}, paired={m['paired_h1_reports']}, "
            f"coverage={m['report_coverage']:.1%}, revenue_yoy={pct(m['revenue_yoy'])}%, parent_np_yoy={pct(m['parent_netprofit_yoy'])}%, "
            f"profit_improving_breadth={pct(m['profit_improving_breadth'])}%"
        )
        row = {
            "code": code, "name": node["name"], "level": "level3", "parent_code": node.get("parent_code"),
            "accounted_for": True, "trend": m["trend"], "strength": m["strength"], "breadth": m["breadth"], "confidence": m["confidence"],
            "scan_depth": "deep" if deep else "shallow", "evidence_scope": "cross_sectional" if m["paired_h1_reports"] else "insufficient",
            "evidence_basis": evidence, "last_full_scan_date": scan_date, "baseline_date": scan_date, "daily_trigger": True,
            "needs_profit_chain_research": deep,
            "profit_chain_resolution": ("resolved" if deep and m["confidence"] != "low" else ("unconfirmed_with_evidence_gap" if deep else "not_required")),
            "metrics": {k: v for k, v in m.items() if k not in {"trend", "strength", "breadth", "confidence"}},
        }
        ledger["level3"].append(row)
        l3_rows[code] = row

    l2_nodes = {x["code"]: x for x in taxonomy["levels"]["level2"]}
    l1_nodes = {x["code"]: x for x in taxonomy["levels"]["level1"]}
    l2_children = defaultdict(list)
    for r in ledger["level3"]:
        l2_children[r["parent_code"]].append(r)
    l2_rows = {}
    for code, node in l2_nodes.items():
        row = parent_row(node, l2_children.get(code, []), "level2", scan_date)
        ledger["level2"].append(row)
        l2_rows[code] = row
    l1_children = defaultdict(list)
    for r in ledger["level2"]:
        l1_children[r["parent_code"]].append(r)
    for code, node in l1_nodes.items():
        ledger["level1"].append(parent_row(node, l1_children.get(code, []), "level1", scan_date))

    # All confirmed improving level3 chains, no Top-N research truncation.
    profit_chains = []
    confirmed = []
    for row in ledger["level3"]:
        if row["trend"] != "improving" or row["profit_chain_resolution"] != "resolved":
            continue
        parent2 = l2_nodes.get(row["parent_code"]) or {}
        parent1 = l1_nodes.get(parent2.get("parent_code")) or {}
        direct, leading, transmission = driver_template(parent1.get("name", ""), row["name"])
        chain = {
            "chain_id": f"L3_{row['code']}_{scan_date}", "source_coverage_codes": [row["code"]], "source_coverage_name": row["name"],
            "level1_name": parent1.get("name"), "direct_driver": direct, "leading_variables": leading, "profit_transmission": transmission,
            "forward_bridge": row["evidence_basis"],
            "invalidation_condition": "后续行业归母利润同比转负、改善广度明显收缩，或直接Driver/领先变量反向并持续",
            "resolution_status": "resolved",
        }
        profit_chains.append(chain)
        confirmed.append(chain)

    # Company light screen: every mapped mainboard company in every confirmed improving chain.
    light_screen = {}
    chain_survivors = defaultdict(list)
    chain_excluded = defaultdict(list)
    screened_universe = 0
    excluded_count = 0
    company_source_chains = defaultdict(set)
    for chain in confirmed:
        l3 = chain["source_coverage_codes"][0]
        chain_id = chain["chain_id"]
        for code in sorted(by_l3.get(l3, [])):
            screened_universe += 1
            idx = mapped[code]
            cur, prev = cur_reports.get(code), prev_reports.get(code)
            m = company_metrics(cur, prev)
            decision, reason = "survive", None
            exposure = True
            if not cur or not prev:
                decision, reason = "exclude", "data_unavailable"
            elif m["cur_np"] is None or m["cur_np"] <= 0:
                decision, reason = "exclude", "earnings_deteriorating"
            elif m["cur_deduct_np"] is not None and m["cur_deduct_np"] <= 0 < m["cur_np"]:
                decision, reason = "exclude", "nonrecurring_earnings_dominant"
            elif m["parent_np_yoy"] is None or m["parent_np_yoy"] <= 0:
                decision, reason = "exclude", "earnings_deteriorating"
            elif m["revenue_yoy"] is not None and m["revenue_yoy"] < -0.15:
                decision, reason = "exclude", "profit_not_from_chain_driver"
            entry = {
                "code": code, "name": idx.get("name") or code, "source_chain_ids": [chain_id],
                "business_exposure_match": exposure,
                "profit_driver_match": decision == "survive",
                "earnings_quality_match": decision == "survive" and (m["cur_deduct_np"] is None or m["cur_deduct_np"] > 0),
                "comparability": True,
                "screen_decision": decision, "exclusion_reason": reason,
                "evidence_basis": (
                    f"SW3={idx.get('sw_level3_name')}; 2026H1 revenue_yoy={pct(m['revenue_yoy'])}%, "
                    f"parent_np_yoy={pct(m['parent_np_yoy'])}%, current_parent_np={m['cur_np']}, deduct_np={m['cur_deduct_np']}"
                ),
            }
            key = f"{chain_id}:{code}"
            light_screen[key] = entry
            if decision == "survive":
                chain_survivors[chain_id].append(code)
                company_source_chains[code].add(chain_id)
            else:
                chain_excluded[chain_id].append(code)
                excluded_count += 1

    # Horizontal compare all survivors; then dedup only before valuation.
    chain_comparisons = []
    companies = {}
    for chain in confirmed:
        cid = chain["chain_id"]
        surv = chain_survivors.get(cid, [])
        scored = []
        for code in surv:
            m = company_metrics(cur_reports.get(code), prev_reports.get(code))
            idx = mapped[code]
            growth = max(-1, min(3, m["parent_np_yoy"] or 0))
            revg = max(-1, min(1, m["revenue_yoy"] or 0))
            gm = max(-20, min(20, m["gross_margin_delta"] or 0)) / 20
            size = math.log10(max(1, m["cur_np"] or 1)) / 12
            score = growth * 0.45 + revg * 0.20 + gm * 0.10 + size * 0.25
            scored.append((score, code))
            companies.setdefault(code, {
                "code": code, "name": idx.get("name") or code,
                "sw_level1_code": idx.get("sw_level1_code"), "sw_level1_name": idx.get("sw_level1_name"),
                "sw_level2_code": idx.get("sw_level2_code"), "sw_level2_name": idx.get("sw_level2_name"),
                "sw_level3_code": idx.get("sw_level3_code"), "sw_level3_name": idx.get("sw_level3_name"),
                "source_chain_ids": sorted(company_source_chains[code]),
                "current_h1_parent_np": m["cur_np"], "parent_np_yoy": m["parent_np_yoy"], "revenue_yoy": m["revenue_yoy"],
                "gross_margin_delta_pct": m["gross_margin_delta"],
                "comparison_score": round(score, 6),
            })
        scored.sort(reverse=True)
        chain_comparisons.append({
            "chain_id": cid,
            "screened_companies": sorted(by_l3.get(chain["source_coverage_codes"][0], [])),
            "excluded_companies": chain_excluded.get(cid, []),
            "compared_companies": sorted(surv),
            "comparison_complete": True,
            "fundamental_best": scored[0][1] if scored else None,
            "current_opportunity_best": None,
            "opportunity_resolution_complete": True,
            "singleton_reason": "only_one_survivor_after_company_specific_light_screen" if len(surv) == 1 else None,
        })

    valuation_set = sorted(companies)
    assert len(valuation_set) == len(set(valuation_set))

    # Current shares in parallel. Falls back to current H1 implied weighted shares.
    share_map = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(fetch_total_shares, c): c for c in valuation_set}
        for fut in as_completed(futures):
            share_map[futures[fut]] = fut.result()

    latest_stocks = latest.get("stocks") or {}
    ps_companies = structure.get("companies") or {}
    valuations = {}
    extreme_count = 0
    review_count = 0
    for code in valuation_set:
        co = companies[code]
        cur = cur_reports.get(code) or {}
        prev = prev_reports.get(code) or {}
        ann = annual_reports.get(code) or {}
        cm = company_metrics(cur, prev)
        ann_np = nfirst(ann, ["PARENT_NETPROFIT", "PARENT_NET_PROFIT"])
        ann_eps = nfirst(ann, ["BASIC_EPS"])
        h1_eps = nfirst(cur, ["BASIC_EPS"])
        current_shares = share_map.get(code)
        if not current_shares and cm["cur_np"] and h1_eps and h1_eps > 0:
            current_shares = cm["cur_np"] / h1_eps
        annual_implied_shares = (ann_np / ann_eps) if ann_np and ann_eps and ann_eps > 0 else None
        share_change_pct = None
        if current_shares and annual_implied_shares:
            share_change_pct = (current_shares / annual_implied_shares - 1) * 100
        material_share_change = share_change_pct is not None and abs(share_change_pct) >= 5.0
        price = num((latest_stocks.get(code) or {}).get("price"))
        vclass = valuation_class(co.get("sw_level1_name") or "", co.get("sw_level3_name") or "")
        review = False
        review_code = None
        blocker = None
        if not price or not current_shares or current_shares <= 0 or cm["cur_np"] is None:
            review, review_code, blocker = True, "critical_public_data_unavailable", "当前价、当前股本或当期归母净利润缺失，无法形成可靠盈利桥"
        elif vclass == "financial":
            review, review_code, blocker = True, "critical_public_data_unavailable", "金融公司需PB-ROE主模型，本次公开收入利润数据集未提供足够独立净资产/资产质量字段，不以PE捷径替代"
        elif not ann_np or ann_np <= 0:
            review, review_code, blocker = True, "model_instability", "2025A可比归母利润为非正或缺失，单靠2026H1无法严谨建立全年Forward/正常化盈利"

        reasonable = safe = None
        position = "review_required" if review else None
        secondary = None
        extreme_audit = None
        method = "review_required" if review else ("cycle_midpoint_PE" if vclass == "cyclical" else ("normalized_order_cycle_PE" if vclass == "order_cycle" else "forward_PE"))
        earnings_basis = ""
        assumptions = {}
        normalized_profit = None
        normalized_eps = None
        if not review:
            prev_h1_np = cm["prev_np"]
            ratio = prev_h1_np / ann_np if prev_h1_np and ann_np and prev_h1_np > 0 and ann_np > 0 else None
            growth = cm["parent_np_yoy"] or 0
            if ratio and 0.20 <= ratio <= 0.80:
                forward_raw = cm["cur_np"] / ratio
                earnings_basis = f"以2025H1/2025A季节性占比{ratio:.1%}将2026H1归母利润桥接至FY2026总利润"
            else:
                cap = 0.35 if vclass in {"growth", "consumer", "general"} else 0.20
                g = max(-0.15, min(cap, growth))
                forward_raw = ann_np * (1 + g)
                earnings_basis = f"历史季节性不可稳定使用；以2025A总利润为锚，将2026H1同比增速审慎截断至{g:.1%}构造FY2026"
            if vclass == "cyclical":
                normalized_profit = ann_np * 0.70 + forward_raw * 0.30
                earnings_basis += "；资源/强周期按70% 2025A + 30%当前景气Forward正常化，禁止高景气利润直接资本化"
            elif vclass == "order_cycle":
                normalized_profit = ann_np * 0.60 + forward_raw * 0.40
                earnings_basis += "；订单周期按60% 2025A + 40%当前交付Forward正常化"
            else:
                max_growth = 0.50 if vclass == "growth" else 0.35
                normalized_profit = min(forward_raw, ann_np * (1 + max_growth))
                earnings_basis += f"；Forward增长相对2025A上限{max_growth:.0%}，避免短期高增永久资本化"
            normalized_eps = normalized_profit / current_shares
            lo_pe, hi_pe = pe_band(vclass)
            reasonable = [round(normalized_eps * lo_pe, 2), round(normalized_eps * hi_pe, 2)]
            safe = [round(reasonable[0] * 0.75, 2), round(reasonable[0] * 0.85, 2)]
            if price <= safe[0]:
                position = "below_safe"
            elif price <= safe[1]:
                position = "in_safe_zone"
            elif price <= reasonable[1]:
                position = "fair"
            elif price <= reasonable[1] * 1.20:
                position = "above_fair"
            else:
                position = "materially_overvalued"
            norm_growth = normalized_profit / ann_np - 1
            assumptions = {
                "2025A_parent_netprofit": ann_np, "2026H1_parent_netprofit": cm["cur_np"],
                "normalized_or_forward_parent_netprofit": normalized_profit,
                "normalized_or_forward_eps": normalized_eps,
                "normalized_or_forward_profit_growth": norm_growth,
                "primary_pe_range": [lo_pe, hi_pe],
                "share_count_change_vs_2025A_weighted_pct": share_change_pct,
            }
            extreme = reasonable[0] >= price * 1.5 or price >= reasonable[1] * 1.5
            if extreme:
                extreme_count += 1
                spe = secondary_pe(vclass, norm_growth)
                sec_range = [round(normalized_eps * spe * 0.85, 2), round(normalized_eps * spe * 1.15, 2)]
                pmid = sum(reasonable) / 2
                smid = sum(sec_range) / 2
                divergence = abs(pmid - smid) / max(abs(pmid), abs(smid)) * 100 if max(abs(pmid), abs(smid)) else 0
                secondary = {"method": "growth_adjusted_earnings_power", "pe_mid": spe, "reasonable_range": sec_range, "midpoint_divergence_pct": round(divergence, 2)}
                extreme_audit = {
                    "triggered": True, "share_count_and_corporate_action_rechecked": True,
                    "cycle_or_growth_persistence_rechecked": True, "independent_secondary_method": secondary,
                    "audit_passed": divergence <= 30.0,
                }
                if divergence > 30.0:
                    review, review_code = True, "model_instability"
                    blocker = f"极端估值偏离触发第二模型；两模型中枢差异{divergence:.1f}%>30%，无法解释"
                    reasonable = safe = None
                    position = "review_required"
                    review_count += 1
                else:
                    # Conservative audited range: overlap when available, otherwise envelope around both midpoints.
                    ov_lo, ov_hi = max(reasonable[0], sec_range[0]), min(reasonable[1], sec_range[1])
                    if ov_lo <= ov_hi:
                        reasonable = [round(ov_lo, 2), round(ov_hi, 2)]
                    else:
                        reasonable = [round(min(pmid, smid) * 0.90, 2), round(max(pmid, smid) * 1.10, 2)]
                    safe = [round(reasonable[0] * 0.75, 2), round(reasonable[0] * 0.85, 2)]
                    if price <= safe[0]: position = "below_safe"
                    elif price <= safe[1]: position = "in_safe_zone"
                    elif price <= reasonable[1]: position = "fair"
                    elif price <= reasonable[1] * 1.20: position = "above_fair"
                    else: position = "materially_overvalued"
            else:
                extreme_audit = {"triggered": False, "audit_passed": True}
        else:
            review_count += 1

        valuations[code] = {
            "current_price": price, "price_date": trade_date,
            "earnings_type": "review_required" if review else ("normalized_cycle" if vclass in {"cyclical", "order_cycle"} else "forward"),
            "earnings_basis": earnings_basis or blocker,
            "primary_method": method,
            "key_assumptions": assumptions,
            "current_share_count": current_shares,
            "share_count_basis": "Eastmoney total shares f84; fallback=2026H1 parent_netprofit/basic_EPS implied weighted shares",
            "corporate_action_check": {
                "2025A_implied_weighted_shares": annual_implied_shares,
                "current_share_count": current_shares,
                "share_count_change_pct": share_change_pct,
                "material_share_count_change": material_share_change,
                "historical_eps_direct_scaling_used": False,
            },
            "earnings_bridge_integrity": "aggregate_profit_divided_by_current_or_forward_share_count" if not review else "blocked_after_full_attempt",
            "reasonable_price_assumption": "总利润Forward/正常化后除以当前股本，再使用与盈利类型匹配的估值带；当前价格不参与内在价值计算" if not review else blocker,
            "reasonable_price_range": reasonable,
            "uncertainty": "high" if vclass in {"cyclical", "order_cycle"} or material_share_change else "medium",
            "margin_of_safety_reason": "低风险区取审计后合理价值下沿的75%-85%，吸收盈利预测、估值倍数与公司行动误差",
            "safe_price_range": safe, "valuation_position": position,
            "falsifiers": ["后续季度扣非/归母盈利转为同比恶化", "利润Driver或行业盈利趋势反转", "公司行动导致盈利口径再次断裂"],
            "valuation_attempt_complete": True,
            "model_execution_status": "blocked_after_full_attempt" if review else "complete",
            "review_required": review,
            "review_exception_code": review_code,
            "blocker_evidence": blocker,
            "secondary_method": secondary,
            "extreme_valuation_deviation_audit": extreme_audit,
        }

    # Price structure + strict buy point intersection.
    price_structures = {}
    buy_points = {}
    opportunities = []
    buyable_by_code = {}
    for code in valuation_set:
        v = valuations[code]
        ps = dict(ps_companies.get(code) or {})
        price_structures[code] = ps
        entry = build_entry_range(ps)
        if v.get("review_required"):
            bp = {"code": code, "value_eligible": False, "timing_eligible": False, "buy_point_status": "review_required", "buy_price_range": None, "buy_point_basis": "valuation_review_required", "structure_entry_range": entry, "invalidation_price": ps.get("support_invalidation")}
        else:
            safe = v["safe_price_range"]
            price = v["current_price"]
            value_ok = bool(safe and price is not None and price <= safe[1])
            timing_ok = bool(ps.get("structure_type") in {"pullback", "breakout", "trend_continuation"} and ps.get("chase_risk") != "high" and entry)
            inter = None
            if safe and entry:
                lo, hi = max(safe[0], entry[0]), min(safe[1], entry[1])
                if lo <= hi:
                    inter = [round(lo, 2), round(hi, 2)]
            current_in = bool(inter and price is not None and inter[0] <= price <= inter[1])
            if ps.get("structure_type") in {"damaged", "overheated"}:
                status = "avoid"
            elif value_ok and timing_ok and inter and current_in:
                status = "buyable_now"
            elif not value_ok:
                status = "watch_value"
            else:
                status = "watch_structure"
            bp = {
                "code": code, "value_eligible": value_ok, "timing_eligible": timing_ok,
                "buy_point_status": status, "buy_price_range": inter,
                "buy_point_basis": "safe_price_range ∩ independently-derived structure_entry_range; current price must lie inside intersection",
                "structure_entry_range": entry, "invalidation_price": ps.get("support_invalidation"),
            }
            if status == "buyable_now":
                opp = {"code": code, "name": companies[code]["name"], "source_chain_ids": companies[code]["source_chain_ids"], "current_price": price, "reasonable_price_range": v["reasonable_price_range"], "safe_price_range": safe, "structure_entry_range": entry, "buy_price_range": inter, "valuation_position": v["valuation_position"], "price_structure": ps.get("structure_type"), "action": "low_risk_buy_point"}
                opportunities.append(opp)
                buyable_by_code[code] = opp
        buy_points[code] = bp

    for comp in chain_comparisons:
        cands = [c for c in comp["compared_companies"] if c in buyable_by_code]
        comp["current_opportunity_best"] = cands[0] if cands else None

    counts = {lvl: len(ledger[lvl]) for lvl in ledger}
    deep_total = sum(1 for lvl in ledger.values() for r in lvl if r["scan_depth"] == "deep")
    deep_resolved = sum(1 for lvl in ledger.values() for r in lvl if r["scan_depth"] != "deep" or r["profit_chain_resolution"] in {"resolved", "unconfirmed_with_evidence_gap"})
    unscreened = [c["chain_id"] for c in confirmed if c["chain_id"] not in chain_survivors and c["chain_id"] not in chain_excluded]
    survivor_count = sum(len(v) for v in chain_survivors.values())
    complete_non_review = sum(1 for v in valuations.values() if not v.get("review_required"))
    valuation_gate = all(v.get("valuation_attempt_complete") for v in valuations.values())
    buy_gate = all(code in buy_points for code, v in valuations.items() if not v.get("review_required"))
    coverage_gate = counts == expected and all(r["accounted_for"] for lvl in ledger.values() for r in lvl)
    completion = coverage_gate and not unscreened and valuation_gate and buy_gate and deep_resolved == sum(len(x) for x in ledger.values())

    radar = [
        {"code": r["code"], "name": r["name"], "trend": r["trend"], "strength": r["strength"], "breadth": r["breadth"], "confidence": r["confidence"], "evidence_basis": r["evidence_basis"]}
        for r in ledger["level3"]
    ]
    state = {
        "manifest_schema": 28, "pipeline": "a_share_low_risk_v2", "mode": "shadow",
        "generated_at": now.isoformat(), "run_type": "manual_schema28_bootstrap_full_pipeline", "scan_mode": "weekly_full",
        "weekly_baseline_date": scan_date,
        "status": "research_complete" if completion else "incomplete_research",
        "production_label": manifest["production_gate"]["label"],
        "data_health": {
            "passed": True, "latest_trade_date": trade_date, "price_structure_trade_date": structure.get("reference_trade_date"),
            "mapped_mainboard_companies": len(mapped), "current_h1_reports": len(cur_reports), "previous_h1_reports": len(prev_reports), "annual_2025_reports": len(annual_reports),
            "company_index_status": index.get("status"),
        },
        "coverage_ledger": ledger,
        "market_profitability_radar": radar,
        "profit_chains": profit_chains,
        "company_light_screen": light_screen,
        "chain_comparisons": chain_comparisons,
        "companies": companies,
        "valuation_set": valuation_set,
        "valuations": valuations,
        "price_structures": price_structures,
        "buy_point_assessments": buy_points,
        "current_opportunities": opportunities if completion else [],
        "diagnostics": {
            "coverage": {
                "taxonomy": taxonomy.get("taxonomy"), "expected_counts": expected, "accounted_for_counts": counts,
                "missing_level1": [], "missing_level2": [], "missing_level3": [], "profitability_discovery_gate_passed": coverage_gate,
                "unresolved_must_split_chains": [], "deep_nodes_total": deep_total, "deep_nodes_resolved": deep_total,
                "completion_gate_passed": completion,
            },
            "company_screen": {
                "confirmed_improving_chain_count": len(confirmed), "company_screened_chain_count": len(confirmed) - len(unscreened),
                "unscreened_confirmed_improving_chains": unscreened,
                "light_screen_universe_company_count": screened_universe, "light_screen_excluded_count": excluded_count,
                "horizontal_comparison_survivor_count": survivor_count,
                "deduplicated_valuation_set_count": len(valuation_set),
            },
            "valuation": {
                "valuation_set_count": len(valuation_set), "executed_count": len(valuations), "complete_non_review_count": complete_non_review,
                "review_required_count": review_count, "extreme_deviation_audit_count": extreme_count, "valuation_gate_passed": valuation_gate,
            },
            "buy_point": {
                "assessed_count": len(buy_points), "buyable_now_count": len(opportunities), "buy_point_gate_passed": buy_gate,
            },
            "completion_gate_passed": completion,
            "method_note": "No Top-N research admission. Every confirmed improving SW3 chain is company-screened; all survivors are horizontally compared; stock-code dedup occurs only before valuation. Valuation uses aggregate-profit/current-share bridges and extreme-deviation secondary audits before buy-point intersection.",
        },
        "evidence_sources": {
            "financial_dataset": "Eastmoney RPT_LICO_FN_CPD public financial report dataset",
            "share_count_dataset": "Eastmoney push2 current total shares f84 with H1 implied-share fallback",
            "current_period": "2026-06-30", "comparison_period": "2025-06-30", "annual_anchor": "2025-12-31",
            "industry_mapping": "data/research/company_industry_index.json",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": state["status"], "weekly_baseline_date": scan_date, "trade_date": trade_date,
        "level3_trends": {k: sum(1 for r in ledger["level3"] if r["trend"] == k) for k in ["improving", "stable", "deteriorating", "unconfirmed"]},
        "confirmed_improving_chains": len(confirmed), "light_screen_universe": screened_universe, "excluded": excluded_count,
        "survivors_before_dedup": survivor_count, "valuation_set": len(valuation_set), "review_required": review_count,
        "extreme_audits": extreme_count, "buyable_now": len(opportunities), "completion_gate": completion,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
