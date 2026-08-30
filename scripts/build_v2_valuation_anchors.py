from __future__ import annotations

import json, math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'data/research/v2/valuation_reference.json'
COMPANY=ROOT/'data/research/v2/company_research.json'
LATEST=ROOT/'data/latest.json'
HISTORY=ROOT/'data/history_shards'
OUT=ROOT/'data/research/v2/valuation_anchors.json'
TZ=ZoneInfo('Asia/Shanghai')
PEER_DIVERGENCE_BLOCK_PCT=45.0
HISTORY_CONFIRM_MAX_DIVERGENCE_PCT=50.0
HISTORY_SEVERE_DIVERGENCE_PCT=150.0
MIN_ZONE_WIDTH_PCT=1.0


def load(p): return json.loads(p.read_text(encoding='utf-8'))
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def percentile(vals,q):
    a=sorted(x for x in (num(v) for v in vals) if x is not None and x>0)
    if not a:return None
    pos=(len(a)-1)*q; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return a[lo]
    w=pos-lo; return a[lo]*(1-w)+a[hi]*w

def valid_range(v): return isinstance(v,list) and len(v)==2 and all(num(x) is not None for x in v) and float(v[0])>0 and float(v[1])>=float(v[0])
def nondegenerate(v): return valid_range(v) and float(v[1])>float(v[0]) and (float(v[1])/float(v[0])-1)*100>=MIN_ZONE_WIDTH_PCT

def history_anchor(code):
    p=HISTORY/f'{code[:4]}.json'
    if not p.exists(): return None
    s=(load(p).get('stocks') or {}).get(code) or {}; h=s.get('history') or []
    closes=[num(x.get('close')) for x in h[-180:] if isinstance(x,dict)]; closes=[x for x in closes if x and x>0]
    if len(closes)<120:return None
    return {'history_points':len(closes),'p10':percentile(closes,.10),'p20':percentile(closes,.20),'p25':percentile(closes,.25),'p35':percentile(closes,.35),'p50':percentile(closes,.50),'p60':percentile(closes,.60),'ma60':sum(closes[-60:])/60,'low':min(closes),'high':max(closes)}

def symbol(code): return ('SH' if code.startswith('6') else 'SZ')+code

def peer_anchor(ak, code, ref):
    try: df=ak.stock_zh_valuation_comparison_em(symbol=symbol(code))
    except Exception as exc: return None,f'{type(exc).__name__}:{exc}'
    if df is None or df.empty:return None,'empty'
    cols=list(df.columns); unit=ref.get('valuation_basis_unit')
    if unit=='PB': col=next((c for c in cols if '市净率-MRQ' in str(c)),None)
    else:
        y=str(datetime.now(TZ).year)[2:]+'E'; col=next((c for c in cols if '市盈率-' in str(c) and y in str(c)),None) or next((c for c in cols if '市盈率-TTM' in str(c)),None)
    code_col=next((c for c in cols if str(c)=='代码'),None)
    if not col or not code_col:return None,'valuation_column_missing'
    vals=[]
    for _,r in df.iterrows():
        c=str(r.get(code_col,'')); v=num(r.get(col))
        if c.isdigit() and len(c)==6 and v and v>0 and v<200: vals.append(v)
    if len(vals)<4:return None,f'peer_sample_insufficient:{len(vals)}'
    lo,mid=percentile(vals,.25),percentile(vals,.50)
    if unit=='PB':
        bvps=num(ref.get('book_value_per_share_proxy'))
        if not bvps:return None,'bvps_missing'
        rng=[bvps*lo,bvps*mid]
    else:
        eps=num(ref.get('consensus_eps_current_year'))
        if not eps:return None,'eps_missing'
        rng=[eps*lo,eps*mid]
    return {'source':'eastmoney_peer_valuation','valuation_column':str(col),'sample_count':len(vals),'peer_multiple_p25':round(lo,4),'peer_multiple_p50':round(mid,4),'fair_value_range':[round(rng[0],2),round(rng[1],2)]},None

def midpoint(v): return (float(v[0])+float(v[1]))/2 if valid_range(v) else None
def midpoint_divergence(a,b):
    ma,mb=midpoint(a),midpoint(b)
    if not ma or not mb:return None
    return abs(ma-mb)/max(1e-9,min(ma,mb))*100

def history_divergence(fundamental,hist):
    if not valid_range(fundamental) or not hist or not num(hist.get('p50')): return None
    fm=midpoint(fundamental); hm=float(hist['p50'])
    return abs(fm-hm)/max(1e-9,min(fm,hm))*100

