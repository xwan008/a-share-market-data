import json
import math
import statistics
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOSED_COMMIT = "51d7ca19e544669edbc65be8392c4f997111e8ec"
CLOSED_URL = f"https://raw.githubusercontent.com/xwan008/a-share-market-data/{CLOSED_COMMIT}/data/latest.json"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def med(xs):
    ys = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(ys) if ys else None


def get_closed_latest():
    with urllib.request.urlopen(CLOSED_URL, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def build_closed_structure(closed_latest):
    latest_path = ROOT / "data/latest.json"
    latest_path.write_text(json.dumps(closed_latest, ensure_ascii=False), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_full_market_price_structure as builder
    builder.main()
    return load("data/research/full_market_price_structure.json")


def history_stats(code, cache):
    key = code[:5]
    if key not in cache:
        p = ROOT / "data/history_shards" / f"{key}.json"
        cache[key] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"stocks": {}}
    item = (cache[key].get("stocks") or {}).get(code) or {}
    rows = item.get("history") or []
    closes = [fnum(r.get("close")) for r in rows]
    closes = [x for x in closes if x and x > 0][-180:]
    if not closes:
        return None
    cur = closes[-1]
    sorted_c = sorted(closes)
    pct = sum(1 for x in closes if x <= cur) / len(closes) * 100
    return {
        "points": len(closes),
        "low": round(min(closes), 3),
        "median": round(statistics.median(closes), 3),
        "high": round(max(closes), 3),
        "percentile": round(pct, 1),
    }


def core_growth(f):
    for k in ("deduct_basic_eps_yoy", "deduct_net_profit_yoy"):
        x = fnum(f.get(k))
        if x is not None:
            return x
    return None


def test_runtime_probe():
    idx = load("data/research/company_industry_index.json")
    state = load("data/research/industry_state.json")
    closed = get_closed_latest()
    structure = build_closed_structure(closed)
    assert closed.get("trade_date") == "2026-09-01" and closed.get("market_status") == "closed"
    assert structure.get("reference_trade_date") == "2026-09-01"

    states = state.get("level3_profitability") or {}
    admitted = {
        c: r for c, r in states.items()
        if r.get("trend") == "improving" or (r.get("trend") == "stable" and r.get("breadth") == "divergent")
    }
    companies = idx.get("companies") or {}
    mapped = defaultdict(list)
    relations = []
    for code, m in companies.items():
        l3 = m.get("sw_level3_code")
        if l3 in admitted and m.get("mapping_status") == "mapped":
            mapped[l3].append(code)
            relations.append((l3, code))

    latest_stocks = closed.get("stocks") or {}
    unique_codes = sorted({code for _, code in relations})
    inactive = [c for c in unique_codes if c not in latest_stocks]

    hard_pass = {}
    hard_excluded = defaultdict(int)
    for code in unique_codes:
        q = latest_stocks.get(code)
        if not q or q.get("confidence") not in {"high", "medium"}:
            hard_excluded["data_unavailable"] += 1
            continue
        f = q.get("fundamentals") or {}
        g = core_growth(f)
        ded = fnum(f.get("deduct_basic_eps"))
        revg = fnum(f.get("revenue_yoy"))
        np = fnum(f.get("net_profit"))
        if g is None or ded is None:
            hard_excluded["data_unavailable"] += 1
            continue
        if ded <= 0 or g <= 0 or (np is not None and np <= 0):
            hard_excluded["core_earnings_not_improving"] += 1
            continue
        if revg is not None and revg < -15:
            hard_excluded["earnings_quality_mismatch"] += 1
            continue
        # Non-financial companies: clearly negative OCF/share is a quality warning, not an automatic fail
        # unless it conflicts with weak revenue and modest core growth.
        l1 = (companies.get(code) or {}).get("sw_level1_code")
        ocfps = fnum(f.get("operating_cashflow_per_share"))
        if l1 != "S49" and ocfps is not None and ocfps < 0 and (revg or 0) < 5 and g < 20:
            hard_excluded["earnings_quality_mismatch"] += 1
            continue
        hard_pass[code] = {"q": q, "f": f, "growth": g, "l3": (companies.get(code) or {}).get("sw_level3_code")}

    # Driver/quality gate. Stable-divergent companies must outperform chain median on core growth.
    chain_growth = {}
    for l3 in admitted:
        gs = [hard_pass[c]["growth"] for c in mapped.get(l3, []) if c in hard_pass]
        chain_growth[l3] = med(gs)
    driver_pass = {}
    driver_excluded = defaultdict(int)
    for code, row in hard_pass.items():
        st = admitted[row["l3"]]
        revg = fnum(row["f"].get("revenue_yoy"))
        if revg is not None and revg < -5:
            driver_excluded["sustainability_insufficient"] += 1
            continue
        if st.get("trend") == "stable" and st.get("breadth") == "divergent":
            cm = chain_growth.get(row["l3"])
            if cm is not None and row["growth"] < cm:
                driver_excluded["stable_divergent_company_not_outperforming"] += 1
                continue
        driver_pass[code] = row

    # Peer metrics for same Level-3.
    by_l3 = defaultdict(list)
    for c, r in driver_pass.items():
        by_l3[r["l3"]].append(c)
    peer_stats = {}
    for l3, codes in by_l3.items():
        peer_stats[l3] = {
            "pe": med([fnum(driver_pass[c]["f"].get("pe_ttm")) for c in codes if (fnum(driver_pass[c]["f"].get("pe_ttm")) or 0) > 0]),
            "pb": med([fnum(driver_pass[c]["f"].get("pb")) for c in codes if (fnum(driver_pass[c]["f"].get("pb")) or 0) > 0]),
            "roe": med([fnum(driver_pass[c]["f"].get("roe")) for c in codes]),
            "growth": med([driver_pass[c]["growth"] for c in codes]),
        }

    # Conservative dominated-by-peer: another direct peer must be no worse on PE, growth and ROE,
    # and strictly better on at least two of them. If PB is lower too, it strengthens domination.
    dominated = set()
    for l3, codes in by_l3.items():
        for c in codes:
            a = driver_pass[c]
            ape = fnum(a["f"].get("pe_ttm")); aroe = fnum(a["f"].get("roe")); apb = fnum(a["f"].get("pb")); ag = a["growth"]
            if not ape or ape <= 0 or aroe is None:
                continue
            for d in codes:
                if d == c:
                    continue
                b = driver_pass[d]
                bpe = fnum(b["f"].get("pe_ttm")); broe = fnum(b["f"].get("roe")); bpb = fnum(b["f"].get("pb")); bg = b["growth"]
                if not bpe or bpe <= 0 or broe is None:
                    continue
                no_worse = bpe <= ape * 1.02 and bg >= ag * 0.98 and broe >= aroe * 0.98
                strict = sum([bpe < ape * 0.9, bg > ag * 1.1, broe > aroe * 1.1, (bpb is not None and apb is not None and bpb < apb * 0.9)])
                if no_worse and strict >= 2:
                    dominated.add(c)
                    break

    peer_pass = {c:r for c,r in driver_pass.items() if c not in dominated}
    precheck_pass = {}
    precheck_excluded = []
    for c, r in peer_pass.items():
        ps = peer_stats[r["l3"]]
        pe = fnum(r["f"].get("pe_ttm")); dyn = fnum(r["f"].get("pe_dynamic")); roe = fnum(r["f"].get("roe"))
        ppm = ps["pe"]
        obvious = bool(pe and ppm and pe > ppm*2.2 and (not dyn or dyn > ppm*1.8) and r["growth"] < max(25, (ps["growth"] or 0)) and (roe or 0) <= (ps["roe"] or 0)*1.1)
        if obvious:
            precheck_excluded.append(c)
        else:
            precheck_pass[c] = r

    hcache = {}
    valuations = []
    for c, r in precheck_pass.items():
        q, f, l3 = r["q"], r["f"], r["l3"]
        price = fnum(q.get("price")); pe = fnum(f.get("pe_ttm")); dyn = fnum(f.get("pe_dynamic")); pb = fnum(f.get("pb")); roe = fnum(f.get("roe"))
        ps = peer_stats[l3]
        if not price or not pe or pe <= 0 or not ps["pe"] or ps["pe"] <= 0:
            continue
        ttm_eps = price / pe
        g = max(0.0, min(r["growth"], 60.0))
        proj_eps = ttm_eps * (1 + g/100*0.5)
        dyn_eps = price/dyn if dyn and dyn > 0 else None
        forward_eps = med([proj_eps, dyn_eps]) if dyn_eps else proj_eps
        growth_ref = ps["growth"] or 0
        growth_factor = 1.0 + max(-0.15, min(0.15, (r["growth"] - growth_ref)/200))
        roe_factor = 1.0
        if roe is not None and ps["roe"]:
            roe_factor += max(-0.08, min(0.08, (roe - ps["roe"])/100))
        fair_mid = ps["pe"] * growth_factor * roe_factor
        if pb and ps["pb"] and roe is not None and ps["roe"] is not None:
            if pb > ps["pb"]*1.8 and roe <= ps["roe"]:
                fair_mid *= 0.9
            elif pb < ps["pb"]*0.8 and roe > ps["roe"]*1.1:
                fair_mid *= 1.05
        fair_low, fair_high = fair_mid*0.9, fair_mid*1.1
        base_fair = forward_eps * fair_mid
        conf = admitted[l3].get("confidence")
        mos = 0.15 if conf == "high" else 0.20 if conf == "medium" else 0.25
        safe = base_fair * (1-mos)
        hs = history_stats(c, hcache)
        s = (structure.get("companies") or {}).get(c) or {}
        timing = bool(s.get("low_risk_eligible") and s.get("structure_type") in {"breakout","pullback","trend_continuation"} and s.get("chase_risk") != "high")
        entry = s.get("structure_entry_range") or s.get("entry_range") or s.get("buy_range")
        value = price <= safe
        in_entry = True
        if isinstance(entry, list) and len(entry) >= 2 and all(isinstance(x,(int,float)) for x in entry[:2]):
            in_entry = entry[0] <= price <= entry[1]
        buyable = value and timing and in_entry
        value_gap = max(0.0, (price/safe-1)*100) if safe > 0 else 999.0
        valuations.append({
            "code": c, "name": q.get("name"), "l3": l3, "industry": admitted[l3].get("name"),
            "price": round(price,3), "pe_ttm": round(pe,2), "pe_dynamic": round(dyn,2) if dyn else None,
            "pb": round(pb,2) if pb is not None else None, "roe": round(roe,2) if roe is not None else None,
            "core_growth": round(r["growth"],1), "peer_pe": round(ps["pe"],2), "peer_pb": round(ps["pb"],2) if ps["pb"] else None,
            "forward_eps": round(forward_eps,3), "fair_pe": [round(fair_low,1),round(fair_mid,1),round(fair_high,1)],
            "base_fair": round(base_fair,2), "mos": mos, "safe": round(safe,2), "value": value,
            "history": hs, "structure": s, "timing": timing, "entry": entry, "buyable": buyable, "value_gap": round(value_gap,1),
        })

    buys = sorted([x for x in valuations if x["buyable"]], key=lambda x:(x["value_gap"], -x["core_growth"]))
    timing_value = sorted([x for x in valuations if x["value"] and x["timing"]], key=lambda x:(x["value_gap"], -x["core_growth"]))
    near = sorted([x for x in valuations if not x["buyable"]], key=lambda x:(x["value_gap"], 0 if x["timing"] else 1, -x["core_growth"]))[:20]
    value_eligible = [x for x in valuations if x["value"]]

    summary = {
        "closed_data": {"trade_date":closed.get("trade_date"),"market_status":closed.get("market_status"),"pe_ttm_usable":(closed.get("fundamental_stats") or {}).get("pe_ttm_usable")},
        "structure": {"date":structure.get("reference_trade_date"),"verified":structure.get("verified_count"),"right_candidates":len(structure.get("right_candidate_codes") or []),"types":structure.get("structure_type_counts")},
        "admitted_level3_count": len(admitted),
        "company_chain_relations": len(relations),
        "unique_company_count": len(unique_codes),
        "inactive": len(inactive),
        "hard_pass": len(hard_pass), "hard_excluded": dict(hard_excluded),
        "driver_pass": len(driver_pass), "driver_excluded": dict(driver_excluded),
        "dominated_by_peer": len(dominated),
        "precheck_excluded": len(precheck_excluded),
        "valuation_set": len(precheck_pass),
        "fully_valued": len(valuations),
        "value_eligible": len(value_eligible),
        "timing_and_value": len(timing_value),
        "buyable_now": len(buys),
        "buys": buys[:20],
        "near": near[:10],
        "sample_verified_structure": next((v["structure"] for v in valuations if v["structure"].get("data_status")=="verified"), None),
    }
    raise AssertionError("RUNTIME_PROBE=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
