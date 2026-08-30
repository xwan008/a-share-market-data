from __future__ import annotations

import json, math, re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'data/research/pipeline/common_qualification_pool.json'
LATEST=ROOT/'data/latest.json'
POLICY=ROOT/'config/valuation_policy_registry.json'
CYCLE_POLICY=ROOT/'config/cycle_valuation_policy.json'
OUT=ROOT/'data/research/pipeline/fundamental_valuation.json'
TZ=ZoneInfo('Asia/Shanghai')


def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None


def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))


def detect_col(columns, exact=None, contains=None):
    for c in columns:
        s=str(c)
        if exact and s==exact: return c
        if contains and contains in s: return c
    return None


def load_consensus(ak):
    df=ak.stock_profit_forecast_em(); cols=list(df.columns)
    code_col=detect_col(cols,contains='代码'); report_col=detect_col(cols,contains='研报数') or detect_col(cols,contains='机构')
    eps_cols={}
    for c in cols:
        m=re.search(r'(20\d{2}).*预测.*每股收益',str(c))
        if m: eps_cols[int(m.group(1))]=c
    if not code_col: raise RuntimeError(f'profit forecast code column not found:{cols}')
    out={}
    for _,r in df.iterrows():
        code=str(r.get(code_col,'')).zfill(6)
        if not (code.isdigit() and len(code)==6): continue
        row={'report_count':int(num(r.get(report_col)) or 0),'eps':{}}
        for y,c in eps_cols.items():
            v=num(r.get(c))
            if v and v>0: row['eps'][y]=v
        out[code]=row
    return out


def parse_spot_df(df, source):
    if df is None or df.empty: return {}
    cols=list(df.columns); code_col=detect_col(cols,contains='代码')
    pb_col=detect_col(cols,exact='市净率') or detect_col(cols,contains='市净率')
    pe_col=detect_col(cols,exact='市盈率-动态') or detect_col(cols,contains='市盈率')
    if not code_col: return {}
    out={}
    for _,r in df.iterrows():
        code=str(r.get(code_col,'')).zfill(6)
        if not (code.isdigit() and len(code)==6): continue
        out[code]={'pb':num(r.get(pb_col)) if pb_col else None,'pe_dynamic':num(r.get(pe_col)) if pe_col else None,'source':source}
    return out


def load_spot_indicators(ak):
    """Prefer all-A bulk data, then fill missing PB/PE from official SH-A/SZ-A Eastmoney endpoints."""
    out={}; errors=[]
    calls=[('stock_zh_a_spot_em',getattr(ak,'stock_zh_a_spot_em',None)),('stock_sh_a_spot_em',getattr(ak,'stock_sh_a_spot_em',None)),('stock_sz_a_spot_em',getattr(ak,'stock_sz_a_spot_em',None))]
    for source,fn in calls:
        if fn is None: continue
        try: rows=parse_spot_df(fn(),source)
        except Exception as exc:
            errors.append(f'{source}:{type(exc).__name__}:{exc}'); continue
        for code,row in rows.items():
            if code not in out: out[code]=row
            else:
                if not out[code].get('pb') and row.get('pb'): out[code]['pb']=row['pb']; out[code]['source']=source
                if not out[code].get('pe_dynamic') and row.get('pe_dynamic'): out[code]['pe_dynamic']=row['pe_dynamic']
    return out, errors