def fundamental_entry_bands(ref, fair_floor):
    explicit=ref.get('explicit_entry_reference_range'); bp=ref.get('buy_band_policy') or {}
    if valid_range(explicit):
        lo,hi=map(float,explicit); split=lo+(hi-lo)*0.55
        return [lo,split],[split,hi],'explicit_low_risk_multiple_no_extra_discount'
    safe_ratio=bp.get('safe_to_fair_floor') if valid_range(bp.get('safe_to_fair_floor')) else [0.82,0.90]
    reason_ratio=bp.get('reasonable_to_fair_floor') if valid_range(bp.get('reasonable_to_fair_floor')) else [0.90,1.0]
    return [fair_floor*float(safe_ratio[0]),fair_floor*float(safe_ratio[1])],[fair_floor*float(reason_ratio[0]),fair_floor*float(reason_ratio[1])],'fair_floor_margin_of_safety'

def calibrate_with_history(fund_safe,fund_reason,hist):
    if not hist:return fund_safe,fund_reason,'fundamental_only_history_unavailable'
    safe=[fund_safe[0],min(fund_safe[1],float(hist['p25']))]
    reasonable=[fund_reason[0],min(fund_reason[1],float(hist['p60']),float(hist['ma60'])*1.08)]
    # History may lower an entry ceiling, never raise a fundamental lower bound. If the cap
    # would collapse a zone, the fundamental zone is already more conservative than recent cost.
    if not nondegenerate(safe): safe=list(fund_safe); safe_note='safe_fundamental_more_conservative_than_history'
    else: safe_note='safe_history_ceiling_applied'
    if not nondegenerate(reasonable): reasonable=list(fund_reason); reason_note='reasonable_fundamental_more_conservative_than_history'
    else: reason_note='reasonable_history_ceiling_applied'
    return safe,reasonable,f'fundamental_plus_180d_cost_calibration:{safe_note}:{reason_note}'

def build_zones(ref, peer, hist):
    f=ref.get('reference_range')
    if not valid_range(f): return None
    f=list(map(float,f)); peer_rng=(peer or {}).get('fair_value_range')
    peer_div=midpoint_divergence(f,peer_rng) if peer_rng else None
    peer_confirmed=bool(peer_rng and peer_div is not None and peer_div<=PEER_DIVERGENCE_BLOCK_PCT)
    if peer_div is not None and peer_div>PEER_DIVERGENCE_BLOCK_PCT:
        return {'status':'valuation_divergence','peer_divergence_pct':round(peer_div,2),'peer_confirmed':False,'history_confirmed':False,'independent_anchor_count':1,'formal_buy_zone_ready':False,'safe_buy_range':None,'reasonable_buy_range':None}

    hist_div=history_divergence(f,hist)
    history_confirmed=bool(hist and hist_div is not None and hist_div<=HISTORY_CONFIRM_MAX_DIVERGENCE_PCT)
    if hist_div is not None and hist_div>HISTORY_SEVERE_DIVERGENCE_PCT:
        return {'status':'fundamental_history_divergence','peer_divergence_pct':round(peer_div,2) if peer_div is not None else None,'history_fair_divergence_pct':round(hist_div,2),'peer_confirmed':peer_confirmed,'history_confirmed':False,'independent_anchor_count':1+(1 if peer_confirmed else 0),'formal_buy_zone_ready':False,'safe_buy_range':None,'reasonable_buy_range':None}

    fair_floor=float(f[0])
    if peer_confirmed: fair_floor=min(fair_floor,float(peer_rng[0]))
    fund_safe,fund_reason,entry_method=fundamental_entry_bands(ref,fair_floor)
    anchor_count=1+(1 if peer_confirmed else 0)+(1 if history_confirmed else 0)
    if anchor_count<2:
        return {'status':'insufficient_confirming_anchors','peer_divergence_pct':round(peer_div,2) if peer_div is not None else None,'history_fair_divergence_pct':round(hist_div,2) if hist_div is not None else None,'peer_confirmed':peer_confirmed,'history_confirmed':history_confirmed,'independent_anchor_count':anchor_count,'formal_buy_zone_ready':False,'safe_buy_range':None,'reasonable_buy_range':None,'conservative_fair_floor':round(fair_floor,2),'entry_method':entry_method}

    safe,reasonable,calibration=calibrate_with_history(fund_safe,fund_reason,hist if history_confirmed else None)
    if not(nondegenerate(safe) and nondegenerate(reasonable)):
        return {'status':'nondegenerate_buy_zone_required','peer_divergence_pct':round(peer_div,2) if peer_div is not None else None,'history_fair_divergence_pct':round(hist_div,2) if hist_div is not None else None,'peer_confirmed':peer_confirmed,'history_confirmed':history_confirmed,'independent_anchor_count':anchor_count,'formal_buy_zone_ready':False,'safe_buy_range':None,'reasonable_buy_range':None,'conservative_fair_floor':round(fair_floor,2),'entry_method':entry_method,'calibration_method':calibration}
    if safe[1]>reasonable[0]:
        boundary=(safe[1]+reasonable[0])/2; safe[1]=boundary; reasonable[0]=boundary
    ready=nondegenerate(safe) and nondegenerate(reasonable)
    return {'status':'valid' if ready else 'nondegenerate_buy_zone_required','formal_buy_zone_ready':ready,'independent_anchor_count':anchor_count,'conservative_fair_floor':round(fair_floor,2),'safe_buy_range':[round(safe[0],2),round(safe[1],2)] if ready else None,'reasonable_buy_range':[round(reasonable[0],2),round(reasonable[1],2)] if ready else None,'value_anchor_range':[round(safe[0],2),round(max(reasonable[1],fair_floor),2)] if ready else None,'peer_divergence_pct':round(peer_div,2) if peer_div is not None else None,'history_fair_divergence_pct':round(hist_div,2) if hist_div is not None else None,'peer_confirmed':peer_confirmed,'history_confirmed':history_confirmed,'entry_method':entry_method,'calibration_method':calibration}

