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

def divergence(a,b):
    if not(valid_range(a) and valid_range(b)):return None
    ma=sum(map(float,a))/2; mb=sum(map(float,b))/2
    return abs(ma-mb)/max(1e-9,min(ma,mb))*100

def build_zones(ref, peer, hist):
    f=ref.get('reference_range')
    if not valid_range(f): return None
    f=list(map(float,f)); peer_rng=(peer or {}).get('fair_value_range')
    div=divergence(f,peer_rng) if peer_rng else None
    if div is not None and div>45:
        return {'status':'valuation_divergence','divergence_pct':round(div,2),'formal_buy_zone_ready':False}
    fair_floor=f[0]
    if valid_range(peer_rng): fair_floor=min(fair_floor,float(peer_rng[0]))
    explicit=ref.get('explicit_entry_reference_range')
    bp=ref.get('buy_band_policy') or {}
    if valid_range(explicit):
        fund_safe=[float(explicit[0]),float(explicit[1])*0.90]
        fund_reason=[float(explicit[1])*0.90,float(explicit[1])]
        entry_method='explicit_low_risk_multiple_no_extra_discount'
    else:
        safe_ratio=bp.get('safe_to_fair_floor') if valid_range(bp.get('safe_to_fair_floor')) else [0.82,0.90]
        reason_ratio=bp.get('reasonable_to_fair_floor') if valid_range(bp.get('reasonable_to_fair_floor')) else [0.90,1.0]
        fund_safe=[fair_floor*float(safe_ratio[0]),fair_floor*float(safe_ratio[1])]
        fund_reason=[fair_floor*float(reason_ratio[0]),fair_floor*float(reason_ratio[1])]
        entry_method='fair_floor_margin_of_safety'
    anchor_count=1+(1 if peer else 0)+(1 if hist else 0)
    if hist:
        safe_ceiling=min(fund_safe[1],hist['p25'])
        safe_lower=max(min(fund_safe[0],safe_ceiling),min(hist['p10'],safe_ceiling))
        reason_ceiling=min(fund_reason[1],hist['p60'],hist['ma60']*1.08)
        reason_lower=max(safe_ceiling,min(fund_reason[0],hist['p35']))
        if reason_ceiling<reason_lower:
            reason_lower=fund_reason[0]; reason_ceiling=fund_reason[1]; calibration='fundamental_dominant_history_below_entry_band'
        else: calibration='fundamental_plus_180d_cost_calibration'
        safe=[safe_lower,safe_ceiling]; reasonable=[reason_lower,reason_ceiling]
        if safe[1]<safe[0]: safe=fund_safe
    else:
        safe,reasonable=fund_safe,fund_reason; calibration='fundamental_only_history_missing'
    ready=anchor_count>=2 and reasonable[1]>=reasonable[0] and safe[1]>=safe[0]
    return {'status':'valid' if ready else 'insufficient_independent_anchors','formal_buy_zone_ready':ready,'independent_anchor_count':anchor_count,'conservative_fair_floor':round(fair_floor,2),'safe_buy_range':[round(safe[0],2),round(safe[1],2)],'reasonable_buy_range':[round(reasonable[0],2),round(reasonable[1],2)],'value_anchor_range':[round(safe[0],2),round(max(reasonable[1],fair_floor),2)],'divergence_pct':round(div,2) if div is not None else None,'entry_method':entry_method,'calibration_method':calibration}

def main():
    import akshare as ak
    ref=load(REF); company=load(COMPANY); latest=load(LATEST); rows={}; peer_errors={}; counts={'formal_zone_ready':0,'valuation_divergence':0,'fundamental_unavailable':0,'peer_available':0,'history_available':0}
    for code in company.get('selected_for_valuation_codes') or []:
        rr=(ref.get('companies') or {}).get(code) or {}; price=num(((latest.get('stocks') or {}).get(code) or {}).get('price'))
        hist=history_anchor(code)
        peer=None
        if rr.get('status')=='available' and rr.get('route')!='cycle':
            peer,err=peer_anchor(ak,code,rr)
            if err: peer_errors[code]=err
        if peer: counts['peer_available']+=1
        if hist: counts['history_available']+=1
        if rr.get('status')!='available':
            counts['fundamental_unavailable']+=1
            rows[code]={'code':code,'name':rr.get('name') or code,'current_price':price,'status':'fundamental_anchor_unavailable','fundamental_anchor':rr,'peer_anchor':peer,'history_cost_anchor':hist,'formal_buy_zone_ready':False,'safe_buy_range':None,'reasonable_buy_range':None}
            continue
        z=build_zones(rr,peer,hist) or {'status':'insufficient_independent_anchors','formal_buy_zone_ready':False}
        if z.get('formal_buy_zone_ready'): counts['formal_zone_ready']+=1
        if z.get('status')=='valuation_divergence': counts['valuation_divergence']+=1
        implied={}
        eps=num(rr.get('consensus_eps_current_year')); bvps=num(rr.get('book_value_per_share_proxy'))
        if z.get('formal_buy_zone_ready'):
            if rr.get('valuation_basis_unit')=='PE' and eps:
                implied={'safe_implied_pe':[round(x/eps,2) for x in z['safe_buy_range']],'reasonable_implied_pe':[round(x/eps,2) for x in z['reasonable_buy_range']]}
            elif rr.get('valuation_basis_unit')=='PB' and bvps:
                implied={'safe_implied_pb':[round(x/bvps,2) for x in z['safe_buy_range']],'reasonable_implied_pb':[round(x/bvps,2) for x in z['reasonable_buy_range']]}
        rows[code]={'code':code,'name':rr.get('name') or code,'current_price':price,'status':z.get('status'),'fundamental_anchor':rr,'peer_anchor':peer,'history_cost_anchor':hist,**z,**implied}
    payload={'schema_version':1,'mode':'shadow','generated_at':datetime.now(TZ).isoformat(),'reference_trade_date':ref.get('reference_trade_date'),'valuation_queue_count':len(rows),'counts':counts,'peer_errors':peer_errors,'companies':rows,'method_note':'Three-anchor framework: A fundamental valuation, B peer valuation when available, C 180d own-market cost distribution. A formal safe/reasonable zone requires A plus at least one independent B/C anchor and is blocked on severe A/B divergence. History calibrates entry, not fair value.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','counts':counts,'peer_errors':len(peer_errors)},ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
