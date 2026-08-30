from __future__ import annotations

import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "data/research/v2/company_research.json"
LATEST = ROOT / "data/latest.json"
HEALTH = ROOT / "data/health.json"
POLICY = ROOT / "config/valuation_policy_registry.json"
CYCLE_POLICY = ROOT / "config/cycle_valuation_policy.json"
CYCLE_REGIME = ROOT / "config/cycle_regime_registry.json"
OUT = ROOT / "data/research/v2/valuation_reference.json"
TZ = ZoneInfo("Asia/Shanghai")
MAX_ANCHOR_AGE_DAYS = 7


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def pct(values, q):
    vals = sorted(float(x) for x in values if num(x) is not None)
    if not vals:
        return None
    pos = (len(vals) - 1) * max(0.0, min(1.0, float(q)))
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    w = pos - lo
    return vals[lo] * (1 - w) + vals[hi] * w


def parse_day(v):
    return date.fromisoformat(str(v)[:10])


def detect_col(columns, contains, exact=None):
    if exact:
        for c in columns:
            if str(c) == exact:
                return c
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


def parse_spot(df, source):
    if df is None or getattr(df, "empty", True):
        return {}
    cols = list(df.columns)
    code_col = detect_col(cols, "代码")
    pb_col = detect_col(cols, "市净率", exact="市净率")
    pe_col = detect_col(cols, "市盈率", exact="市盈率-动态")
    if not code_col:
        return {}
    out = {}
    for _, r in df.iterrows():
        code = str(r.get(code_col, "")).zfill(6)
        if code.isdigit() and len(code) == 6:
            out[code] = {"pb": num(r.get(pb_col)) if pb_col else None, "pe_dynamic": num(r.get(pe_col)) if pe_col else None, "source": source}
    return out


def load_spot(ak):
    out, errors = {}, []
    for source, fn_name in (("all_a", "stock_zh_a_spot_em"), ("sh_a", "stock_sh_a_spot_em"), ("sz_a", "stock_sz_a_spot_em")):
        fn = getattr(ak, fn_name, None)
        if fn is None:
            continue
        try:
            rows = parse_spot(fn(), source)
        except Exception as exc:
            errors.append(f"{fn_name}:{type(exc).__name__}:{exc}")
            continue
        for code, row in rows.items():
            prev = out.setdefault(code, row)
            if not prev.get("pb") and row.get("pb"):
                prev["pb"] = row["pb"]; prev["source"] = source
            if not prev.get("pe_dynamic") and row.get("pe_dynamic"):
                prev["pe_dynamic"] = row["pe_dynamic"]
    return out, errors


def valid_range(v):
    return isinstance(v, list) and len(v) == 2 and all(num(x) is not None for x in v) and float(v[0]) > 0 and float(v[1]) >= float(v[0])


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
        mx = num(band.get("roe_max")); rng = band.get("pb_range")
        if mx is not None and roe <= mx and valid_range(rng):
            return [float(rng[0]), float(rng[1])]
    return None


def cycle_policy_for(tags, code, cfg):
    sub = cfg.get("subchain_policies") or {}
    matched = next((t for t in tags if t in sub), None)
    if not matched:
        return None, None
    policy = dict(sub[matched])
    override = (cfg.get("company_overrides") or {}).get(code) or {}
    policy.update(override)
    return matched, policy


def regime_for(tag, code, cfg):
    base = dict((cfg.get("subchains") or {}).get(tag) or {})
    base.update((cfg.get("company_overrides") or {}).get(code) or {})
    return base or None


def fetch_anchor(ak, symbol, reference_trade_date, neutral_window, minimum_sessions):
    df = ak.futures_zh_daily_sina(symbol=symbol)
    if df is None or df.empty:
        raise RuntimeError(f"empty_futures:{symbol}")
    cols = list(df.columns)
    close_col = next((c for c in cols if str(c).lower() == "close"), None)
    date_col = next((c for c in cols if str(c).lower() == "date"), None)
    if close_col is None or date_col is None:
        raise RuntimeError(f"futures_columns_missing:{symbol}")
    pairs = [(str(r.get(date_col))[:10], num(r.get(close_col))) for _, r in df.iterrows()]
    pairs = [(d, v) for d, v in pairs if v is not None and v > 0]
    if len(pairs) < minimum_sessions:
        raise RuntimeError(f"futures_history_insufficient:{symbol}:{len(pairs)}")
    last_date = pairs[-1][0]
    age = (parse_day(reference_trade_date) - parse_day(last_date)).days
    if age < -1 or age > MAX_ANCHOR_AGE_DAYS:
        raise RuntimeError(f"stale_futures:{symbol}:{last_date}:{age}")
    vals = [v for _, v in pairs]
    neutral = vals[-min(neutral_window, len(vals)):]
    med = pct(neutral, 0.5)
    current = vals[-1]
    ma60 = sum(vals[-60:]) / min(60, len(vals))
    return {"symbol": symbol, "last_date": last_date, "age_days": age, "current": current, "ma60": ma60, "neutral_median": med, "current_to_neutral": current / med, "current_to_ma60": current / ma60}


