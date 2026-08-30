from __future__ import annotations

import json, math, re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'data/research/v2/valuation_reference.json'
COMPANY=ROOT/'data/research/v2/company_research.json'
LATEST=ROOT/'data/latest.json'
POLICY=ROOT/'config/valuation_policy_registry.json'
CYCLE_POLICY=ROOT/'config/cycle_valuation_policy.json'
CYCLE_REGIME=ROOT/'config/cycle_regime_registry.json'
TZ=ZoneInfo('Asia/Shanghai')


def load(p): return json.loads(p.read_text(encoding='utf-8'))
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def valid_range(v): return isinstance(v,list) and len(v)==2 and all(num(x) is not None for x in v) and float(v[0])>0 and float(v[1])>=float(v[0])
def parse_day(v): return date.fromisoformat(str(v)[:10])
def percentile(vals,q):
    a=sorted(float(x) for x in vals if num(x) is not None)
    if not a:return None
    pos=(len(a)-1)*q; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return a[lo]
    w=pos-lo; return a[lo]*(1-w)+a[hi]*w

def policy_key(tags):
    text=' '.join(tags); mapping=[('船舶制造','shipbuilding'),('重卡','heavy_truck'),('CXO','cxo_cdmo'),('CDMO','cxo_cdmo'),('特高压','grid_equipment'),('电网一次设备','grid_equipment'),('AI服务器','ai_server'),('高速光模块','optical'),('PCB/CCL','pcb_ccl'),('乘用车','passenger_car'),('商用车动力系统','commercial_powertrain'),('数据中心基础设施','data_center_infrastructure'),('航空主机','aviation_oem'),('半导体材料','semiconductor_materials'),('半导体设备','semiconductor_equipment'),('高速连接器/铜互连','high_speed_connector'),('工程机械','construction_machinery'),('船机动力','marine_power'),('创新药','innovative_drug'),('锂电池','lithium_battery'),('风电整机/零部件','wind_equipment'),('纺织制造','textile_manufacturing'),('核电','nuclear_utility')]
    for needle,key in mapping:
        if needle in text:return key
    return None

def financial_kind(tags):
    text=' '.join(tags)
    if '证券' in text:return 'broker'
    if '保险' in text:return 'insurance'
    return None

def choose_pb_band(policy,roe):
    for band in policy.get('roe_pb_bands') or []:
        mx=num(band.get('roe_max')); rng=band.get('pb_range')
        if mx is not None and roe<=mx and valid_range(rng): return [float(rng[0]),float(rng[1])]
    return None

def load_consensus(ak):
    try: df=ak.stock_profit_forecast_em()
    except Exception:return {}
    cols=list(df.columns); code_col=next((c for c in cols if '代码' in str(c)),None); report_col=next((c for c in cols if '研报数' in str(c)),None); eps_cols={}
    for c in cols:
        m=re.search(r'(20\d{2}).*预测.*每股收益',str(c))
        if m:eps_cols[int(m.group(1))]=c
    out={}
    if not code_col:return out
    for _,r in df.iterrows():
        code=str(r.get(code_col,'')).zfill(6); eps={}
        if not(code.isdigit() and len(code)==6):continue
        for y,c in eps_cols.items():
            v=num(r.get(c))
            if v and v>0:eps[y]=v
        out[code]={'report_count':int(num(r.get(report_col)) or 0) if report_col else 0,'eps':eps}
    return out

def baidu_pb(ak,code):
    df=ak.stock_zh_valuation_baidu(symbol=code,indicator='市净率',period='近一年')
    if df is None or df.empty:return None
    col=next((c for c in df.columns if str(c).lower()=='value'),None)
    if not col:return None
    vals=[num(x) for x in df[col].tolist()]; vals=[x for x in vals if x and x>0]
    return vals[-1] if vals else None

def cycle_policy_for(tags,code,cfg):
    sub=cfg.get('subchain_policies') or {}; tag=next((t for t in tags if t in sub),None)
    if not tag:return None,None
    p=dict(sub[tag]); p.update((cfg.get('company_overrides') or {}).get(code) or {}); return tag,p

def regime_for(tag,code,cfg):
    r=dict((cfg.get('subchains') or {}).get(tag) or {}); r.update((cfg.get('company_overrides') or {}).get(code) or {}); return r or None

