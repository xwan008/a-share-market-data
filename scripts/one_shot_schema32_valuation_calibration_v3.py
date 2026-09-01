from __future__ import annotations
import json, math, statistics
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'data/research/company_industry_index.json'; LATEST=ROOT/'data/latest.json'; HIST=ROOT/'data/history_shards'
TARGETS={'601899':'紫金矿业','601225':'陕西煤业','600096':'云天化','603236':'移远通信'}
URL='https://datacenter-web.eastmoney.com/api/data/v1/get'; HEAD={'User-Agent':'Mozilla/5.0 schema32-self-contained'}

def num(x):
    try:
        v=float(x);return v if math.isfinite(v) else None
    except:return None

def yoy(a,b):
    a,b=num(a),num(b)
    if a is None or b is None:return None
    if b>0:return a/b-1
    if b<=0<a:return 1.0
    if b<0 and a<0:return (abs(b)-abs(a))/abs(b)
    return None

def fetch(report,date,date_field):
    out={}
    for page in range(1,15):
        p={'reportName':report,'columns':'ALL','filter':f"({date_field}='{date}')",'pageNumber':page,'pageSize':500,'sortColumns':'SECURITY_CODE','sortTypes':'1'}
        j=requests.get(URL,params=p,headers=HEAD,timeout=40).json(); rows=((j.get('result') or {}).get('data') or [])
        if not rows:break
        for r in rows:
            c=str(r.get('SECURITY_CODE') or '').zfill(6)
            if len(c)==6:out[c]=r
    return out

def flatten_index(obj):
    companies=obj.get('companies') if isinstance(obj,dict) else None
    if isinstance(companies,dict):
        return {str(k):v for k,v in companies.items() if len(str(k))==6}
    return {}

def l3(r): return (r or {}).get('sw_level3_code'),(r or {}).get('sw_level3_name')

def price_map(latest):
    stocks=latest.get('stocks') or {}
    out={}
    if isinstance(stocks,dict):
        for c,v in stocks.items():
            if isinstance(v,dict): out[str(c)]=num(v.get('price') or v.get('close') or v.get('current'))
            else: out[str(c)]=num(v)
    return out

def shares_implied(r):
    p=num((r or {}).get('PARENT_NETPROFIT')); e=num((r or {}).get('BASIC_EPS'))
    return p/e if p is not None and e not in (None,0) and p/e>1e6 else None

def parent_equity(r):
    for k in ['TOTAL_PARENT_EQUITY','PARENT_EQUITY','TOTAL_EQUITY_ATTR_P','TOTAL_EQUITY_PARENT']:
        x=num((r or {}).get(k))
        if x is not None:return x,k
    return None,None

def extract_closes(node):
    vals=[]
    def rec(x):
        if isinstance(x,list):
            # likely list of day dicts
            for v in x:rec(v)
        elif isinstance(x,dict):
            for k in ['close','price','收盘','f2']:
                if k in x:
                    z=num(x[k])
                    if z is not None and z>0: vals.append(z); return
            for v in x.values():rec(v)
    rec(node);return vals

def history180(code):
    for p in HIST.glob('*.json'):
        txt=p.read_text(encoding='utf-8')
        if code not in txt:continue
        try:o=json.loads(txt)
        except:continue
        found=[]
        def seek(x):
            if isinstance(x,dict):
                if code in x:
                    found.extend(extract_closes(x[code]))
                for k,v in x.items():
                    if isinstance(v,(dict,list)):seek(v)
            elif isinstance(x,list):
                for v in x:
                    if isinstance(v,(dict,list)):seek(v)
        seek(o)
        if found:
            vals=found[-180:];cur=vals[-1]
            return {'source':p.name,'n':len(vals),'low':round(min(vals),2),'median':round(statistics.median(vals),2),'high':round(max(vals),2),'current':round(cur,2),'percentile':round(100*sum(x<=cur for x in vals)/len(vals),1)}
    return None

idx=flatten_index(json.loads(INDEX.read_text(encoding='utf-8'))); prices=price_map(json.loads(LATEST.read_text(encoding='utf-8')))
cur=fetch('RPT_LICO_FN_CPD','2026-06-30','REPORTDATE');prev=fetch('RPT_LICO_FN_CPD','2025-06-30','REPORTDATE');ann=fetch('RPT_LICO_FN_CPD','2025-12-31','REPORTDATE')
bal=fetch('RPT_DMSK_FN_BALANCE','2026-06-30','REPORT_DATE')
print('COUNTS',len(idx),len(prices),len(cur),len(prev),len(ann),len(bal))