def calendar_forward_eps(eps_now, eps_next, now):
    current_w = max(0.0, min(1.0, (12 - now.month) / 12.0))
    next_w = 1.0 - current_w
    return eps_now * current_w + eps_next * next_w, current_w, next_w


def build_cycle_reference(code, name, price, tags, cons, cfg, regimes, reference_trade_date, ak, anchor_cache, anchor_errors, now):
    tag, policy = cycle_policy_for(tags, code, cfg)
    if not tag:
        return None
    reports = int(cons.get("report_count") or 0)
    eps_now = num((cons.get("eps") or {}).get(now.year))
    eps_next = num((cons.get("eps") or {}).get(now.year + 1))
    min_reports = int((cfg.get("forward_earnings_policy") or {}).get("minimum_report_count", 3))
    if reports < min_reports or not eps_now or not eps_next:
        return {"code": code, "name": name, "status": "review_required", "reason": f"cycle_consensus_required:reports={reports},eps_now={eps_now},eps_next={eps_next}", "route": "cycle", "cycle_tag": tag, "independent_anchor_count": 0}
    regime = regime_for(tag, code, regimes)
    if not regime:
        return {"code": code, "name": name, "status": "review_required", "reason": "cycle_regime_required", "route": "cycle", "cycle_tag": tag, "independent_anchor_count": 0}
    reviewed = str(regimes.get("reviewed_at") or "")[:10]
    max_age = int(regimes.get("max_review_age_days", 45))
    age = (parse_day(reference_trade_date) - parse_day(reviewed)).days if reviewed else 999
    if age > max_age or age < -7:
        return {"code": code, "name": name, "status": "review_required", "reason": f"cycle_regime_stale:{age}", "route": "cycle", "cycle_tag": tag, "independent_anchor_count": 0}
    factors = regime.get("bear_base_bull_earnings_factor") or [0.85, 0.95, 1.05]
    mult = regime.get("multiple_range_by_regime") or policy.get("fallback_multiple_range")
    if not (isinstance(factors, list) and len(factors) == 3 and valid_range(mult)):
        return {"code": code, "name": name, "status": "review_required", "reason": "cycle_policy_invalid", "route": "cycle", "cycle_tag": tag, "independent_anchor_count": 0}
    anchors = policy.get("anchors") or []
    normalization = 1.0
    anchor_rows = []
    normalized_basis = None
    if anchors:
        neutral_cfg = cfg.get("neutral_commodity_policy") or {}
        neutral_window = int(neutral_cfg.get("window_sessions", 504))
        minimum = int(neutral_cfg.get("minimum_sessions", 252))
        weighted_delta = 0.0
        missing = []
        for a in anchors:
            symbol = a.get("symbol")
            if symbol not in anchor_cache and symbol not in anchor_errors:
                try:
                    anchor_cache[symbol] = fetch_anchor(ak, symbol, reference_trade_date, neutral_window, minimum)
                except Exception as exc:
                    anchor_errors[symbol] = f"{type(exc).__name__}:{exc}"
            if symbol in anchor_errors:
                missing.append(symbol); continue
            m = anchor_cache[symbol]
            weight = float(a.get("weight", 1.0)); direction = float(a.get("direction", 1.0))
            weighted_delta += weight * (m["current_to_neutral"] - 1.0) * direction
            anchor_rows.append({**m, "weight": weight, "direction": direction})
        if missing:
            return {"code": code, "name": name, "status": "review_required", "reason": f"cycle_anchor_fetch_failed:{missing}", "route": "cycle", "cycle_tag": tag, "independent_anchor_count": 0}
        f12, w0, w1 = calendar_forward_eps(eps_now, eps_next, now)
        sensitivity = float(policy.get("earnings_sensitivity", 0.8))
        windfall = max(0.0, weighted_delta)
        raw = 1.0 / (1.0 + windfall * sensitivity)
        normalization = max(float(neutral_cfg.get("min_normalization_factor", 0.70)), min(1.0, raw))
        normalized_basis = f12 * normalization
        base_eps = normalized_basis * float(factors[1])
        earnings_method = "forward12m_neutral_commodity_then_regime"
        forward_weights = {"current_year": round(w0, 4), "next_year": round(w1, 4)}
    else:
        downside_guard = min(eps_now, eps_next)
        structural = float(policy.get("anchorless_normalization_haircut", 1.0))
        base_regime = float(factors[1])
        # Single conservative cycle factor: avoid structural haircut × regime haircut double counting.
        single_factor = min(structural, base_regime, 1.0)
        normalized_basis = downside_guard * single_factor
        base_eps = normalized_basis
        normalization = single_factor
        earnings_method = "current_year_primary_next_year_downside_guard_single_cycle_factor"
        forward_weights = None
    lo, hi = float(mult[0]), float(mult[1])
    fair = [base_eps * lo, base_eps * hi]
    bear_eps = normalized_basis * float(factors[0])
    bull_eps = normalized_basis * float(factors[2])
    scenario = [bear_eps * lo, bull_eps * hi]
    return {
        "code": code, "name": name, "status": "available", "reference_source": "v2_cycle_normalized_fundamental_anchor",
        "route": "cycle", "cycle_tag": tag, "reference_range": [round(fair[0], 2), round(fair[1], 2)],
        "scenario_fair_value_range": [round(scenario[0], 2), round(scenario[1], 2)], "valuation_model": "v2_cycle_normalized_fundamental",
        "valuation_basis_unit": "PE", "consensus_eps_current_year": round(eps_now, 4), "consensus_eps_next_year": round(eps_next, 4),
        "forecast_report_count": reports, "normalized_forward_eps": round(base_eps, 4), "normalization_factor": round(normalization, 4),
        "earnings_normalization_method": earnings_method, "forward_eps_weights": forward_weights,
        "reasonable_multiple_reference": [lo, hi], "market_forward_pe_current_year": round(price / eps_now, 2) if price else None,
        "commodity_anchors": anchor_rows, "cycle_regime": regime.get("regime"), "cycle_regime_summary": regime.get("summary"),
        "buy_band_policy": {"safe_to_fair_floor": policy.get("safe_to_fair_floor"), "reasonable_to_fair_floor": policy.get("reasonable_to_fair_floor")},
        "independent_anchor_count": 1,
        "method_note": "Cycle anchor normalizes earnings first. Anchorless cycles use one conservative cycle factor=min(structural haircut, base regime factor), not multiplicative repeated haircuts."
    }