def main():
    import akshare as ak
    ref=load(REF); company=load(COMPANY); latest=load(LATEST); rows={}; peer_errors={}; counts={'formal_zone_ready':0,'valuation_divergence':0,'fundamental_history_divergence':0,'insufficient_confirming_anchors':0,'fundamental_unavailable':0,'peer_available':0,'peer_confirmed':0,'history_available':0,'history_confirmed':0}
    for code in company.get('selected_for_valuation_codes') or []:
        rr=(ref.get('companies') or {}).get(code) or {}; price=num(((latest.get('stocks') or {}).get(code) or {}).get('price'))
        hist=history_anchor(code); peer=None
        if rr.get('status')=='available' and rr.get('route')!='cycle':
            peer,err=peer_anchor(ak,code,rr)
            if err: peer_errors[code]=err
        if peer: counts['peer_available']+=1
        if hist: counts['history_available']+=1
        if rr.get('status')!='available':
            counts['fundamental_unavailable']+=1
            rows[code]={'code':code,'name':rr.get('name') or code,'current_price':price,'status':'fundamental_anchor_unavailable','fundamental_anchor':rr,'peer_anchor':peer,'history_cost_anchor':hist,'formal_buy_zone_ready':False,'independent_anchor_count':0,'safe_buy_range':None,'reasonable_buy_range':None}
            continue
        z=build_zones(rr,peer,hist) or {'status':'insufficient_confirming_anchors','formal_buy_zone_ready':False,'independent_anchor_count':1}
        if z.get('formal_buy_zone_ready'): counts['formal_zone_ready']+=1
        if z.get('status')=='valuation_divergence': counts['valuation_divergence']+=1
        if z.get('status')=='fundamental_history_divergence': counts['fundamental_history_divergence']+=1
        if z.get('status') in {'insufficient_confirming_anchors','nondegenerate_buy_zone_required'}: counts['insufficient_confirming_anchors']+=1
        if z.get('peer_confirmed'): counts['peer_confirmed']+=1
        if z.get('history_confirmed'): counts['history_confirmed']+=1
        implied={}; eps=num(rr.get('consensus_eps_current_year')); bvps=num(rr.get('book_value_per_share_proxy'))
        if z.get('formal_buy_zone_ready'):
            if rr.get('valuation_basis_unit')=='PE' and eps:
                implied={'safe_implied_pe':[round(x/eps,2) for x in z['safe_buy_range']],'reasonable_implied_pe':[round(x/eps,2) for x in z['reasonable_buy_range']]}
            elif rr.get('valuation_basis_unit')=='PB' and bvps:
                implied={'safe_implied_pb':[round(x/bvps,2) for x in z['safe_buy_range']],'reasonable_implied_pb':[round(x/bvps,2) for x in z['reasonable_buy_range']]}
        rows[code]={'code':code,'name':rr.get('name') or code,'current_price':price,'fundamental_anchor':rr,'peer_anchor':peer,'history_cost_anchor':hist,**z,**implied}
    payload={'schema_version':2,'mode':'shadow','generated_at':datetime.now(TZ).isoformat(),'reference_trade_date':ref.get('reference_trade_date'),'valuation_queue_count':len(rows),'counts':counts,'peer_errors':peer_errors,'thresholds':{'peer_divergence_block_pct':PEER_DIVERGENCE_BLOCK_PCT,'history_confirmation_max_divergence_pct':HISTORY_CONFIRM_MAX_DIVERGENCE_PCT,'history_severe_divergence_pct':HISTORY_SEVERE_DIVERGENCE_PCT,'minimum_zone_width_pct':MIN_ZONE_WIDTH_PCT},'companies':rows,'method_note':'Anchor existence is not enough: B/C count only when they confirm A within explicit economic tolerances. Extreme A-vs-history mismatch blocks formal zones as likely model/basis mismatch. History can lower an entry ceiling but never raise a fundamental lower bound or collapse a zone into a point.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','counts':counts,'peer_errors':len(peer_errors)},ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
