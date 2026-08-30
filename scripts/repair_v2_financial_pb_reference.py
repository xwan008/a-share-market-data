from __future__ import annotations

import json, math, re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'data/research/v2/valuation_reference.json'
COMPANY=ROOT/'data/research/v2/company_research.json'
LATEST=ROOT/'data/latest.json'
POLICY=ROOT/'config/valuation_policy_registry.json'
TZ=ZoneInfo('Asia/Shanghai')


def load(p): return json.loads(p.read_text(encoding='utf-8'))
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def detect(cols,contains): return next((c for c in cols if contains in str(c)),None)
def symbol(code): return ('SH' if code.startswith('6') else 'SZ')+code

def load_consensus(ak):
    df=ak.stock_profit_forecast_em(); cols=list(df.columns); code_col=detect(cols,'代码'); report_col=detect(cols,'研报数') or detect(cols,'机构'); eps_cols={}
    for c in cols:
        m=re.search(r'(20\d{2}).*预测.*每股收益',str(c))
        if m: eps_cols[int(m.group(1))]=c
    out={}
    if not code_col:return out
    for _,r in df.iterrows():
        code=str(r.get(code_col,'')).zfill(6)
        if not(code.isdigit() and len(code)==6):continue
        eps={}
        for y,c in eps_cols.items():
            v=num(r.get(c))
            if v and v>0:eps[y]=v
        out[code]={'report_count':int(num(r.get(report_col)) or 0) if report_col else 0,'eps':eps}
    return out

def financial_kind(cr):
    text=' '.join(str(x.get('driver_id') or '') for x in cr.get('driver_links') or [])
    if '证券' in text:return 'broker'
    if '保险' in text:return 'insurance'
    return None

def self_pb_from_comparison(ak,code):
    df=ak.stock_zh_valuation_comparison_em(symbol=symbol(code))
    if df is None or df.empty:return None,None,'empty'
    cols=list(df.columns); code_col=next((c for c in cols if str(c)=='代码'),None); pb_col=next((c for c in cols if '市净率-MRQ' in str(c)),None)
    if not code_col or not pb_col:return None,None,'columns_missing'
    for _,r in df.iterrows():
        c=str(r.get(code_col,'')).zfill(6)
        if c==code:
            pb=num(r.get(pb_col))
            return pb,str(pb_col),None if pb and pb>0 else 'target_pb_missing'
    return None,str(pb_col),'target_row_missing'

def choose_pb_band(policy,roe):
    for band in policy.get('roe_pb_bands') or []:
        mx=num(band.get('roe_max')); rng=band.get('pb_range')
        if mx is not None and isinstance(rng,list) and len(rng)==2 and roe<=mx:return [float(rng[0]),float(rng[1])]
    return None

def main():
    import akshare as ak
    payload=load(REF); company=load(COMPANY); latest=load(LATEST); policies=load(POLICY); consensus=load_consensus(ak); rows=payload.get('companies') or {}; cmap=company.get('companies') or {}; stocks=latest.get('stocks') or {}; year=datetime.now(TZ).year
    min_reports=int((policies.get('forecast_policy') or {}).get('minimum_report_count',3)); repaired=0; errors={}
    for code,row in list(rows.items()):
        if row.get('status')=='available' or row.get('reason')!='market_pb_required':continue
        cr=cmap.get(code) or {}; kind=financial_kind(cr); policy=(policies.get('financial_policies') or {}).get(kind) if kind else None
        if not policy:continue
        c=consensus.get(code) or {'report_count':0,'eps':{}}; reports=int(c.get('report_count') or 0); eps_now=num((c.get('eps') or {}).get(year)); eps_next=num((c.get('eps') or {}).get(year+1)); price=num((stocks.get(code) or {}).get('price'))
        if reports<min_reports or not eps_now or not price:
            errors[code]=f'consensus_or_price_required:reports={reports},eps={eps_now},price={price}'; continue
        try: pb,pb_col,err=self_pb_from_comparison(ak,code)
        except Exception as exc: pb=None; pb_col=None; err=f'{type(exc).__name__}:{exc}'
        if err or not pb:
            errors[code]=err or 'pb_missing'; continue
        bvps=price/pb; roe_now=eps_now/bvps; roe_next=eps_next/bvps if eps_next else None; low_roe=min(roe_now,roe_next) if roe_next is not None else roe_now; mult=choose_pb_band(policy,low_roe)
        if not mult:
            errors[code]='pb_band_required'; continue
        fair=[bvps*mult[0],bvps*mult[1]]
        rows[code]={'code':code,'name':row.get('name') or cr.get('name') or code,'status':'available','reference_source':'v2_forward_pb_roe_fundamental_anchor_peer_table_self_pb_fallback','route':'financial','financial_kind':kind,'reference_range':[round(fair[0],2),round(fair[1],2)],'valuation_model':policy.get('valuation_model'),'valuation_basis_unit':'PB','consensus_eps_current_year':round(eps_now,4),'consensus_eps_next_year':round(eps_next,4) if eps_next else None,'forecast_report_count':reports,'book_value_per_share_proxy':round(bvps,4),'market_pb':round(pb,4),'market_indicator_source':f'eastmoney_peer_comparison_target_row:{pb_col}','forward_roe_current_year':round(roe_now,4),'forward_roe_next_year':round(roe_next,4) if roe_next is not None else None,'low_risk_forward_roe':round(low_roe,4),'reasonable_multiple_reference':mult,'buy_band_policy':{'safe_to_fair_floor':policy.get('safe_to_fair_floor'),'reasonable_to_fair_floor':policy.get('reasonable_to_fair_floor')},'independent_anchor_count':1}
        repaired+=1
    available=sum(1 for x in rows.values() if x.get('status')=='available'); payload['schema_version']=3; payload['generated_at']=datetime.now(TZ).isoformat(); payload['available_count']=available; payload['review_required_count']=len(rows)-available; payload['financial_pb_fallback_repaired_count']=repaired; payload['financial_pb_fallback_errors']=errors
    sc=payload.get('source_counts') or {}; sc['v2_forward_pb_reference']=int(sc.get('v2_forward_pb_reference') or 0)+repaired; sc['market_data_required']=max(0,int(sc.get('market_data_required') or 0)-repaired); payload['source_counts']=sc
    payload['method_note']=str(payload.get('method_note') or '')+' Financial PB fallback reads the target company own PB-MRQ row from Eastmoney peer-comparison data when bulk spot PB is unavailable; peer median is not substituted for target PB.'
    REF.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','repaired':repaired,'errors':errors,'available':available,'review_required':len(rows)-available},ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