def metrics(c):
    price=prices.get(c); r=cur.get(c,{}); p=prev.get(c,{}); a=ann.get(c,{})
    h=num(r.get('DEDUCT_BASIC_EPS')); ph=num(p.get('DEDUCT_BASIC_EPS')); ae=num(a.get('DEDUCT_BASIC_EPS'))
    ttm=(ae-ph+h) if None not in (ae,ph,h) else None
    ratio=ph/ae if ph is not None and ae and ph>0 and ae>0 else None
    seasonal=h/ratio if h is not None and ratio and .2<=ratio<=.8 else (h*2 if h is not None else None)
    # Blend TTM + seasonal forward to avoid overcapitalizing a single half-year acceleration.
    fwd=statistics.mean([x for x in [ttm,seasonal] if x is not None and x>0]) if any(x is not None and x>0 for x in [ttm,seasonal]) else None
    core_ttm_pe=price/ttm if price and ttm and ttm>0 else None; fwd_pe=price/fwd if price and fwd and fwd>0 else None
    sh=shares_implied(r); eq,eqfield=parent_equity(bal.get(c,{})); pb=(price*sh/eq) if price and sh and eq and eq>0 else None
    return {'price':price,'h1_core_eps':h,'prev_h1_core_eps':ph,'annual_core_eps':ae,'core_growth':yoy(h,ph),'core_ttm_eps':ttm,'seasonal_forward_eps':seasonal,'forward_core_eps':fwd,'core_pe_ttm':core_ttm_pe,'forward_core_pe':fwd_pe,'pb':pb,'share_basis':sh,'parent_equity':eq,'equity_field':eqfield}

allm={c:metrics(c) for c in idx}
outs={}
for c,name in TARGETS.items():
    lc,ln=l3(idx.get(c)); peers=[pc for pc,r in idx.items() if l3(r)[0]==lc]
    peer_fpe=[allm[x]['forward_core_pe'] for x in peers if allm[x]['forward_core_pe'] is not None and 2<=allm[x]['forward_core_pe']<=80]
    peer_tpe=[allm[x]['core_pe_ttm'] for x in peers if allm[x]['core_pe_ttm'] is not None and 2<=allm[x]['core_pe_ttm']<=80]
    peer_pb=[allm[x]['pb'] for x in peers if allm[x]['pb'] is not None and .1<=allm[x]['pb']<=15]
    peer_g=[allm[x]['core_growth'] for x in peers if allm[x]['core_growth'] is not None and -.8<=allm[x]['core_growth']<=3]
    pf=statistics.median(peer_fpe) if peer_fpe else None; pt=statistics.median(peer_tpe) if peer_tpe else None; ppb=statistics.median(peer_pb) if peer_pb else None; pg=statistics.median(peer_g) if peer_g else None
    me=allm[c]; adj=1.; reason='growth near peer median'
    if me['core_growth'] is not None and pg is not None:
        d=me['core_growth']-pg
        if d>=.20:adj=1.10;reason='core growth >= peer median +20pp'
        elif d<=-.20:adj=.90;reason='core growth <= peer median -20pp'
    # primary anchor is L3 peer forward-core PE; TTM peer PE is sanity only.
    fair=pf*adj if pf else me['forward_core_pe']
    pbflag='ok_or_unavailable'
    if me['pb'] and ppb:
        ratio_pb=me['pb']/ppb
        if ratio_pb>1.5 and (me['core_growth'] or 0)<=(pg or 0): fair*=.90;pbflag='10% PE discount: PB >1.5x peer without growth support'
        elif ratio_pb<.67 and (me['core_growth'] or 0)>=(pg or 0): pbflag='low PB with adequate growth; no mechanical premium'
    low=fair*.85 if fair else None; high=fair*1.15 if fair else None; fwd=me['forward_core_eps']
    base=fair*fwd if fair and fwd else None; rr=[round(low*fwd,2),round(high*fwd,2)] if low and fwd else None
    mos=.15 if c=='603236' else .20; safe=base*(1-mos) if base else None; hist=history180(c)
    sanity='ok_or_unavailable'
    if hist and base:
        if base<hist['median']*.70 and (me['core_growth'] or 0)>0:sanity='AUDIT model <70% of 180d median despite improving core earnings'
        elif base>hist['median']*1.50:sanity='AUDIT model >150% of 180d median'
    outs[c]={**me,'name':name,'l3':[lc,ln],'peer_count':len(peers),'peer_forward_core_pe_median':pf,'peer_core_pe_ttm_median':pt,'peer_pb_median':ppb,'peer_core_growth_median':pg,'growth_adjustment':adj,'growth_adjustment_reason':reason,'pb_cross_check':pbflag,'fair_pe':[round(low,2),round(fair,2),round(high,2)] if fair else None,'reasonable_price_range':rr,'base_fair_value':round(base,2) if base else None,'mos':mos,'safe_price_ceiling':round(safe,2) if safe else None,'history_180d':hist,'market_sanity':sanity,'value_gap_pct':round(max(0,(me['price']-safe)/me['price']*100),1) if me['price'] and safe else None}
print('SELF_CONTAINED_CALIBRATION')
print(json.dumps(outs,ensure_ascii=False,indent=2))
