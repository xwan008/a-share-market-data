from __future__ import annotations

import json, math, re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'data/research/pipeline/common_qualification_pool.json'
LATEST=ROOT/'data/latest.json'
POLICY=ROOT/'config/valuation_policy_registry.json'
OUT=ROOT/'data/research/pipeline/fundamental_valuation.json'
TZ=ZoneInfo('Asia/Shanghai')
CYCLE_KEYS=('铜矿资源','电解铝','动力煤','氟化工','氨纶')


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
    s=' '.join(tags); mapping=[('船舶制造','shipbuilding'),('重卡','heavy_truck'),('CXO','cxo_cdmo'),('CDMO','cxo_cdmo'),('特高压','grid_equipment'),('电网一次设备','grid_equipment'),('AI服务器','ai_server'),('高速光模块','optical'),('PCB/CCL','pcb_ccl')]
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


def zone(price,fair_floor,policy,default_band):
    sb=policy.get('safe_to_fair_floor') or default_band.get('safe_to_fair_floor') or [0.75,0.88]
    rb=policy.get('reasonable_to_fair_floor') or default_band.get('reasonable_to_fair_floor') or [0.88,1.0]
    safe=[fair_floor*sb[0],fair_floor*sb[1]]; reasonable=[fair_floor*rb[0],fair_floor*rb[1]]
    conclusion='safe_buy_zone' if price<=safe[1] else ('reasonable_buy_zone' if price<=reasonable[1] else 'above_buy_zone')
    return safe,reasonable,conclusion


