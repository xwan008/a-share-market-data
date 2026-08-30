from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMPANY=ROOT/'data/research/v2/company_research.json'
PRICE=ROOT/'data/research/v2/full_market_price_structure.json'
ANCHORS=ROOT/'data/research/v2/valuation_anchors.json'
OUT=ROOT/'data/research/v2/price_expectation_gap.json'
TZ=ZoneInfo('Asia/Shanghai')

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def valid_range(v): return isinstance(v,list) and len(v)==2 and all(isinstance(x,(int,float)) for x in v) and v[0]>0 and v[1]>=v[0]

def value_state(price,row):
    if not row.get('formal_buy_zone_ready'): return 'valuation_review_required',None
    safe=row.get('safe_buy_range'); reasonable=row.get('reasonable_buy_range'); fair=(row.get('fundamental_anchor') or {}).get('reference_range')
    if not(valid_range(safe) and valid_range(reasonable)): return 'valuation_review_required',None
    ref_mid=sum(fair)/2 if valid_range(fair) else reasonable[1]
    gap=(ref_mid/price-1)*100 if price and price>0 else None
    # Exact entry-zone semantics: a price must actually lie inside [low, high].
    # Below the lower bound is not automatically "safer"; it requires value-trap review.
    if price < safe[0]*0.85: return 'deep_discount_review',gap
    if price < safe[0]: return 'below_safe_zone_review',gap
    if safe[0] <= price <= safe[1]: return 'safe_buy_zone',gap
    if reasonable[0] <= price <= reasonable[1]: return 'reasonable_buy_zone',gap
    if safe[1] < price < reasonable[0]: return 'between_buy_zones_review',gap
    if gap is not None and gap>=20: return 'large_gap_above_buy_zone',gap
    if gap is not None and gap>=5: return 'remaining_gap_above_buy_zone',gap
    return 'priced_in',gap

def combine(vs,structure):
    if vs=='valuation_review_required': return 'valuation_review_required'
    if vs in {'deep_discount_review','below_safe_zone_review'}: return 'fundamental_price_conflict' if structure=='damaged' else 'deep_value_review'
    if vs=='between_buy_zones_review': return 'buy_zone_boundary_review'
    if structure=='damaged': return 'fundamental_price_conflict'
    if vs=='safe_buy_zone':
        if structure in {'breakout','pullback'}: return 'gap_just_starting'
        if structure=='trend_continuation': return 'trend_confirmed_gap_remaining'
        return 'safe_zone_not_started'
    if vs=='reasonable_buy_zone':
        if structure in {'breakout','pullback'}: return 'gap_just_starting'
        if structure=='trend_continuation': return 'trend_confirmed_gap_remaining'
        return 'reasonable_zone_not_started'
    if structure=='overheated' or vs=='priced_in': return 'priced_in_or_overheated'
    if vs in {'large_gap_above_buy_zone','remaining_gap_above_buy_zone'} and structure in {'base_not_started','transition'}: return 'gap_above_zone_not_started'
    if vs in {'large_gap_above_buy_zone','remaining_gap_above_buy_zone'} and structure in {'breakout','pullback'}: return 'gap_just_starting'
    if vs in {'large_gap_above_buy_zone','remaining_gap_above_buy_zone'} and structure=='trend_continuation': return 'trend_confirmed_gap_remaining'
    return 'gap_unclear_or_limited'

def main():
    company=load(COMPANY); price=load(PRICE); anchors=load(ANCHORS); cmap=company.get('companies') or {}; pmap=price.get('companies') or {}; amap=anchors.get('companies') or {}; codes=company.get('selected_for_valuation_codes') or []
    rows={}; counts={}; formal=0
    for code in codes:
        cr=cmap.get(code) or {}; pr=pmap.get(code) or {}; ar=amap.get(code) or {}; current=pr.get('current_price') or ar.get('current_price')
        vs,gap=value_state(float(current),ar) if isinstance(current,(int,float)) and current>0 else ('valuation_review_required',None)
        structure=pr.get('structure_type') or 'unavailable'; expectation=combine(vs,structure); counts[expectation]=counts.get(expectation,0)+1
        if ar.get('formal_buy_zone_ready'): formal+=1
        rows[code]={
            'code':code,'name':cr.get('name') or pr.get('name') or ar.get('name') or code,'current_price':current,
            'research_status':cr.get('research_status'),'forward_bridge_valid':cr.get('forward_bridge_valid'),
            'valuation_reference_status':'available' if (ar.get('fundamental_anchor') or {}).get('status')=='available' else 'review_required',
            'valuation_anchor_status':ar.get('status'),'independent_v2_anchor_count':ar.get('independent_anchor_count') or 0,
            'fundamental_anchor_range':(ar.get('fundamental_anchor') or {}).get('reference_range'),'peer_anchor':ar.get('peer_anchor'),
            'history_cost_anchor':ar.get('history_cost_anchor'),'formal_buy_zone':{'safe':ar.get('safe_buy_range'),'reasonable':ar.get('reasonable_buy_range')} if ar.get('formal_buy_zone_ready') else None,
            'safe_buy_range':ar.get('safe_buy_range'),'reasonable_buy_range':ar.get('reasonable_buy_range'),'value_anchor_range':ar.get('value_anchor_range'),
            'formal_buy_zone_status':'ready' if ar.get('formal_buy_zone_ready') else ar.get('status'),'value_gap_state':vs,'gap_to_reference_mid_pct':round(gap,2) if gap is not None else None,
            'structure_type':structure,'structure_action':pr.get('action'),'chase_risk':pr.get('chase_risk'),'relative_strength_20d_vs_market_pct':pr.get('relative_strength_20d_vs_market_pct'),'price_discovery':pr.get('price_discovery'),
            'expectation_gap_state':expectation,'production_valuation_ready':bool(ar.get('formal_buy_zone_ready')),
            'implied_zone_valuation':{k:v for k,v in ar.items() if k in {'safe_implied_pe','reasonable_implied_pe','safe_implied_pb','reasonable_implied_pb'}},
            'method_note':'Expectation gap uses exact V2 safe/reasonable interval membership; prices below the safe lower bound require value-trap review and are not entry eligible.'
        }
    payload={'schema_version':3,'mode':'shadow','generated_at':datetime.now(TZ).isoformat(),'reference_trade_date':price.get('reference_trade_date') or company.get('reference_trade_date'),'valuation_queue_count':len(codes),'formal_buy_zone_ready_count':formal,'expectation_gap_state_counts':counts,'production_valuation_ready_count':formal,'companies':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','valuation_queue':len(codes),'formal_zones':formal,'states':counts},ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