def fetch_futures_anchor(ak,symbol,ref,window,min_sessions):
    df=ak.futures_zh_daily_sina(symbol=symbol)
    if df is None or df.empty:raise RuntimeError('empty')
    dc=next((c for c in df.columns if str(c).lower()=='date'),None); cc=next((c for c in df.columns if str(c).lower()=='close'),None)
    pairs=[(str(r.get(dc))[:10],num(r.get(cc))) for _,r in df.iterrows()]; pairs=[x for x in pairs if x[1] and x[1]>0]
    if len(pairs)<min_sessions:raise RuntimeError(f'insufficient:{len(pairs)}')
    last=pairs[-1][0]
    if (parse_day(ref)-parse_day(last)).days>7:raise RuntimeError(f'stale:{last}')
    vals=[x[1] for x in pairs]; med=percentile(vals[-min(window,len(vals)):],.5); return {'symbol':symbol,'last_date':last,'current':vals[-1],'neutral_median':med,'current_to_neutral':vals[-1]/med}

def repair_cycle(ak,code,name,price,tags,cr,policy_cfg,regimes,ref,anchor_cache,anchor_errors):
    tag,p=cycle_policy_for(tags,code,policy_cfg)
    if not tag:return None
    ttm=num(((cr.get('financial_evidence') or {}).get('ttm_deducted_eps')))
    if not ttm or ttm<=0 or not cr.get('forward_bridge_valid'):return None
    regime=regime_for(tag,code,regimes)
    if not regime:return None
    factors=regime.get('bear_base_bull_earnings_factor') or [0.85,0.95,1.05]; mult=regime.get('multiple_range_by_regime') or p.get('fallback_multiple_range')
    if not(valid_range(mult) and isinstance(factors,list) and len(factors)==3):return None
    anchors=p.get('anchors') or []; normalization=1.0; anchor_rows=[]
    if anchors:
        neutral_cfg=policy_cfg.get('neutral_commodity_policy') or {}; window=int(neutral_cfg.get('window_sessions',504)); minimum=int(neutral_cfg.get('minimum_sessions',252)); delta=0.0
        for a in anchors:
            s=a.get('symbol')
            if s not in anchor_cache and s not in anchor_errors:
                try:anchor_cache[s]=fetch_futures_anchor(ak,s,ref,window,minimum)
                except Exception as exc:anchor_errors[s]=f'{type(exc).__name__}:{exc}'
            if s in anchor_errors:return None
            m=anchor_cache[s]; w=float(a.get('weight',1)); direction=float(a.get('direction',1)); delta+=w*(m['current_to_neutral']-1)*direction; anchor_rows.append({**m,'weight':w,'direction':direction})
        sensitivity=float(p.get('earnings_sensitivity',0.8)); raw=1/(1+max(0,delta)*sensitivity); normalization=max(float(neutral_cfg.get('min_normalization_factor',0.70)),min(1.0,raw)); base=ttm*normalization*min(float(factors[1]),1.0); method='ttm_deducted_eps_neutral_commodity_then_regime'
    else:
        single=min(float(p.get('anchorless_normalization_haircut',1.0)),float(factors[1]),1.0); normalization=single; base=ttm*single; method='ttm_deducted_eps_single_cycle_factor'
    lo,hi=float(mult[0]),float(mult[1]); fair=[base*lo,base*hi]
    return {'code':code,'name':name,'status':'available','reference_source':'v2_cycle_ttm_deducted_fallback','route':'cycle','cycle_tag':tag,'reference_range':[round(fair[0],2),round(fair[1],2)],'valuation_model':'v2_cycle_ttm_deducted_fallback','valuation_basis_unit':'PE','ttm_deducted_eps':round(ttm,4),'normalized_ttm_deducted_eps':round(base,4),'normalization_factor':round(normalization,4),'earnings_normalization_method':method,'reasonable_multiple_reference':[lo,hi],'market_pe_on_ttm_deducted_eps':round(price/ttm,2) if price else None,'commodity_anchors':anchor_rows,'cycle_regime':regime.get('regime'),'buy_band_policy':{'safe_to_fair_floor':p.get('safe_to_fair_floor'),'reasonable_to_fair_floor':p.get('reasonable_to_fair_floor')},'independent_anchor_count':1,'fallback_note':'No H1 simple annualization. Uses statement-derived TTM deducted EPS plus existing cycle normalization and forward-bridge gate.'}