def business_policy(tags,policies):
    """Map an earnings-driver tag to a versioned non-cycle business PE policy."""
    s=' '.join(tags)
    mapping=[
        ('船舶制造','shipbuilding'),('重卡','heavy_truck'),('CXO','cxo_cdmo'),('CDMO','cxo_cdmo'),
        ('特高压','grid_equipment'),('电网一次设备','grid_equipment'),('AI服务器','ai_server'),
        ('高速光模块','optical'),('PCB/CCL','pcb_ccl'),('乘用车','passenger_car'),
        ('商用车动力系统','commercial_powertrain'),('数据中心基础设施','data_center_infrastructure'),
        ('航空主机','aviation_oem'),('半导体材料','semiconductor_materials'),('半导体设备','semiconductor_equipment'),
        ('高速连接器/铜互连','high_speed_connector'),('工程机械','construction_machinery'),('船机动力','marine_power'),
        ('创新药','innovative_drug'),('锂电池','lithium_battery'),('风电整机/零部件','wind_equipment'),
        ('纺织制造','textile_manufacturing'),('核电','nuclear_utility'),
    ]
    for needle,key in mapping:
        if needle in s and policies.get('business_policies',{}).get(key): return policies['business_policies'][key],key
    return None,None


def financial_policy(tags,policies):
    s=' '.join(tags)
    if '证券' in s: return policies.get('financial_policies',{}).get('broker'),'broker'
    if '保险' in s: return policies.get('financial_policies',{}).get('insurance'),'insurance'
    return None,None


def choose_pb_band(policy,forward_roe):
    for band in policy.get('roe_pb_bands',[]):
        mx=num(band.get('roe_max')); rng=band.get('pb_range')
        if mx is not None and forward_roe<=mx and isinstance(rng,list) and len(rng)==2: return [float(rng[0]),float(rng[1])]
    return None


def choose_low_risk_forward_roe(roe_now, roe_next):
    if roe_next is None: return roe_now, 'current_year_only'
    if roe_next < roe_now: return roe_next, 'next_year_downside_guard'
    return roe_now, 'current_year_primary_no_positive_next_year_uplift'


def growth_pe_floor_cap(growth_pct, policies):
    if growth_pct is None: return None
    cfg=policies.get('low_risk_pe_policy',{})
    for band in cfg.get('growth_floor_caps',[]):
        mx=num(band.get('growth_max_pct')); cap=num(band.get('pe_floor_cap'))
        if mx is not None and cap is not None and growth_pct<=mx: return float(cap)
    return None


def choose_low_risk_pe_range(policy, growth_pct, policies):
    theoretical=policy.get('multiple_range')
    if not isinstance(theoretical,list) or len(theoretical)!=2: return None,None,None,None
    theo_lo,theo_hi=map(float,theoretical)
    explicit=policy.get('low_risk_multiple_range'); cap=growth_pe_floor_cap(growth_pct,policies)
    if isinstance(explicit,list) and len(explicit)==2:
        lo,hi=map(float,explicit); return [lo,hi],[theo_lo,theo_hi],cap,'company_explicit_low_risk_pe'
    lo=theo_lo if cap is None else min(theo_lo,cap)
    width=float(policies.get('low_risk_pe_policy',{}).get('derived_range_width',4)); hi=min(theo_hi,max(lo,lo+width))
    method='theoretical_pe_unchanged' if lo==theo_lo and hi==theo_hi else 'growth_guarded_low_risk_pe'
    return [lo,hi],[theo_lo,theo_hi],cap,method


def zone(price,fair_floor,policy,default_band):
    sb=policy.get('safe_to_fair_floor') or default_band.get('safe_to_fair_floor') or [0.78,0.90]
    rb=policy.get('reasonable_to_fair_floor') or default_band.get('reasonable_to_fair_floor') or [0.90,1.0]
    safe=[fair_floor*sb[0],fair_floor*sb[1]]; reasonable=[fair_floor*rb[0],fair_floor*rb[1]]
    conclusion='safe_buy_zone' if price<=safe[1] else ('reasonable_buy_zone' if price<=reasonable[1] else 'above_buy_zone')
    return safe,reasonable,conclusion


