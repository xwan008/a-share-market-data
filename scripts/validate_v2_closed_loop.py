from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DRIVERS=ROOT/'data/research/v2/earnings_driver_scan.json'
COMPANY=ROOT/'data/research/v2/company_research.json'
VALUATION=ROOT/'data/research/v2/valuation_reference.json'
ANCHORS=ROOT/'data/research/v2/valuation_anchors.json'
PRICE=ROOT/'data/research/v2/full_market_price_structure.json'
GAP=ROOT/'data/research/v2/price_expectation_gap.json'
RANK=ROOT/'data/research/v2/opportunity_ranking.json'
ENTRY_VALUE_STATES={'safe_buy_zone','reasonable_buy_zone'}

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def vr(v): return isinstance(v,list) and len(v)==2 and all(isinstance(x,(int,float)) for x in v) and v[0]>0 and v[1]>=v[0]
def nondeg(v): return vr(v) and v[1]>v[0] and (v[1]/v[0]-1)*100>=0.99

def main():
    errors=[]; outputs=(DRIVERS,COMPANY,VALUATION,ANCHORS,PRICE,GAP,RANK)
    for p in outputs:
        if not p.exists(): errors.append(f'missing_output:{p.name}')
    if errors:
        print(json.dumps({'status':'FAIL','errors':errors},ensure_ascii=False,indent=2)); return 2
    d,c,v,a,p,g,r=map(load,outputs)
    if any(x.get('mode')!='shadow' for x in (d,c,v,a,p,g,r)): errors.append('non_shadow_output_detected')
    ref=p.get('reference_trade_date')
    for name,x in (('company',c),('valuation',v),('anchors',a),('gap',g),('ranking',r)):
        if x.get('reference_trade_date')!=ref: errors.append(f"reference_trade_date_mismatch:{name}:{x.get('reference_trade_date')}!={ref}")
    active=[x for x in d.get('drivers',[]) if x.get('active')]
    for x in active:
        if not x.get('direct_profit_driver') or not x.get('evidence_for'): errors.append(f"active_driver_without_profit_evidence:{x.get('driver_id')}")
    if (d.get('driver_policy') or {}).get('legacy_t1_t2_controls_eligibility') is not False: errors.append('legacy_tier_still_controls_driver_eligibility')
    cmap=c.get('companies') or {}
    for code in c.get('research_pass_codes') or []:
        row=cmap.get(code) or {}
        if row.get('risk_warning') or not row.get('low_risk_eligible'): errors.append(f'risk_warning_in_research_pass:{code}')
        if not row.get('forward_bridge_valid'): errors.append(f'research_pass_without_forward_bridge:{code}')
    for code in c.get('production_evidence_ready_codes') or []:
        row=cmap.get(code) or {}; ev=row.get('financial_evidence') or {}
        if not ev.get('recurring_profit_verified'): errors.append(f'production_evidence_without_recurring_profit:{code}')
        if not ev.get('cashflow_quality_verified'): errors.append(f'production_evidence_without_cashflow_quality:{code}')
        if row.get('deducted_profit_verification_required'): errors.append(f'production_evidence_still_requires_deducted_profit:{code}')
        if not row.get('forward_bridge_valid'): errors.append(f'production_evidence_without_forward_bridge:{code}')
    selected=set(c.get('selected_for_valuation_codes') or [])
    if not selected.issubset(set(cmap)): errors.append('valuation_queue_not_subset_of_company_research')
    vrows=v.get('companies') or {}; arows=a.get('companies') or {}; grows=g.get('companies') or {}
    if set(vrows)!=selected: errors.append(f'valuation_reference_company_set_mismatch:{len(vrows)}!={len(selected)}')
    if set(arows)!=selected: errors.append(f'valuation_anchor_company_set_mismatch:{len(arows)}!={len(selected)}')
    if set(grows)!=selected: errors.append(f'gap_company_set_mismatch:{len(grows)}!={len(selected)}')
    for code,row in vrows.items():
        n=int(row.get('independent_anchor_count') or 0)
        if row.get('status')=='available' and (n!=1 or not vr(row.get('reference_range'))): errors.append(f'invalid_first_anchor:{code}')
        if row.get('status')!='available' and n!=0: errors.append(f'review_reference_with_nonzero_anchor:{code}:{n}')
    for code,row in arows.items():
        ready=bool(row.get('formal_buy_zone_ready')); n=int(row.get('independent_anchor_count') or 0); status=row.get('status')
        if ready:
            safe=row.get('safe_buy_range'); reasonable=row.get('reasonable_buy_range')
            if n<2: errors.append(f'formal_zone_without_two_confirming_anchors:{code}:{n}')
            if not nondeg(safe) or not nondeg(reasonable): errors.append(f'formal_zone_degenerate_or_invalid:{code}:{safe}:{reasonable}')
            elif safe[1]>reasonable[0]+1e-9: errors.append(f'zone_overlap_order_invalid:{code}:{safe}:{reasonable}')
            if status!='valid': errors.append(f'formal_zone_with_nonvalid_status:{code}:{status}')
        if status in {'valuation_divergence','fundamental_history_divergence','insufficient_confirming_anchors','nondegenerate_buy_zone_required'} and ready:
            errors.append(f'blocked_anchor_state_cannot_publish_zone:{code}:{status}')
        if row.get('peer_confirmed') and not row.get('peer_anchor'): errors.append(f'peer_confirmed_without_peer_anchor:{code}')
        if row.get('history_confirmed') and not row.get('history_cost_anchor'): errors.append(f'history_confirmed_without_history:{code}')
    for code,row in grows.items():
        ar=arows.get(code) or {}; n=int(row.get('independent_v2_anchor_count') or 0); expected=int(ar.get('independent_anchor_count') or 0)
        if n!=expected: errors.append(f'gap_anchor_count_mismatch:{code}:{n}!={expected}')
        if bool(row.get('formal_buy_zone'))!=bool(ar.get('formal_buy_zone_ready')): errors.append(f'gap_formal_zone_readiness_mismatch:{code}')
        if row.get('formal_buy_zone') and (row.get('safe_buy_range')!=ar.get('safe_buy_range') or row.get('reasonable_buy_range')!=ar.get('reasonable_buy_range')): errors.append(f'gap_zone_value_mismatch:{code}')
    ranked=r.get('ranked_opportunities') or []; by={x.get('code'):x for x in ranked}
    if set(by)!=selected: errors.append(f'ranking_company_set_mismatch:{len(by)}!={len(selected)}')
    for code,row in by.items():
        gr=grows.get(code) or {}; cr=cmap.get(code) or {}
        if bool(row.get('formal_buy_zone'))!=bool(gr.get('formal_buy_zone')): errors.append(f'ranking_zone_mismatch:{code}')
        if row.get('production_publish_eligible'):
            if not gr.get('production_valuation_ready'): errors.append(f'production_without_formal_zone:{code}')
            if row.get('value_gap_state') not in ENTRY_VALUE_STATES: errors.append(f'production_price_not_inside_entry_zone:{code}:{row.get("value_gap_state")}')
            if not row.get('entry_price_eligible'): errors.append(f'production_without_entry_price_flag:{code}')
            if not cr.get('production_evidence_ready'): errors.append(f'production_without_statement_evidence:{code}')
    for x in r.get('shadow_top3') or []:
        code=x.get('code'); row=by.get(code) or {}; cr=cmap.get(code) or {}
        if not row.get('shadow_priority_eligible'): errors.append(f'shadow_top3_not_eligible:{code}')
        if cr.get('risk_warning'): errors.append(f'risk_warning_in_shadow_top3:{code}')
    for x in r.get('production_top3') or []:
        if not x.get('production_publish_eligible') or not x.get('formal_buy_zone') or not x.get('entry_price_eligible'): errors.append(f'production_top3_without_complete_new_entry_gate:{x.get("code")}')
    status='PASS' if not errors else 'FAIL'; ac=a.get('counts') or {}; fs=c.get('financial_evidence_summary') or {}
    print(json.dumps({'status':status,'errors':errors,'counts':{'active_drivers':len(active),'company_recall':len(cmap),'research_pass':len(c.get('research_pass_codes') or []),'statement_recurring_verified':fs.get('recurring_profit_verified_count'),'statement_production_evidence_ready':fs.get('production_evidence_ready_count'),'valuation_queue':len(selected),'first_anchor_available':v.get('available_count'),'valuation_fallback_repairs':v.get('valuation_fallback_repaired_counts'),'formal_buy_zone_ready':ac.get('formal_zone_ready'),'valuation_divergence':ac.get('valuation_divergence'),'fundamental_history_divergence':ac.get('fundamental_history_divergence'),'insufficient_confirming_anchors':ac.get('insufficient_confirming_anchors'),'entry_price_eligible':r.get('entry_price_eligible_count'),'ranked':len(ranked),'shadow_top3':len(r.get('shadow_top3') or []),'production_top3':len(r.get('production_top3') or [])}},ensure_ascii=False,indent=2)); return 0 if not errors else 2

if __name__=='__main__': raise SystemExit(main())