def main():
    import akshare as ak
    ref=load(REF); company=load(COMPANY); latest=load(LATEST); policies=load(POLICY); cycle_cfg=load(CYCLE_POLICY); regimes=load(CYCLE_REGIME); cons=load_consensus(ak); rows=ref.get('companies') or {}; cmap=company.get('companies') or {}; stocks=latest.get('stocks') or {}; now=datetime.now(TZ); repaired={'business_ttm':0,'financial_pb_baidu':0,'cycle_ttm':0}; errors={}; anchor_cache={}; anchor_errors={}
    for code,row in list(rows.items()):
        if row.get('status')=='available':continue
        cr=cmap.get(code) or {}; tags=[x.get('driver_id') for x in cr.get('driver_links') or [] if x.get('driver_id')]; name=cr.get('name') or row.get('name') or code; price=num((stocks.get(code) or {}).get('price')); ttm=num(((cr.get('financial_evidence') or {}).get('ttm_deducted_eps')))
        cyc=repair_cycle(ak,code,name,price,tags,cr,cycle_cfg,regimes,str(ref.get('reference_trade_date') or '')[:10],anchor_cache,anchor_errors)
        if cyc:
            rows[code]=cyc; repaired['cycle_ttm']+=1; continue
        kind=financial_kind(tags)
        if kind:
            policy=(policies.get('financial_policies') or {}).get(kind); c=cons.get(code) or {}; eps=num((c.get('eps') or {}).get(now.year)) or ttm
            if policy and price and eps and eps>0:
                try:pb=baidu_pb(ak,code)
                except Exception as exc:pb=None; errors[code]=f'baidu_pb:{type(exc).__name__}:{exc}'
                if pb and pb>0:
                    bvps=price/pb; roe=eps/bvps; mult=choose_pb_band(policy,roe)
                    if mult:
                        fair=[bvps*mult[0],bvps*mult[1]]; rows[code]={'code':code,'name':name,'status':'available','reference_source':'v2_pb_roe_baidu_pb_fallback','route':'financial','financial_kind':kind,'reference_range':[round(fair[0],2),round(fair[1],2)],'valuation_model':policy.get('valuation_model'),'valuation_basis_unit':'PB','earnings_basis':'consensus_eps' if num((c.get('eps') or {}).get(now.year)) else 'ttm_deducted_eps','earnings_per_share_basis':round(eps,4),'book_value_per_share_proxy':round(bvps,4),'market_pb':round(pb,4),'market_indicator_source':'baidu_valuation_pb_latest','roe_basis':round(roe,4),'reasonable_multiple_reference':mult,'buy_band_policy':{'safe_to_fair_floor':policy.get('safe_to_fair_floor'),'reasonable_to_fair_floor':policy.get('reasonable_to_fair_floor')},'independent_anchor_count':1}; repaired['financial_pb_baidu']+=1; continue
        key=policy_key(tags); policy=(policies.get('company_overrides') or {}).get(code) or ((policies.get('business_policies') or {}).get(key) if key else None)
        if policy and ttm and ttm>0 and cr.get('forward_bridge_valid'):
            mult=policy.get('multiple_range')
            if valid_range(mult):
                lo,hi=float(mult[0]),float(mult[1]); fair=[ttm*lo,ttm*hi]; entry=policy.get('low_risk_multiple_range'); entry_ref=[ttm*float(entry[0]),ttm*float(entry[1])] if valid_range(entry) else None
                rows[code]={'code':code,'name':name,'status':'available','reference_source':'v2_ttm_deducted_eps_fallback','route':'business','reference_range':[round(fair[0],2),round(fair[1],2)],'valuation_model':f'{key or "company"}_ttm_deducted_pe_fallback','valuation_basis_unit':'PE','ttm_deducted_eps':round(ttm,4),'earnings_basis':'reported_ttm_deducted_eps','reasonable_multiple_reference':[lo,hi],'explicit_entry_multiple_range':[float(entry[0]),float(entry[1])] if valid_range(entry) else None,'explicit_entry_reference_range':[round(entry_ref[0],2),round(entry_ref[1],2)] if entry_ref else None,'buy_band_policy':{'safe_to_fair_floor':policy.get('safe_to_fair_floor'),'reasonable_to_fair_floor':policy.get('reasonable_to_fair_floor')},'market_pe_on_ttm_deducted_eps':round(price/ttm,2) if price else None,'independent_anchor_count':1,'fallback_note':'TTM deducted EPS = FY2025 + H1 2026 - H1 2025; requires company forward bridge; never simple H1 annualization.'}; repaired['business_ttm']+=1
    available=sum(1 for x in rows.values() if x.get('status')=='available'); ref['schema_version']=4; ref['generated_at']=datetime.now(TZ).isoformat(); ref['companies']=rows; ref['available_count']=available; ref['review_required_count']=len(rows)-available; ref['valuation_fallback_repaired_counts']=repaired; ref['valuation_fallback_errors']=errors; ref['commodity_anchor_errors']={**(ref.get('commodity_anchor_errors') or {}),**anchor_errors}; ref['method_note']=str(ref.get('method_note') or '')+' Review rows may be repaired by statement-derived TTM deducted EPS, Baidu target-company PB, or cycle-normalized TTM deducted EPS. Fallbacks require positive recurring earnings and forward bridge; no H1 simple annualization.'
    REF.write_text(json.dumps(ref,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','repaired':repaired,'available':available,'review_required':len(rows)-available,'errors':len(errors),'anchor_errors':anchor_errors},ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
