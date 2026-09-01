from __future__ import annotations
import json, math, statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'data/research/company_industry_index.json'
TARGETS={'601899':'紫金矿业','601225':'陕西煤业','600096':'云天化','603236':'移远通信'}
URL='https://datacenter-web.eastmoney.com/api/data/v1/get'
QUOTE='https://push2.eastmoney.com/api/qt/stock/get'
KLINE='https://push2his.eastmoney.com/api/qt/stock/kline/get'
HEAD={'User-Agent':'Mozilla/5.0 schema32-calibration'}

def num(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except: return None

def secid(code): return ('1.' if code.startswith(('600','601','603','605','688')) else '0.')+code

def fetch_report(date):
    out={}
    for page in range(1,40):
        p={'reportName':'RPT_LICO_FN_CPD','columns':'ALL','filter':f"(REPORTDATE='{date}')",'pageNumber':page,'pageSize':500,'sortColumns':'SECURITY_CODE','sortTypes':'1'}
        j=requests.get(URL,params=p,headers=HEAD,timeout=30).json(); rows=((j.get('result') or {}).get('data') or [])
        if not rows: break
        for r in rows:
            c=str(r.get('SECURITY_CODE') or '').zfill(6)
            if len(c)==6: out[c]=r
    return out

def quote(code):
    fields='f58,f2,f9,f23,f115'
    d=(requests.get(QUOTE,params={'secid':secid(code),'fields':fields},headers=HEAD,timeout=15).json().get('data') or {})
    return {'name':d.get('f58'),'price':num(d.get('f2')),'dynamic_pe':num(d.get('f9')),'pb':num(d.get('f23')),'ttm_pe':num(d.get('f115'))}

def kline180(code):
    p={'secid':secid(code),'klt':101,'fqt':1,'lmt':180,'end':'20500101','fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56'}
    d=(requests.get(KLINE,params=p,headers=HEAD,timeout=20).json().get('data') or {})
    ks=d.get('klines') or []
    closes=[]
    for s in ks:
        parts=s.split(',')
        if len(parts)>2:
            x=num(parts[2])
            if x is not None: closes.append(x)
    if not closes: return None
    cur=closes[-1]; less=sum(1 for x in closes if x<=cur)
    return {'n':len(closes),'low':round(min(closes),2),'median':round(statistics.median(closes),2),'high':round(max(closes),2),'current':round(cur,2),'percentile':round(100*less/len(closes),1)}

def yoy(a,b):
    a,b=num(a),num(b)
    if a is None or b is None:return None
    if b>0:return a/b-1
    if b<=0<a:return 1.0
    if b<0 and a<0:return (abs(b)-abs(a))/abs(b)
    return None

def flatten(obj):
    out=[]
    def rec(x):
        if isinstance(x,dict):
            code=str(x.get('code') or x.get('stock_code') or x.get('security_code') or '')
            if len(code)==6 and code.isdigit(): out.append(x)
            for v in x.values(): rec(v)
        elif isinstance(x,list):
            for v in x: rec(v)
    rec(obj)
    # dedup by code keeping richest record
    best={}
    for r in out:
        c=str(r.get('code') or r.get('stock_code') or r.get('security_code'))
        if c not in best or len(r)>len(best[c]): best[c]=r
    return list(best.values())

def l3_info(r):
    # explicit known variants first
    code=None; name=None
    for k,v in r.items():
        lk=k.lower()
        if 'level3' in lk or 'level_3' in lk or lk.startswith('sw3') or 'sw_level3' in lk:
            if 'code' in lk: code=str(v)
            elif 'name' in lk: name=str(v)
    if code is None:
        for k in ['industry_level3_code','l3_code','third_level_code']: 
            if r.get(k) is not None: code=str(r[k]); break
    if name is None:
        for k in ['industry_level3_name','l3_name','third_level_name']:
            if r.get(k) is not None: name=str(r[k]); break
    return code,name

cur=fetch_report('2026-06-30'); prev=fetch_report('2025-06-30'); ann=fetch_report('2025-12-31')
idx=json.loads(INDEX.read_text(encoding='utf-8')); records=flatten(idx); bycode={str(r.get('code') or r.get('stock_code') or r.get('security_code')):r for r in records}

# Quote all mapped records needed for target L3 peer groups only.
target_l3={}
for c in TARGETS:
    r=bycode.get(c) or {}; target_l3[c]=l3_info(r)
print('TARGET_INDEX_RECORDS')
print(json.dumps({c:{'record':bycode.get(c),'l3':target_l3[c]} for c in TARGETS},ensure_ascii=False,indent=2))

peer_groups={}
for c,(l3c,l3n) in target_l3.items():
    peers=[]
    for r in records:
        rc=str(r.get('code') or r.get('stock_code') or r.get('security_code'))
        pc,pn=l3_info(r)
        if l3c and pc==l3c: peers.append(rc)
        elif (not l3c) and l3n and pn==l3n: peers.append(rc)
    peer_groups[c]=sorted(set(peers))

allcodes=sorted(set(x for ps in peer_groups.values() for x in ps))
quotes={}
with ThreadPoolExecutor(max_workers=24) as ex:
    fs={ex.submit(quote,c):c for c in allcodes}
    for f in as_completed(fs):
        c=fs[f]
        try: quotes[c]=f.result()
        except Exception as e: quotes[c]={'error':str(e)}

outputs={}
for c,name in TARGETS.items():
    q=quotes.get(c) or quote(c); h=kline180(c); r=cur.get(c) or {}; rp=prev.get(c) or {}; ra=ann.get(c) or {}
    h1eps=num(r.get('DEDUCT_BASIC_EPS')); p1eps=num(rp.get('DEDUCT_BASIC_EPS')); aeps=num(ra.get('DEDUCT_BASIC_EPS'))
    growth=yoy(h1eps,p1eps)
    ratio=(p1eps/aeps) if p1eps is not None and aeps not in (None,0) and p1eps>0 and aeps>0 else None
    if ratio is not None and 0.20<=ratio<=0.80 and h1eps is not None:
        fwd=h1eps/ratio; fwd_basis=f'2025H1/2025A core EPS seasonality={ratio:.1%}'
    elif h1eps is not None:
        fwd=h1eps*2; fwd_basis='H1 core EPS simple x2 calibration fallback'
    else:
        fwd=None; fwd_basis='missing core EPS'
    peers=peer_groups[c]
    valid_pe=[]; valid_pb=[]; peer_growth=[]
    for pc in peers:
        pq=quotes.get(pc) or {}; pe=pq.get('dynamic_pe') or pq.get('ttm_pe'); pb=pq.get('pb')
        if pe is not None and 2<=pe<=100: valid_pe.append(pe)
        if pb is not None and 0.1<=pb<=20: valid_pb.append(pb)
        pr=cur.get(pc) or {}; pp=prev.get(pc) or {}; g=yoy(pr.get('DEDUCT_BASIC_EPS'),pp.get('DEDUCT_BASIC_EPS'))
        if g is not None and -0.8<=g<=3: peer_growth.append(g)
    peer_pe=statistics.median(valid_pe) if valid_pe else None; peer_pb=statistics.median(valid_pb) if valid_pb else None; pg=statistics.median(peer_growth) if peer_growth else None
    dyn=q.get('dynamic_pe'); ttm=q.get('ttm_pe')
    # Fair PE: peer median primary; current company dynamic PE only a constrained 25% auxiliary anchor.
    fair_mid=None; adj=1.0; adj_reason='growth near peer median or peer growth unavailable'
    if peer_pe is not None:
        if growth is not None and pg is not None:
            diff=growth-pg
            if diff>=0.20: adj=1.10; adj_reason=f'core growth {growth:.1%} exceeds peer median {pg:.1%} by >=20pp'
            elif diff<=-0.20: adj=0.90; adj_reason=f'core growth {growth:.1%} trails peer median {pg:.1%} by >=20pp'
        peer_adj=peer_pe*adj
        if dyn is not None and 2<=dyn<=100:
            clipped=min(max(dyn,peer_pe*0.8),peer_pe*1.2)
            fair_mid=peer_adj*0.75+clipped*0.25
        else: fair_mid=peer_adj
    elif dyn is not None and 2<=dyn<=100:
        fair_mid=dyn
    if fair_mid is not None:
        fair_low=fair_mid*0.85; fair_high=fair_mid*1.15
    else: fair_low=fair_high=None
    base=fwd*fair_mid if fwd is not None and fair_mid is not None else None
    rr=[round(fwd*fair_low,2),round(fwd*fair_high,2)] if fwd is not None and fair_low is not None else None
    # calibration MOS: cyclical/resource 20%, growth communications 15%.
    mos=0.15 if c=='603236' else 0.20
    safe=base*(1-mos) if base is not None else None
    sanity='ok'
    if h and base is not None:
        if base < h['median']*0.70 and (growth or 0)>0: sanity='model_below_180d_median_gt30pct_despite_positive_core_growth'
        elif base > h['median']*1.50: sanity='model_above_180d_median_gt50pct'
    outputs[c]={
      'name':name,'l3':target_l3[c],'peer_count':len(peers),'valid_peer_pe_count':len(valid_pe),'valid_peer_pb_count':len(valid_pb),
      'price':q.get('price'),'dynamic_pe':dyn,'ttm_pe':ttm,'pb':q.get('pb'),'core_eps_h1_2026':h1eps,'core_eps_h1_2025':p1eps,'core_eps_2025A':aeps,
      'core_growth':growth,'peer_core_growth_median':pg,'peer_pe_median':peer_pe,'peer_pb_median':peer_pb,'forward_core_eps':fwd,'forward_basis':fwd_basis,
      'growth_adjustment':adj,'growth_adjustment_reason':adj_reason,
      'fair_pe':[round(fair_low,2),round(fair_mid,2),round(fair_high,2)] if fair_mid else None,
      'reasonable_price_range':rr,'base_fair_value':round(base,2) if base else None,'mos':mos,'safe_price_ceiling':round(safe,2) if safe else None,
      'history_180d':h,'market_sanity':sanity,
      'value_gap_pct':round(max(0,(q.get('price')-safe)/q.get('price')*100),1) if q.get('price') and safe else None
    }
print('CALIBRATION_RESULT')
print(json.dumps(outputs,ensure_ascii=False,indent=2))
