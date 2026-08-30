from __future__ import annotations

import importlib.util, json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('cycle_base',ROOT/'scripts/build_cycle_valuation.py')
BASE=importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader; SPEC.loader.exec_module(BASE)
COMMON=ROOT/'data/research/pipeline/common_qualification_pool.json'; LATEST=ROOT/'data/latest.json'
POLICY=ROOT/'config/cycle_valuation_policy.json'; REGIME=ROOT/'config/cycle_regime_registry.json'; OUT=ROOT/'data/research/pipeline/cycle_valuation.json'
TZ=ZoneInfo('Asia/Shanghai')

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    import akshare as ak
    out=load(OUT); common=load(COMMON); latest=load(LATEST); cfg=load(POLICY); reg=load(REGIME)
    consensus=BASE.load_consensus(ak); stocks=latest.get('stocks',{}); gate=common.get('future_earnings_gate',{})
    now=datetime.now(TZ); year=now.year; min_reports=int(cfg['forward_earnings_policy'].get('minimum_report_count',3))
    market_policy=cfg.get('low_risk_price_calibration',{}); ref=BASE.parse_day(out['reference_trade_date']); review=BASE.parse_day(reg['reviewed_at'])
    regime_age=(ref-review).days; max_age=int(reg.get('max_review_age_days',45)); repaired=[]; pending=[]; left=[]
    for row in out.get('companies',[]):
        code=str(row.get('code')).zfill(6); tag=row.get('cycle_tag'); p=dict(cfg.get('subchain_policies',{}).get(tag,{})); p.update(cfg.get('company_overrides',{}).get(code,{}))
        mode=p.get('valuation_mode','commodity_anchor_normalized'); row['valuation_mode']=mode
        if mode!='conservative_consensus_cycle':
            if row.get('valuation_status')=='valid' and row.get('left_conclusion') in {'safe_buy_zone','reasonable_buy_zone'}: left.append(code)
            continue
        c=consensus.get(code,{'report_count':0,'eps':{}}); reports=int(c.get('report_count') or 0); eps0=BASE.num(c.get('eps',{}).get(year)); eps1=BASE.num(c.get('eps',{}).get(year+1))
        price=BASE.num((stocks.get(code) or {}).get('price')) or BASE.num(row.get('current_price')); regime=BASE.regime_for(tag,code,reg)
        problems=[]
        if price is None: problems.append('current_price_missing')
        if reports<min_reports or eps0 is None or eps1 is None: problems.append(f'forward_consensus_insufficient:reports={reports},eps_{year}={eps0},eps_{year+1}={eps1}')
        if not regime or regime_age < -7 or regime_age > max_age: problems.append(f'cycle_regime_missing_or_stale:age_days={regime_age}:max={max_age}')
        if problems:
            row.update({'valuation_status':'unavailable','execution_state':'input_data_insufficient','valuation_model':'conservative_consensus_cycle_low_risk','commodity_anchors':[],'reasonable_multiple_range':None,'value_anchor_range':None,'safe_buy_range':None,'reasonable_buy_range':None,'left_conclusion':'unavailable','reason':';'.join(problems),'forward_earnings_basis':f'{year} EPS primary; {year+1} only downside guard; no TTM/H1 annualization substitute.'}); pending.append(code); continue
        haircut=float(p.get('anchorless_normalization_haircut',0.85)); guarded=min(eps0,eps1); normalized=guarded*haircut
        factors=regime.get('bear_base_bull_earnings_factor'); mult=regime.get('multiple_range_by_regime') or p.get('fallback_multiple_range')
        if not isinstance(factors,list) or len(factors)!=3 or not isinstance(mult,list) or len(mult)!=2: raise RuntimeError(f'bad_anchorless_policy:{code}')
        scenarios=[max(0.01,normalized*float(x)) for x in factors]; lo,hi=float(mult[0]),float(mult[1]); fair=scenarios[1]*lo
        market=BASE.load_market_price_anchor(code,market_policy); safe,reasonable,value,method=BASE.calibrate_low_risk_buy_bands(fair,market,p,market_policy)
        conclusion='safe_buy_zone' if price<=safe[1] else ('reasonable_buy_zone' if price<=reasonable[1] else 'above_buy_zone')
        fwd,w0,w1=BASE.calendar_forward_eps(eps0,eps1,now)
        row.update({'current_price':round(price,3),'valuation_status':'valid','execution_state':'valid','valuation_model':'conservative_consensus_cycle_low_risk','valuation_basis_unit':'PE','forecast_source':'akshare.stock_profit_forecast_em','forecast_report_count':reports,'consensus_eps_current_year':round(eps0,4),'consensus_eps_next_year':round(eps1,4),'next_year_eps_growth_pct':round((eps1/eps0-1)*100,2),'forward_12m_eps_proxy':round(fwd,4),'forward_eps_weights':{'current_year':round(w0,4),'next_year':round(w1,4)},'low_risk_eps_pre_haircut':round(guarded,4),'low_risk_eps_guard_method':'next_year_downside_guard' if eps1<eps0 else 'current_year_primary_no_positive_next_year_uplift','anchorless_cycle_haircut':haircut,'normalized_forward_eps':round(normalized,4),'neutralization_factor':haircut,'weighted_neutral_commodity_delta':None,'market_forward_pe_current_year':round(price/eps0,2),'market_forward_pe_next_year':round(price/eps1,2),'market_forward_pe_12m_proxy':round(price/fwd,2),'commodity_anchors':[],'short_term_anchor_effect_on_eps':None,'low_risk_short_term_effect_on_eps':0.0,'profit_sensitivity':None,'cycle_regime':regime.get('regime'),'cycle_regime_reviewed_at':reg.get('reviewed_at'),'cycle_regime_age_days':regime_age,'cycle_regime_summary':regime.get('summary'),'cycle_regime_scores':{'supply':regime.get('supply_score'),'demand':regime.get('demand_score'),'inventory':regime.get('inventory_score')},'cycle_regime_evidence':regime.get('evidence',[]),'bear_base_bull_regime_factor':[round(float(x),4) for x in factors],'bear_base_bull_forward_eps':[round(x,4) for x in scenarios],'forward_earnings_basis':f'{year} EPS {eps0:.4f} primary; {year+1} EPS {eps1:.4f} only downside guard -> haircut {haircut:.2f} -> reviewed regime -> 180d calibration.','reasonable_multiple_range':[lo,hi],'multiple_rationale':p.get('rationale') or regime.get('summary'),'scenario_fair_value_range':[round(scenarios[0]*lo,2),round(scenarios[2]*hi,2)],'normalized_base_fair_value_floor':round(fair,2),'base_fair_value_floor':round(fair,2),'market_price_anchor_180d':market,'price_calibration_method':method,'value_anchor_range':[round(value[0],2),round(value[1],2)],'safe_buy_range':[round(safe[0],2),round(safe[1],2)],'reasonable_buy_range':[round(reasonable[0],2),round(reasonable[1],2)],'key_sensitivities':['2026 consensus EPS','2027 downside durability','cycle regime','structural haircut','180d market price distribution'],'invalidation_condition':(gate.get(code) or {}).get('invalidation_condition') or row.get('invalidation_condition') or 'cycle earnings bridge invalidated','left_conclusion':conclusion,'reason':None}); repaired.append(code)
        if conclusion in {'safe_buy_zone','reasonable_buy_zone'}: left.append(code)
    out['schema_version']=5; out['generated_at']=datetime.now(TZ).isoformat(); out['left_set_codes']=sorted(set(left)); out['anchorless_cycle_repaired_codes']=sorted(repaired); out['anchorless_cycle_still_unavailable_codes']=sorted(pending)
    out['method_note']='Machine-anchor cycles use long-window commodity normalization. Anchorless cycles use current-year EPS primary, next-year downside guard, structural haircut, reviewed regime and 180d price calibration.'
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'status':'ok','repaired':len(repaired),'pending':len(pending),'left':len(out['left_set_codes'])},ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