def main():
    import akshare as ak
    common=load(COMMON); latest=load(LATEST); policies=load(POLICY); stocks=latest.get('stocks',{})
    consensus=load_consensus(ak); spot,spot_errors=load_spot_indicators(ak)
    year=datetime.now(TZ).year; min_reports=int(policies.get('forecast_policy',{}).get('minimum_report_count',3)); default_band=policies.get('default_buy_band',{})
    companies=[]; left=[]; cycle_codes=[]; unsupported=[]; supported=[]
    execution={'valid':0,'consensus_insufficient':0,'market_data_missing':0,'normalization_required':0,'unsupported_policy':0}; model_counts={}

    for code in common.get('common_pool_codes',[]):
        gate=common['future_earnings_gate'][code]; tags=gate.get('t2_tags') or []; tag_text=' '.join(tags)
        if any(k in tag_text for k in CYCLE_KEYS): cycle_codes.append(code); continue
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
            bvps=price/pb; roe_now=eps_now/bvps; roe_next=eps_next/bvps if eps_next else None; froe=roe_next if roe_next is not None else roe_now; mult=choose_pb_band(policy,froe)
            if not mult: raise RuntimeError(f'financial PB band missing:{code}:roe={froe}')
            lo,hi=mult; fair_lo,fair_hi=bvps*lo,bvps*hi; safe,reasonable,conclusion=zone(price,fair_lo,policy,default_band)
            row={'code':code,'name':name,'current_price':round(price,3),'valuation_status':'valid','execution_state':'valid','policy_status':'supported','valuation_model':model,'valuation_basis_unit':'PB','forecast_source':'akshare.stock_profit_forecast_em+Eastmoney_A_share_spot','forecast_report_count':reports,'consensus_eps_current_year':round(eps_now,4),'consensus_eps_next_year':round(eps_next,4) if eps_next else None,'book_value_per_share_proxy':round(bvps,4),'market_pb':round(pb,4),'market_indicator_source':market_source,'forward_roe_current_year':round(roe_now,4),'forward_roe_next_year':round(roe_next,4) if roe_next is not None else None,'market_pe_dynamic':round(pe_dyn,4) if pe_dyn else None,'market_forward_pe_current_year':round(price/eps_now,2),'market_forward_pe_next_year':round(price/eps_next,2) if eps_next else None,'forward_earnings_basis':f'BVPS proxy={bvps:.4f} from market PB ({market_source}); {year}/{year+1} consensus maps to Forward ROE then versioned PB band.','reasonable_multiple_range':[lo,hi],'multiple_rationale':policy.get('rationale'),'value_anchor_range':[round(fair_lo,2),round(fair_hi,2)],'safe_buy_range':[round(safe[0],2),round(safe[1],2)],'reasonable_buy_range':[round(reasonable[0],2),round(reasonable[1],2)],'key_sensitivities':['forward ROE','book value quality','market activity/investment return'],'invalidation_condition':gate.get('invalidation_condition') or 'forward ROE or book-value bridge deteriorates','left_conclusion':conclusion}
        else:
            mult=policy.get('multiple_range')
            if not isinstance(mult,list) or len(mult)!=2:
                unsupported.append(code); execution['unsupported_policy']+=1; companies.append({'code':code,'name':name,'current_price':price,'valuation_status':'unavailable','execution_state':'unsupported_policy','policy_status':'unsupported','valuation_model':model or 'unsupported_business_model','valuation_basis_unit':'PE','forecast_source':'akshare.stock_profit_forecast_em','forecast_report_count':reports,'forward_earnings_basis':'Versioned multiple_range missing.','reasonable_multiple_range':None,'value_anchor_range':None,'safe_buy_range':None,'reasonable_buy_range':None,'key_sensitivities':['valuation policy'],'invalidation_condition':'policy coverage repaired','left_conclusion':'unavailable','reason':'versioned_multiple_missing'}); continue
            lo,hi=map(float,mult); fair_lo,fair_hi=eps_now*lo,eps_now*hi; safe,reasonable,conclusion=zone(price,fair_lo,policy,default_band)
            row={'code':code,'name':name,'current_price':round(price,3),'valuation_status':'valid','execution_state':'valid','policy_status':'supported','valuation_model':model,'valuation_basis_unit':'PE','forecast_source':'akshare.stock_profit_forecast_em','forecast_report_count':reports,'consensus_eps_current_year':round(eps_now,4),'consensus_eps_next_year':round(eps_next,4) if eps_next else None,'next_year_eps_growth_pct':round(growth,2) if growth is not None else None,'market_pe_dynamic':round(pe_dyn,4) if pe_dyn else None,'market_forward_pe_current_year':round(price/eps_now,2),'market_forward_pe_next_year':round(price/eps_next,2) if eps_next else None,'forward_earnings_basis':f'{year} consensus EPS={eps_now:.4f}; {year+1} EPS={eps_next:.4f}' if eps_next else f'{year} consensus EPS={eps_now:.4f}; next-year EPS unavailable.','reasonable_multiple_range':[lo,hi],'multiple_rationale':policy.get('rationale') or 'Versioned business valuation policy.','value_anchor_range':[round(fair_lo,2),round(fair_hi,2)],'safe_buy_range':[round(safe[0],2),round(safe[1],2)],'reasonable_buy_range':[round(reasonable[0],2),round(reasonable[1],2)],'key_sensitivities':['future earnings','consensus revisions','reasonable multiple'],'invalidation_condition':gate.get('invalidation_condition') or 'future earnings bridge invalidated','left_conclusion':conclusion}
        execution['valid']+=1; model_counts[row['valuation_model']]=model_counts.get(row['valuation_model'],0)+1
        if row['left_conclusion'] in {'safe_buy_zone','reasonable_buy_zone'}: left.append(code)
        companies.append(row)

    payload={'schema_version':4,'generated_at':datetime.now(TZ).isoformat(),'common_pool_count':len(common.get('common_pool_codes',[])),'fundamental_company_count':len(companies),'deferred_cycle_codes':sorted(cycle_codes),'market_indicator_errors':spot_errors,'policy_coverage':{'noncycle_count':len(companies),'supported_policy_count':len(set(supported)),'unsupported_policy_count':len(set(unsupported)),'supported_policy_codes':sorted(set(supported)),'unsupported_policy_codes':sorted(set(unsupported)),'execution_counts':execution,'model_counts':dict(sorted(model_counts.items()))},'companies':companies,'left_set_codes':sorted(left),'method_note':'All non-cycle candidates require versioned policy. PE uses consensus Forward EPS. Brokers/insurers execute Forward ROE-PB; PB is loaded from all-A Eastmoney data with SH-A/SZ-A fallback. Data insufficiency remains explicit.'}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','fundamental':len(companies),'cycle_deferred':len(cycle_codes),'left':len(left),'unsupported_policy':len(set(unsupported)),'execution':execution,'market_indicator_errors':spot_errors},ensure_ascii=False))
    return 0


if __name__=='__main__': raise SystemExit(main())