def main():
    import akshare as ak
    common=load(COMMON); latest=load(LATEST); policies=load(POLICY); cycle_policy=load(CYCLE_POLICY); stocks=latest.get('stocks',{})
    cycle_tags=set(cycle_policy.get('subchain_policies',{})); consensus=load_consensus(ak); spot,spot_errors=load_spot_indicators(ak)
    year=datetime.now(TZ).year; min_reports=int(policies.get('forecast_policy',{}).get('minimum_report_count',3)); default_band=policies.get('default_buy_band',{})
    companies=[]; left=[]; cycle_codes=[]; unsupported=[]; supported=[]
    execution={'valid':0,'consensus_insufficient':0,'market_data_missing':0,'normalization_required':0,'unsupported_policy':0}; model_counts={}

    for code in common.get('common_pool_codes',[]):
        gate=common['future_earnings_gate'][code]; tags=gate.get('recall_tags') or gate.get('t2_tags') or []
        if any(tag in cycle_tags for tag in tags): cycle_codes.append(code); continue
        name=gate.get('name') or (stocks.get(code) or {}).get('name') or code; price=num((stocks.get(code) or {}).get('price'))
        override=policies.get('company_overrides',{}).get(code); fin,fin_key=financial_policy(tags,policies); base,key=business_policy(tags,policies)
        policy=override or fin or base; kind='financial_pb_roe' if fin and not override else 'forward_pe'
        model=(override or {}).get('valuation_model') if override else (fin.get('valuation_model') if fin else (f'{key}_forward_pe' if base else None))
        state=None; reason=None
        if not policy:
            unsupported.append(code); execution['unsupported_policy']+=1; state='unsupported_policy'; reason='No versioned valuation policy mapped; coverage defect.'
        else: supported.append(code)
        c=consensus.get(code,{'report_count':0,'eps':{}}); reports=int(c.get('report_count') or 0); eps_now=num(c.get('eps',{}).get(year)); eps_next=num(c.get('eps',{}).get(year+1))
        growth=((eps_next/eps_now)-1)*100 if eps_now and eps_next else None; market=spot.get(code,{}); pb=num(market.get('pb')); pe_dyn=num(market.get('pe_dynamic')); market_source=market.get('source')
        if state is None and override and override.get('requires_normalized_earnings_bridge'):
            state='normalization_required'; execution[state]+=1; reason='Material one-off/investment-income effects require normalized recurring earnings bridge.'
        elif state is None and (eps_now is None or reports<min_reports):
            state='consensus_insufficient'; execution[state]+=1; reason=f'Consensus insufficient:reports={reports},eps_{year}={eps_now}; H1 annualization cannot form formal anchor.'
        elif state is None and price is None:
            state='market_data_missing'; execution[state]+=1; reason='Current price missing.'
        if state:
            row={'code':code,'name':name,'current_price':price,'valuation_status':'unavailable','execution_state':state,'policy_status':'unsupported' if state=='unsupported_policy' else 'supported','valuation_model':model or 'unsupported_business_model','valuation_basis_unit':'PB' if kind=='financial_pb_roe' else 'PE','forecast_source':'analyst_consensus' if eps_now else 'none','forecast_report_count':reports,'consensus_eps_current_year':round(eps_now,4) if eps_now else None,'consensus_eps_next_year':round(eps_next,4) if eps_next else None,'forward_earnings_basis':f'{year}/{year+1} consensus primary; H1 annualization cannot create formal anchor.','reasonable_multiple_range':None,'value_anchor_range':None,'reasonable_buy_range':None,'safe_buy_range':None,'market_pb':round(pb,4) if pb else None,'market_pe_dynamic':round(pe_dyn,4) if pe_dyn else None,'market_indicator_source':market_source,'key_sensitivities':['future earnings','consensus revisions','valuation policy'],'invalidation_condition':gate.get('invalidation_condition') or 'future earnings bridge invalidated','left_conclusion':'unavailable','reason':reason}
            companies.append(row); model_counts[row['valuation_model']]=model_counts.get(row['valuation_model'],0)+1; continue

        if kind=='financial_pb_roe':
            if pb is None or pb<=0:
                execution['market_data_missing']+=1
                row={'code':code,'name':name,'current_price':price,'valuation_status':'unavailable','execution_state':'market_data_missing','policy_status':'supported','valuation_model':model,'valuation_basis_unit':'PB','forecast_source':'akshare.stock_profit_forecast_em','forecast_report_count':reports,'consensus_eps_current_year':round(eps_now,4),'consensus_eps_next_year':round(eps_next,4) if eps_next else None,'forward_earnings_basis':'Forward ROE-PB bridge requires current PB/BVPS proxy; all-A and SH/SZ fallback endpoints returned no positive PB.','reasonable_multiple_range':None,'value_anchor_range':None,'reasonable_buy_range':None,'safe_buy_range':None,'market_indicator_source':market_source,'key_sensitivities':['forward ROE','market activity/investment return','book value quality'],'invalidation_condition':gate.get('invalidation_condition') or 'forward ROE bridge invalidated','left_conclusion':'unavailable','reason':'market_pb_missing'}
                companies.append(row); model_counts[model]=model_counts.get(model,0)+1; continue
            bvps=price/pb; roe_now=eps_now/bvps; roe_next=eps_next/bvps if eps_next else None; low_risk_roe,roe_method=choose_low_risk_forward_roe(roe_now,roe_next); mult=choose_pb_band(policy,low_risk_roe)
            if not mult: raise RuntimeError(f'financial PB band missing:{code}:roe={low_risk_roe}')
            lo,hi=mult; fair_lo,fair_hi=bvps*lo,bvps*hi; safe,reasonable,conclusion=zone(price,fair_lo,policy,default_band)
            row={'code':code,'name':name,'current_price':round(price,3),'valuation_status':'valid','execution_state':'valid','policy_status':'supported','valuation_model':model,'valuation_basis_unit':'PB','forecast_source':'akshare.stock_profit_forecast_em+Eastmoney_A_share_spot','forecast_report_count':reports,'consensus_eps_current_year':round(eps_now,4),'consensus_eps_next_year':round(eps_next,4) if eps_next else None,'book_value_per_share_proxy':round(bvps,4),'market_pb':round(pb,4),'market_indicator_source':market_source,'forward_roe_current_year':round(roe_now,4),'forward_roe_next_year':round(roe_next,4) if roe_next is not None else None,'low_risk_forward_roe':round(low_risk_roe,4),'low_risk_roe_method':roe_method,'market_pe_dynamic':round(pe_dyn,4) if pe_dyn else None,'market_forward_pe_current_year':round(price/eps_now,2),'market_forward_pe_next_year':round(price/eps_next,2) if eps_next else None,'forward_earnings_basis':f'BVPS proxy={bvps:.4f}; {year} Forward ROE is the primary PB-band anchor and {year+1} ROE can only lower, not raise, the low-risk PB band.','reasonable_multiple_range':[lo,hi],'multiple_rationale':policy.get('rationale'),'value_anchor_range':[round(fair_lo,2),round(fair_hi,2)],'safe_buy_range':[round(safe[0],2),round(safe[1],2)],'reasonable_buy_range':[round(reasonable[0],2),round(reasonable[1],2)],'key_sensitivities':['current-year forward ROE','next-year downside durability','book value quality','market activity/investment return'],'invalidation_condition':gate.get('invalidation_condition') or 'forward ROE or book-value bridge deteriorates','left_conclusion':conclusion}
        else:
            low_risk_mult,theoretical_mult,growth_cap,pe_method=choose_low_risk_pe_range(policy,growth,policies)
            if not low_risk_mult or not theoretical_mult:
                unsupported.append(code); execution['unsupported_policy']+=1; companies.append({'code':code,'name':name,'current_price':price,'valuation_status':'unavailable','execution_state':'unsupported_policy','policy_status':'unsupported','valuation_model':model or 'unsupported_business_model','valuation_basis_unit':'PE','forecast_source':'akshare.stock_profit_forecast_em','forecast_report_count':reports,'forward_earnings_basis':'Versioned multiple_range missing.','reasonable_multiple_range':None,'value_anchor_range':None,'safe_buy_range':None,'reasonable_buy_range':None,'key_sensitivities':['valuation policy'],'invalidation_condition':'policy coverage repaired','left_conclusion':'unavailable','reason':'versioned_multiple_missing'}); continue
            lo,hi=low_risk_mult; theo_lo,theo_hi=theoretical_mult
            fair_lo,fair_hi=eps_now*lo,eps_now*hi; business_fair_lo,business_fair_hi=eps_now*theo_lo,eps_now*theo_hi
            safe,reasonable,conclusion=zone(price,fair_lo,policy,default_band)
            row={'code':code,'name':name,'current_price':round(price,3),'valuation_status':'valid','execution_state':'valid','policy_status':'supported','valuation_model':model,'valuation_basis_unit':'PE','forecast_source':'akshare.stock_profit_forecast_em','forecast_report_count':reports,'consensus_eps_current_year':round(eps_now,4),'consensus_eps_next_year':round(eps_next,4) if eps_next else None,'next_year_eps_growth_pct':round(growth,2) if growth is not None else None,'market_forward_pe_current_year':round(price/eps_now,2),'market_forward_pe_next_year':round(price/eps_next,2) if eps_next else None,'market_pe_dynamic':round(pe_dyn,4) if pe_dyn else None,'market_indicator_source':market_source,'forward_earnings_basis':f'{year} consensus EPS is primary low-risk anchor; {year+1} EPS is a durability guard and positive growth cannot lift the {year} entry PE.','theoretical_business_multiple_range':[theo_lo,theo_hi],'growth_pe_floor_cap':growth_cap,'low_risk_pe_method':pe_method,'reasonable_multiple_range':[lo,hi],'multiple_rationale':policy.get('rationale'),'business_fair_value_range':[round(business_fair_lo,2),round(business_fair_hi,2)],'value_anchor_range':[round(fair_lo,2),round(fair_hi,2)],'safe_buy_range':[round(safe[0],2),round(safe[1],2)],'reasonable_buy_range':[round(reasonable[0],2),round(reasonable[1],2)],'key_sensitivities':['current-year EPS','next-year downside durability','company/industry low-risk PE','orders/volume/margin'],'invalidation_condition':gate.get('invalidation_condition') or 'future earnings bridge or business multiple deteriorates','left_conclusion':conclusion}
        execution['valid']+=1; companies.append(row); model_counts[model]=model_counts.get(model,0)+1
        if conclusion in {'safe_buy_zone','reasonable_buy_zone'}: left.append(code)

    payload={'schema_version':5,'generated_at':datetime.now(TZ).isoformat(),'reference_trade_date':latest.get('trade_date'),'common_pool_count':len(common.get('common_pool_codes',[])),'fundamental_company_count':len(companies),'deferred_to_cycle_valuation_count':len(cycle_codes),'deferred_to_cycle_valuation_codes':sorted(cycle_codes),'forecast_policy':policies.get('forecast_policy'),'low_risk_pe_policy':policies.get('low_risk_pe_policy'),'policy_coverage':{'supported_count':len(set(supported)),'unsupported_count':len(set(unsupported)),'unsupported_codes':sorted(set(unsupported))},'execution_state_counts':execution,'market_indicator_errors':spot_errors,'model_counts':model_counts,'companies':companies,'left_set_codes':sorted(left)}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','fundamental':len(companies),'cycle_deferred':len(cycle_codes),'left':len(left),'unsupported_policy':len(set(unsupported)),'execution':execution,'market_indicator_errors':spot_errors[:3]},ensure_ascii=False)); return 0


if __name__=='__main__': raise SystemExit(main())
