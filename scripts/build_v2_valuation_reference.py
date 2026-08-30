from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "data/research/v2/company_research.json"
LATEST = ROOT / "data/latest.json"
POLICY = ROOT / "config/valuation_policy_registry.json"
CYCLE_POLICY = ROOT / "config/cycle_valuation_policy.json"
LEGACY = ROOT / "data/research/pipeline/left_valuation_scan.json"
OUT = ROOT / "data/research/v2/valuation_reference.json"
TZ = ZoneInfo("Asia/Shanghai")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def detect_col(columns, contains):
    for c in columns:
        if contains in str(c):
            return c
    return None


def load_consensus(ak):
    df = ak.stock_profit_forecast_em()
    cols = list(df.columns)
    code_col = detect_col(cols, "代码")
    report_col = detect_col(cols, "研报数") or detect_col(cols, "机构")
    eps_cols = {}
    for c in cols:
        m = re.search(r"(20\d{2}).*预测.*每股收益", str(c))
        if m:
            eps_cols[int(m.group(1))] = c
    out = {}
    if not code_col:
        return out
    for _, r in df.iterrows():
        code = str(r.get(code_col, "")).zfill(6)
        if not (code.isdigit() and len(code) == 6):
            continue
        eps = {}
        for year, col in eps_cols.items():
            v = num(r.get(col))
            if v is not None and v > 0:
                eps[year] = v
        out[code] = {"report_count": int(num(r.get(report_col)) or 0) if report_col else 0, "eps": eps}
    return out


def load_pb(ak):
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        return {}
    cols = list(df.columns)
    code_col = detect_col(cols, "代码")
    pb_col = detect_col(cols, "市净率")
    out = {}
    if not code_col or not pb_col:
        return out
    for _, r in df.iterrows():
        code = str(r.get(code_col, "")).zfill(6)
        pb = num(r.get(pb_col))
        if code.isdigit() and len(code) == 6 and pb and pb > 0:
            out[code] = pb
    return out


def valid_range(v):
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v) and v[0] > 0 and v[1] >= v[0]


def policy_key(tags):
    text = " ".join(tags)
    mapping = [
        ("船舶制造", "shipbuilding"), ("重卡", "heavy_truck"), ("CXO", "cxo_cdmo"), ("CDMO", "cxo_cdmo"),
        ("特高压", "grid_equipment"), ("电网一次设备", "grid_equipment"), ("AI服务器", "ai_server"),
        ("高速光模块", "optical"), ("PCB/CCL", "pcb_ccl"), ("乘用车", "passenger_car"),
        ("商用车动力系统", "commercial_powertrain"), ("数据中心基础设施", "data_center_infrastructure"),
        ("航空主机", "aviation_oem"), ("半导体材料", "semiconductor_materials"), ("半导体设备", "semiconductor_equipment"),
        ("高速连接器/铜互连", "high_speed_connector"), ("工程机械", "construction_machinery"), ("船机动力", "marine_power"),
        ("创新药", "innovative_drug"), ("锂电池", "lithium_battery"), ("风电整机/零部件", "wind_equipment"),
        ("纺织制造", "textile_manufacturing"), ("核电", "nuclear_utility")
    ]
    for needle, key in mapping:
        if needle in text:
            return key
    return None


def choose_pb_band(policy, roe):
    for band in policy.get("roe_pb_bands", []):
        mx = num(band.get("roe_max"))
        rng = band.get("pb_range")
        if mx is not None and roe <= mx and valid_range(rng):
            return [float(rng[0]), float(rng[1])]
    return None


