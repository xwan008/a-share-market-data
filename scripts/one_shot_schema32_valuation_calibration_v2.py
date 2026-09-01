from __future__ import annotations
import json, math, statistics, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'data/research/company_industry_index.json'
TARGETS={'601899':'紫金矿业','601225':'陕西煤业','600096':'云天化','603236':'移远通信'}
URL='https://datacenter-web.eastmoney.com/api/data/v1/get'
QUOTE='https://push2.eastmoney.com/api/qt/stock/get'
KLINE='https://push2his.eastmoney.com/api/qt/stock/kline/get'
HEAD={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
S=requests.Session(); S.headers.update(HEAD)

def num(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except: return None

def secid(code): return ('1.' if code.startswith(('600','601','603','605','688')) else '0.')+code

def get(url,params,timeout=20,retries=4):
    err=None
    for i in range(retries):
        try:
            r=S.get(url,params=params,timeout=timeout); r.raise_for_status(); return r
        except Exception as e:
            err=e; time.sleep(1.2*(i+1))
    raise err

def fetch_report(date):
    out={}
    for page in range(1,15):
        p={'reportName':'RPT_LICO_FN_CPD','columns':'ALL','filter':f"(REPORTDATE='{date}')",'pageNumber':page,'pageSize':500,'sortColumns':'SECURITY_CODE','sortTypes':'1'}
        rows=(((get(URL,p,30).json().get('result') or {}).get('data')) or [])
        if not rows: break
        for r in rows:
            c=str(r.get('SECURITY_CODE') or '').zfill(6)
            if len(c)==6: out[c]=r
    return out

def quote(code):
    d=(get(QUOTE,{'secid':secid(code),'fields':'f58,f2,f9,f23,f115'},15).json().get('data') or {})
    return {'name':d.get('f58'),'price':num(d.get('f2')),'dynamic_pe':num(d.get('f9')),'pb':num(d.get('f23')),'ttm_pe':num(d.get('f115'))}

def kline180(code):
    try:
        p={'secid':secid(code),'klt':101,'fqt':1,'lmt':180,'end':'20500101','fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56'}
        ks=((get(KLINE,p,25,5).json().get('data') or {}).get('klines') or [])
        closes=[num(x.split(',')[2]) for x in ks if len(x.split(','))>2]
        closes=[x for x in closes if x is not None]
        if not closes:return None
        cur=closes[-1]
        return {'n':len(closes),'low':round(min(closes),2),'median':round(statistics.median(closes),2),'high':round(max(closes),2),'current':round(cur,2),'percentile':round(100*sum(x<=cur for x in closes)/len(closes),1)}
    except Exception as e:
        return {'error':str(e)}

def yoy(a,b):
    a,b=num(a),num(b)
    if a is None or b is None:return None
    if b>0:return a/b-1
    if b<=0<a:return 1.0
    if b<0 and a<0:return (abs(b)-abs(a))/abs(b)
    return None

def flatten_with_key_codes(obj):
    out=[]
    def rec(x,keycode=None):
        if isinstance(x,dict):
            local=dict(x)
            if keycode and 'code' not in local and 'stock_code' not in local: local['_key_code']=keycode
            explicit=str(local.get('code') or local.get('stock_code') or local.get('security_code') or local.get('_key_code') or '')
            if len(explicit)==6 and explicit.isdigit(): out.append(local)
            for k,v in x.items():
                kc=str(k) if str(k).isdigit() and len(str(k))==6 else None
                rec(v,kc)
        elif isinstance(x,list):
            for v in x: rec(v,None)
    rec(obj)
    best={}
    for r in out:
        c=str(r.get('code') or r.get('stock_code') or r.get('security_code') or r.get('_key_code') or '')
        if len(c)==6 and (c not in best or len(r)>len(best[c])): best[c]=r
    return best

def l3_info(r):
    if not r:return None,None
    code=name=None
    for k,v in r.items():
        lk=k.lower()
        if any(s in lk for s in ['level3','level_3','sw_level3','sw3']):
            if 'code' in lk: code=str(v)
            if 'name' in lk: name=str(v)
    # common nested structure
    for key in ['sw_level3','level3','industry_level3']:
        v=r.get(key)
        if isinstance(v,dict):
            code=code or str(v.get('code') or '') or None; name=name or str(v.get('name') or '') or None
    return code,name

idx=json.loads(INDEX.read_text(encoding='utf-8'))
bycode=flatten_with_key_codes(idx)
print('INDEX_TOP_LEVEL',type(idx).__name__, list(idx.keys())[:20] if isinstance(idx,dict) else 'list')
print('INDEX_RECORD_COUNT',len(bycode))
print('TARGET_INDEX_RECORDS')
print(json.dumps({c:bycode.get(c) for c in TARGETS},ensure_ascii=False,indent=2))

target_l3={c:l3_info(bycode.get(c)) for c in TARGETS}
peer_groups={}
for c,(l3c,l3n) in target_l3.items():
    peers=[]
    for pc,r in bycode.items():
        rc,rn=l3_info(r)
        if l3c and rc==l3c: peers.append(pc)
        elif not l3c and l3n and rn==l3n: peers.append(pc)
    peer_groups[c]=sorted(set(peers))
print('PEER_GROUPS',json.dumps({c:{'l3':target_l3[c],'count':len(v),'codes':v} for c,v in peer_groups.items()},ensure_ascii=False))

cur=fetch_report('2026-06-30'); prev=fetch_report('2025-06-30'); ann=fetch_report('2025-12-31')
allcodes=sorted(set(TARGETS)|set(x for ps in peer_groups.values() for x in ps))
quotes={}
with ThreadPoolExecutor(max_workers=12) as ex:
    fs={ex.submit(quote,c):c for c in allcodes}
    for f in as_completed(fs):
        c=fs[f]
        try:quotes[c]=f.result()
        except Exception as e:quotes[c]={'error':str(e)}

outputs={}
for c,name in TARGETS.items():
    q=quotes.get(c,{})
    if not q.get('price'):
        try:q=quote(c)
        except Exception as e:q={'error':str(e)}
    h=kline180(c); r=cur.get(c,{ }); rp=prev.get(c,{ }); ra=ann.get(c,{ })
    h1eps=num(r.get('DEDUCT_BASIC_EPS')); p1eps=num(rp.get('DEDUCT_BASIC_EPS')); aeps=num(ra.get('DEDUCT_BASIC_EPS')); growth=yoy(h1eps,p1eps)
    ratio=p1eps/aeps if p1eps is not None and aeps not in (None,0) and p1eps>0 and aeps>0 else None
    if ratio is not None and .20<=ratio<=.80 and h1eps is not None: fwd=h1eps/ratio; fb=f'2025H1/2025A core EPS seasonality={ratio:.1%}'
    elif h1eps is not None: fwd=h1eps*2; fb='H1 core EPS x2 calibration fallback'
    else:fwd=None;fb='missing core EPS'
    pes=[];pbs=[];gs=[]
    for pc in peer_groups[c]:
        pq=quotes.get(pc,{ }); pe=pq.get('dynamic_pe') or pq.get('ttm_pe'); pb=pq.get('pb')
        if pe is not None and 2<=pe<=100:pes.append(pe)
        if pb is not None and .1<=pb<=20:pbs.append(pb)
        g=yoy((cur.get(pc) or {}).get('DEDUCT_BASIC_EPS'),(prev.get(pc) or {}).get('DEDUCT_BASIC_EPS'))
        if g is not None and -.8<=g<=3:gs.append(g)
    ppe=statistics.median(pes) if pes else None; ppb=statistics.median(pbs) if pbs else None; pg=statistics.median(gs) if gs else None
    dyn=q.get('dynamic_pe'); adj=1.; reason='growth near peer median or unavailable'
    if growth is not None and pg is not None:
        if growth-pg>=.20:adj=1.10;reason=f'growth {growth:.1%} >= peer {pg:.1%}+20pp'
        elif growth-pg<=-.20:adj=.90;reason=f'growth {growth:.1%} <= peer {pg:.1%}-20pp'
    fair=None
    if ppe is not None:
        pa=ppe*adj
        if dyn is not None and 2<=dyn<=100:
            aux=min(max(dyn,ppe*.8),ppe*1.2); fair=.75*pa+.25*aux
        else:fair=pa
    elif dyn is not None and 2<=dyn<=100:fair=dyn
    low=fair*.85 if fair else None; high=fair*1.15 if fair else None
    base=fwd*fair if fwd and fair else None; rr=[round(fwd*low,2),round(fwd*high,2)] if fwd and low else None
    mos=.15 if c=='603236' else .20; safe=base*(1-mos) if base else None
    sanity='unavailable'
    if isinstance(h,dict) and h.get('median') and base:
        sanity='ok'
        if base<h['median']*.70 and (growth or 0)>0:sanity='audit: base fair <70% of 180d median despite positive core growth'
        elif base>h['median']*1.50:sanity='audit: base fair >150% of 180d median'
    outputs[c]={'name':name,'l3':target_l3[c],'peer_count':len(peer_groups[c]),'valid_peer_pe':len(pes),'valid_peer_pb':len(pbs),'price':q.get('price'),'dynamic_pe':dyn,'ttm_pe':q.get('ttm_pe'),'pb':q.get('pb'),'core_eps_h1_2026':h1eps,'core_eps_h1_2025':p1eps,'core_eps_2025A':aeps,'core_growth':growth,'peer_growth_median':pg,'peer_pe_median':ppe,'peer_pb_median':ppb,'forward_core_eps':fwd,'forward_basis':fb,'growth_adjustment':adj,'adjustment_reason':reason,'fair_pe':[round(low,2),round(fair,2),round(high,2)] if fair else None,'reasonable_price_range':rr,'base_fair_value':round(base,2) if base else None,'mos':mos,'safe_price_ceiling':round(safe,2) if safe else None,'history_180d':h,'market_sanity':sanity,'value_gap_pct':round(max(0,(q['price']-safe)/q['price']*100),1) if q.get('price') and safe else None}
print('CALIBRATION_RESULT')
print(json.dumps(outputs,ensure_ascii=False,indent=2))
