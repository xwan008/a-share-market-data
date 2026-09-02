import json
import math
import statistics
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOSED_COMMIT = "51d7ca19e544669edbc65be8392c4f997111e8ec"
BASE = f"https://raw.githubusercontent.com/xwan008/a-share-market-data/{CLOSED_COMMIT}"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def remote_json(path):
    with urllib.request.urlopen(f"{BASE}/{path}", timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def med(xs):
    ys = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(ys) if ys else None


def core_growth(f):
    for k in ("deduct_basic_eps_yoy", "deduct_net_profit_yoy"):
        x = fnum(f.get(k))
        if x is not None:
            return x
    return None


def entry_range(s):
    p = fnum(s.get("current_price")); ma20 = fnum(s.get("ma20")); support = fnum(s.get("support_invalidation")); level = fnum(s.get("breakout_level"))
    st = s.get("structure_type")
    if st == "pullback" and support and ma20:
        return [round(support * 1.001, 2), round(ma20 * 1.002, 2)]
    if st == "breakout" and level:
        return [round(level * 0.995, 2), round(level * 1.03, 2)]
    if st == "trend_continuation" and ma20:
        lo = max(x for x in [ma20, support or 0] if x > 0)
        return [round(lo * 0.997, 2), round(ma20 * 1.04, 2)]
    return None


def test_runtime_probe():
    idx = load("data/research/company_industry_index.json")
    state = load("data/research/industry_state.json")
    closed = remote_json("data/latest.json")
    structure = remote_json("data/research/full_market_price_structure.json")
    assert closed.get("trade_date") == "2026-09-01" and closed.get("market_status") == "closed"
    assert structure.get("reference_trade_date") == "2026-09-01"
    assert (structure.get("verified_count") or 0) > 3000

    states = state.get("level3_profitability") or {}
    admitted = {c:r for c,r in states.items() if r.get("trend") == "improving" or (r.get("trend") == "stable" and r.get("breadth") == "divergent")}
    companies = idx.get("companies") or {}
    mapped = defaultdict(list); relations = []
    for code, m in companies.items():
        l3 = m.get("sw_level3_code")
        if l3 in admitted and m.get("mapping_status") == "mapped":
            mapped[l3].append(code); relations.append((l3, code))

    stocks = closed.get("stocks") or {}
    unique_codes = sorted({c for _,c in relations})
    hard_pass = {}; hard_excluded = defaultdict(int)
    for code in unique_codes:
        q = stocks.get(code)
        if not q or q.get("confidence") not in {"high","medium"}:
            hard_excluded["data_unavailable"] += 1; continue
        f = q.get("fundamentals") or {}; g = core_growth(f); ded = fnum(f.get("deduct_basic_eps")); revg = fnum(f.get("revenue_yoy")); np = fnum(f.get("net_profit"))
        if g is None or ded is None:
            hard_excluded["data_unavailable"] += 1; continue
        if ded <= 0 or g <= 0 or (np is not None and np <= 0):
            hard_excluded["core_earnings_not_improving"] += 1; continue
        if revg is not None and revg < -15:
            hard_excluded["earnings_quality_mismatch"] += 1; continue
        l1 = (companies.get(code) or {}).get("sw_level1_code"); ocf = fnum(f.get("operating_cashflow_per_share"))
        if l1 != "S49" and ocf is not None and ocf < 0 and (revg or 0) < 5 and g < 20:
            hard_excluded["earnings_quality_mismatch"] += 1; continue
        hard_pass[code] = {"q":q,"f":f,"growth":g,"l3":(companies.get(code) or {}).get("sw_level3_code")}

    chain_growth = {l3:med([hard_pass[c]["growth"] for c in mapped.get(l3,[]) if c in hard_pass]) for l3 in admitted}
    driver_pass = {}; driver_excluded = defaultdict(int)
    for code,row in hard_pass.items():
        st = admitted[row["l3"]]; revg = fnum(row["f"].get("revenue_yoy"))
        if revg is not None and revg < -5:
            driver_excluded["sustainability_insufficient"] += 1; continue
        if st.get("trend") == "stable" and st.get("breadth") == "divergent" and chain_growth.get(row["l3"]) is not None and row["growth"] < chain_growth[row["l3"]]:
            driver_excluded["stable_divergent_not_outperforming"] += 1; continue
        driver_pass[code] = row

    by_l3 = defaultdict(list)
    for c,r in driver_pass.items(): by_l3[r["l3"]].append(c)
    peers = {}
    for l3,codes in by_l3.items():
        peers[l3] = {
            "pe":med([fnum(driver_pass[c]["f"].get("pe_ttm")) for c in codes if (fnum(driver_pass[c]["f"].get("pe_ttm")) or 0)>0]),
            "pb":med([fnum(driver_pass[c]["f"].get("pb")) for c in codes if (fnum(driver_pass[c]["f"].get("pb")) or 0)>0]),
            "roe":med([fnum(driver_pass[c]["f"].get("roe")) for c in codes]),
            "growth":med([driver_pass[c]["growth"] for c in codes]),
        }

    dominated = set()
    for l3,codes in by_l3.items():
        for c in codes:
            a=driver_pass[c]; ape=fnum(a["f"].get("pe_ttm")); ar=fnum(a["f"].get("roe")); apb=fnum(a["f"].get("pb")); ag=a["growth"]
            if not ape or ape<=0 or ar is None: continue
            for d in codes:
                if d==c: continue
                b=driver_pass[d]; bpe=fnum(b["f"].get("pe_ttm")); br=fnum(b["f"].get("roe")); bpb=fnum(b["f"].get("pb")); bg=b["growth"]
                if not bpe or bpe<=0 or br is None: continue
                strict=sum([bpe<ape*.9,bg>ag*1.1,br>ar*1.1,(bpb is not None and apb is not None and bpb<apb*.9)])
                if bpe<=ape*1.02 and bg>=ag*.98 and br>=ar*.98 and strict>=2:
                    dominated.add(c); break

    peer_pass={c:r for c,r in driver_pass.items() if c not in dominated}
    valuation_set={}; expensive=[]
    for c,r in peer_pass.items():
        ps=peers[r["l3"]]; pe=fnum(r["f"].get("pe_ttm")); dyn=fnum(r["f"].get("pe_dynamic")); roe=fnum(r["f"].get("roe")); ppm=ps["pe"]
        obvious=bool(pe and ppm and pe>ppm*2.2 and (not dyn or dyn>ppm*1.8) and r["growth"]<max(25,(ps["growth"] or 0)) and (roe or 0)<=(ps["roe"] or 0)*1.1)
        if obvious: expensive.append(c)
        else: valuation_set[c]=r

    vals=[]; review=0
    for c,r in valuation_set.items():
        q,f,l3=r["q"],r["f"],r["l3"]; price=fnum(q.get("price")); pe=fnum(f.get("pe_ttm")); dyn=fnum(f.get("pe_dynamic")); pb=fnum(f.get("pb")); roe=fnum(f.get("roe")); ps=peers[l3]
        if not price or not pe or pe<=0 or not ps["pe"] or ps["pe"]<=0:
            review+=1; continue
        ttm_eps=price/pe; g=max(0,min(r["growth"],60)); proj=ttm_eps*(1+g/200); dyn_eps=price/dyn if dyn and dyn>0 else None; fwd=med([proj,dyn_eps]) if dyn_eps else proj
        growth_factor=1+max(-.15,min(.15,(r["growth"]-(ps["growth"] or 0))/200)); roe_factor=1
        if roe is not None and ps["roe"]: roe_factor+=max(-.08,min(.08,(roe-ps["roe"])/100))
        fair=ps["pe"]*growth_factor*roe_factor
        if pb and ps["pb"] and roe is not None and ps["roe"] is not None:
            if pb>ps["pb"]*1.8 and roe<=ps["roe"]: fair*=.9
            elif pb<ps["pb"]*.8 and roe>ps["roe"]*1.1: fair*=1.05
        base=fwd*fair; conf=admitted[l3].get("confidence"); mos=.15 if conf=="high" else .20 if conf=="medium" else .25; safe=base*(1-mos)
        s=(structure.get("companies") or {}).get(c) or {}; entry=entry_range(s); timing=bool(s.get("low_risk_eligible") and s.get("structure_type") in {"breakout","pullback","trend_continuation"} and s.get("action")=="participate" and s.get("chase_risk")=="low")
        in_entry=bool(entry and entry[0]<=price<=entry[1]); value=price<=safe; buy=value and timing and in_entry
        value_gap=max(0,(price/safe-1)*100) if safe>0 else 999
        struct_gap=0
        if entry:
            if price<entry[0]: struct_gap=(entry[0]/price-1)*100
            elif price>entry[1]: struct_gap=(price/entry[1]-1)*100
        elif not timing: struct_gap=999
        vals.append({"code":c,"name":q.get("name"),"industry":admitted[l3].get("name"),"l3":l3,"price":round(price,2),"pe_ttm":round(pe,2),"pe_dynamic":round(dyn,2) if dyn else None,"pb":round(pb,2) if pb is not None else None,"roe":round(roe,2) if roe is not None else None,"growth":round(r["growth"],1),"peer_pe":round(ps["pe"],2),"fair_pe":[round(fair*.9,1),round(fair,1),round(fair*1.1,1)],"base_fair":round(base,2),"mos":mos,"safe":round(safe,2),"value":value,"structure_type":s.get("structure_type"),"action":s.get("action"),"chase":s.get("chase_risk"),"ma20":s.get("ma20"),"ma60":s.get("ma60"),"support":s.get("support_invalidation"),"entry":entry,"timing":timing,"buyable":buy,"value_gap":round(value_gap,1),"structure_gap":round(struct_gap,1) if struct_gap<900 else None})

    buys=sorted([x for x in vals if x["buyable"]],key=lambda x:(x["value_gap"],-x["growth"]))
    near=sorted([x for x in vals if not x["buyable"]],key=lambda x:(max(x["value_gap"],x["structure_gap"] or 999),0 if x["timing"] else 1,-x["growth"]))[:10]
    summary={"closed":{"date":closed.get("trade_date"),"status":closed.get("market_status"),"ttm":(closed.get("fundamental_stats") or {}).get("pe_ttm_usable")},"structure":{"date":structure.get("reference_trade_date"),"verified":structure.get("verified_count"),"right_candidates":len(structure.get("right_candidate_codes") or []),"types":structure.get("structure_type_counts")},"admitted_level3":len(admitted),"relations":len(relations),"unique_companies":len(unique_codes),"hard_pass":len(hard_pass),"hard_excluded":dict(hard_excluded),"driver_pass":len(driver_pass),"driver_excluded":dict(driver_excluded),"dominated":len(dominated),"obviously_expensive":len(expensive),"valuation_set":len(valuation_set),"fully_valued":len(vals),"review":review,"value_eligible":sum(x["value"] for x in vals),"buyable_now":len(buys),"buys":buys[:20],"near":near}
    raise AssertionError("RUNTIME_PROBE="+json.dumps(summary,ensure_ascii=False,separators=(",",":")))