def main() -> int:
    import akshare as ak

    company = load(COMPANY)
    latest = load(LATEST)
    policies = load(POLICY)
    cycle_policy = load(CYCLE_POLICY)
    legacy = load(LEGACY)
    codes = company.get("selected_for_valuation_codes") or []
    cmap = company.get("companies") or {}
    stocks = latest.get("stocks") or {}
    legacy_map = {str(x.get("code") or "").zfill(6): x for x in legacy.get("companies", [])}
    cycle_tags = set((cycle_policy.get("subchain_policies") or {}).keys())
    consensus = load_consensus(ak)
    pb_map = load_pb(ak)
    year = datetime.now(TZ).year
    min_reports = int((policies.get("forecast_policy") or {}).get("minimum_report_count", 3))
    rows = {}
    counts = {"legacy_reference": 0, "v2_forward_pe_reference": 0, "v2_forward_pb_reference": 0, "cycle_reference_required": 0, "policy_required": 0, "consensus_required": 0, "market_data_required": 0}

    for code in codes:
        cr = cmap.get(code) or {}
        tags = [x.get("driver_id") for x in cr.get("driver_links", []) if x.get("driver_id")]
        name = cr.get("name") or (stocks.get(code) or {}).get("name") or code
        price = num((stocks.get(code) or {}).get("price"))
        old = legacy_map.get(code) or {}
        old_rng = old.get("business_fair_value_range") if valid_range(old.get("business_fair_value_range")) else old.get("value_anchor_range")
        if old.get("valuation_status") == "valid" and valid_range(old_rng):
            rows[code] = {
                "code": code, "name": name, "status": "available", "reference_source": "legacy_numeric_reference_only",
                "reference_range": [round(float(old_rng[0]), 2), round(float(old_rng[1]), 2)],
                "valuation_model": old.get("valuation_model"), "valuation_basis_unit": old.get("valuation_basis_unit"),
                "consensus_eps_current_year": old.get("consensus_eps_current_year"), "market_forward_pe_current_year": old.get("market_forward_pe_current_year"),
                "reasonable_multiple_reference": old.get("reasonable_multiple_range"), "independent_anchor_count": 1,
                "legacy_safe_buy_range_ignored": old.get("safe_buy_range"), "legacy_reasonable_buy_range_ignored": old.get("reasonable_buy_range")
            }
            counts["legacy_reference"] += 1
            continue

        if any(tag in cycle_tags for tag in tags):
            rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "cycle_normalized_reference_required", "independent_anchor_count": 0}
            counts["cycle_reference_required"] += 1
            continue

        override = (policies.get("company_overrides") or {}).get(code)
        text = " ".join(tags)
        financial = None
        if "证券" in text:
            financial = (policies.get("financial_policies") or {}).get("broker")
        elif "保险" in text:
            financial = (policies.get("financial_policies") or {}).get("insurance")
        key = policy_key(tags)
        business = (policies.get("business_policies") or {}).get(key) if key else None
        policy = override or financial or business
        if not policy:
            rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "versioned_valuation_policy_required", "independent_anchor_count": 0}
            counts["policy_required"] += 1
            continue

        cons = consensus.get(code) or {"report_count": 0, "eps": {}}
        reports = int(cons.get("report_count") or 0)
        eps_now = num((cons.get("eps") or {}).get(year))
        eps_next = num((cons.get("eps") or {}).get(year + 1))
        if reports < min_reports or not eps_now or eps_now <= 0:
            rows[code] = {"code": code, "name": name, "status": "review_required", "reason": f"consensus_required:reports={reports},eps={eps_now}", "independent_anchor_count": 0}
            counts["consensus_required"] += 1
            continue
        if not price or price <= 0:
            rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "current_price_required", "independent_anchor_count": 0}
            counts["market_data_required"] += 1
            continue

        if financial and not override:
            pb = pb_map.get(code)
            if not pb or pb <= 0:
                rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "market_pb_required", "independent_anchor_count": 0}
                counts["market_data_required"] += 1
                continue
            bvps = price / pb
            roe = eps_now / bvps
            mult = choose_pb_band(policy, roe)
            if not mult:
                rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "pb_band_required", "independent_anchor_count": 0}
                counts["policy_required"] += 1
                continue
            fair = [bvps * mult[0], bvps * mult[1]]
            rows[code] = {
                "code": code, "name": name, "status": "available", "reference_source": "v2_forward_pb_roe_reference",
                "reference_range": [round(fair[0], 2), round(fair[1], 2)], "valuation_model": policy.get("valuation_model"), "valuation_basis_unit": "PB",
                "consensus_eps_current_year": round(eps_now, 4), "consensus_eps_next_year": round(eps_next, 4) if eps_next else None,
                "reasonable_multiple_reference": mult, "market_pb": round(pb, 4), "forward_roe_current_year": round(roe, 4), "independent_anchor_count": 1
            }
            counts["v2_forward_pb_reference"] += 1
        else:
            mult = policy.get("multiple_range")
            if not valid_range(mult):
                rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "multiple_range_required", "independent_anchor_count": 0}
                counts["policy_required"] += 1
                continue
            fair = [eps_now * float(mult[0]), eps_now * float(mult[1])]
            rows[code] = {
                "code": code, "name": name, "status": "available", "reference_source": "v2_forward_pe_reference",
                "reference_range": [round(fair[0], 2), round(fair[1], 2)], "valuation_model": (override or {}).get("valuation_model") or (f"{key}_forward_pe" if key else "company_override_forward_pe"),
                "valuation_basis_unit": "PE", "consensus_eps_current_year": round(eps_now, 4), "consensus_eps_next_year": round(eps_next, 4) if eps_next else None,
                "market_forward_pe_current_year": round(price / eps_now, 2), "reasonable_multiple_reference": [float(mult[0]), float(mult[1])], "independent_anchor_count": 1
            }
            counts["v2_forward_pe_reference"] += 1

    payload = {
        "schema_version": 1, "mode": "shadow", "generated_at": datetime.now(TZ).isoformat(), "reference_trade_date": company.get("reference_trade_date"),
        "valuation_queue_count": len(codes), "available_count": sum(1 for x in rows.values() if x.get("status") == "available"),
        "review_required_count": sum(1 for x in rows.values() if x.get("status") != "available"), "source_counts": counts, "companies": rows,
        "method_note": "This builder creates one auditable numeric valuation reference across the V2 valuation queue. It never creates a formal buy zone; commodity/cycle names without an already-normalized reference remain review_required."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "queue": len(codes), "available": payload["available_count"], "review_required": payload["review_required_count"], "sources": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