def main() -> int:
    import akshare as ak

    company = load(COMPANY); latest = load(LATEST); health = load(HEALTH)
    policies = load(POLICY); cycle_cfg = load(CYCLE_POLICY); regimes = load(CYCLE_REGIME)
    codes = company.get("selected_for_valuation_codes") or []
    cmap = company.get("companies") or {}; stocks = latest.get("stocks") or {}
    consensus = load_consensus(ak); spot, spot_errors = load_spot(ak)
    now = datetime.now(TZ); year = now.year
    reference_trade_date = str(health.get("trade_date") or latest.get("trade_date") or "")[:10]
    min_reports = int((policies.get("forecast_policy") or {}).get("minimum_report_count", 3))
    rows = {}; anchor_cache = {}; anchor_errors = {}
    counts = {"v2_forward_pe_reference": 0, "v2_forward_pb_reference": 0, "v2_cycle_reference": 0, "policy_required": 0, "consensus_required": 0, "market_data_required": 0, "cycle_review_required": 0}

    for code in codes:
        cr = cmap.get(code) or {}
        tags = [x.get("driver_id") for x in cr.get("driver_links", []) if x.get("driver_id")]
        name = cr.get("name") or (stocks.get(code) or {}).get("name") or code
        price = num((stocks.get(code) or {}).get("price"))
        cons = consensus.get(code) or {"report_count": 0, "eps": {}}

        cycle_row = build_cycle_reference(code, name, price, tags, cons, cycle_cfg, regimes, reference_trade_date, ak, anchor_cache, anchor_errors, now)
        if cycle_row is not None:
            rows[code] = cycle_row
            if cycle_row.get("status") == "available": counts["v2_cycle_reference"] += 1
            else: counts["cycle_review_required"] += 1
            continue

        override = (policies.get("company_overrides") or {}).get(code)
        text = " ".join(tags)
        financial = None
        if "证券" in text: financial = (policies.get("financial_policies") or {}).get("broker")
        elif "保险" in text: financial = (policies.get("financial_policies") or {}).get("insurance")
        key = policy_key(tags); business = (policies.get("business_policies") or {}).get(key) if key else None
        policy = override or financial or business
        if not policy:
            rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "versioned_valuation_policy_required", "independent_anchor_count": 0}; counts["policy_required"] += 1; continue
        reports = int(cons.get("report_count") or 0); eps_now = num((cons.get("eps") or {}).get(year)); eps_next = num((cons.get("eps") or {}).get(year + 1))
        if reports < min_reports or not eps_now or eps_now <= 0:
            rows[code] = {"code": code, "name": name, "status": "review_required", "reason": f"consensus_required:reports={reports},eps={eps_now}", "independent_anchor_count": 0}; counts["consensus_required"] += 1; continue
        if not price or price <= 0:
            rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "current_price_required", "independent_anchor_count": 0}; counts["market_data_required"] += 1; continue

        if financial and not override:
            market = spot.get(code) or {}; pb = num(market.get("pb"))
            if not pb or pb <= 0:
                rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "market_pb_required", "independent_anchor_count": 0}; counts["market_data_required"] += 1; continue
            bvps = price / pb; roe_now = eps_now / bvps; roe_next = eps_next / bvps if eps_next else None
            low_risk_roe = min(roe_now, roe_next) if roe_next is not None else roe_now
            mult = choose_pb_band(policy, low_risk_roe)
            if not mult:
                rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "pb_band_required", "independent_anchor_count": 0}; counts["policy_required"] += 1; continue
            fair = [bvps * mult[0], bvps * mult[1]]
            rows[code] = {"code": code, "name": name, "status": "available", "reference_source": "v2_forward_pb_roe_fundamental_anchor", "route": "financial", "reference_range": [round(fair[0], 2), round(fair[1], 2)], "valuation_model": policy.get("valuation_model"), "valuation_basis_unit": "PB", "consensus_eps_current_year": round(eps_now, 4), "consensus_eps_next_year": round(eps_next, 4) if eps_next else None, "forecast_report_count": reports, "book_value_per_share_proxy": round(bvps, 4), "market_pb": round(pb, 4), "market_indicator_source": market.get("source"), "forward_roe_current_year": round(roe_now, 4), "forward_roe_next_year": round(roe_next, 4) if roe_next is not None else None, "low_risk_forward_roe": round(low_risk_roe, 4), "reasonable_multiple_reference": mult, "buy_band_policy": {"safe_to_fair_floor": policy.get("safe_to_fair_floor"), "reasonable_to_fair_floor": policy.get("reasonable_to_fair_floor")}, "independent_anchor_count": 1}
            counts["v2_forward_pb_reference"] += 1
        else:
            mult = policy.get("multiple_range")
            if not valid_range(mult):
                rows[code] = {"code": code, "name": name, "status": "review_required", "reason": "multiple_range_required", "independent_anchor_count": 0}; counts["policy_required"] += 1; continue
            fair = [eps_now * float(mult[0]), eps_now * float(mult[1])]
            entry_mult = policy.get("low_risk_multiple_range") if valid_range(policy.get("low_risk_multiple_range")) else None
            entry_ref = [eps_now * float(entry_mult[0]), eps_now * float(entry_mult[1])] if entry_mult else None
            rows[code] = {"code": code, "name": name, "status": "available", "reference_source": "v2_forward_pe_fundamental_anchor", "route": "business", "reference_range": [round(fair[0], 2), round(fair[1], 2)], "valuation_model": (override or {}).get("valuation_model") or (f"{key}_forward_pe" if key else "company_override_forward_pe"), "valuation_basis_unit": "PE", "consensus_eps_current_year": round(eps_now, 4), "consensus_eps_next_year": round(eps_next, 4) if eps_next else None, "forecast_report_count": reports, "market_forward_pe_current_year": round(price / eps_now, 2), "reasonable_multiple_reference": [float(mult[0]), float(mult[1])], "explicit_entry_multiple_range": [float(entry_mult[0]), float(entry_mult[1])] if entry_mult else None, "explicit_entry_reference_range": [round(entry_ref[0], 2), round(entry_ref[1], 2)] if entry_ref else None, "buy_band_policy": {"safe_to_fair_floor": policy.get("safe_to_fair_floor"), "reasonable_to_fair_floor": policy.get("reasonable_to_fair_floor")}, "independent_anchor_count": 1}
            counts["v2_forward_pe_reference"] += 1

    available = sum(1 for x in rows.values() if x.get("status") == "available")
    payload = {"schema_version": 2, "mode": "shadow", "generated_at": datetime.now(TZ).isoformat(), "reference_trade_date": reference_trade_date, "valuation_queue_count": len(codes), "available_count": available, "review_required_count": len(codes) - available, "source_counts": counts, "spot_source_errors": spot_errors, "commodity_anchor_errors": anchor_errors, "companies": rows, "method_note": "V2 first valuation anchor is rebuilt from V2 policies only; no V1 valuation result is consumed. Business uses forward PE, financials use forward ROE/PB, and cycle names use normalized earnings with explicit anti-double-haircut discipline."}
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "queue": len(codes), "available": available, "review_required": len(codes)-available, "sources": counts, "anchor_errors": anchor_errors}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
