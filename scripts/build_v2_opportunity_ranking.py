from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMPANY=ROOT/'data/research/v2/company_research.json'
GAP=ROOT/'data/research/v2/price_expectation_gap.json'
OUT=ROOT/'data/research/v2/opportunity_ranking.json'
TZ=ZoneInfo('Asia/Shanghai')
STATE_PRIORITY={'PRIORITY_INFLECTION':6,'RIGHT_PARTICIPATE':5,'LEFT_WATCH':4,'WAIT_BREAKOUT':3,'WAIT_PULLBACK':2,'REJECT':0}

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def clamp(v,lo,hi): return max(lo,min(hi,v))

def choose_state(cr,g):
    rs=cr.get('research_status'); structure=g.get('structure_type'); exp=g.get('expectation_gap_state'); chase=g.get('chase_risk'); vs=g.get('value_gap_state')
    if not cr.get('low_risk_eligible') or rs in {'ineligible_low_risk','quality_review_required','reject'}: return 'REJECT'
    if structure=='damaged' or exp=='fundamental_price_conflict': return 'REJECT'
    if structure=='overheated' or chase=='high': return 'WAIT_PULLBACK'
    if exp=='valuation_review_required': return 'LEFT_WATCH'
    if vs in {'safe_buy_zone','reasonable_buy_zone'}:
        if rs=='pass' and structure=='breakout': return 'PRIORITY_INFLECTION'
        if rs=='pass' and structure in {'pullback','trend_continuation'}: return 'RIGHT_PARTICIPATE'
        return 'LEFT_WATCH' if structure=='base_not_started' else 'WAIT_BREAKOUT'
    if exp in {'gap_just_starting','trend_confirmed_gap_remaining'}:
        if rs=='pass' and structure=='breakout': return 'PRIORITY_INFLECTION'
        if rs=='pass' and structure in {'pullback','trend_continuation'}: return 'RIGHT_PARTICIPATE'
    if exp in {'safe_zone_not_started','reasonable_zone_not_started','deep_value_review'}: return 'LEFT_WATCH'
    if exp=='priced_in_or_overheated': return 'WAIT_PULLBACK' if structure in {'breakout','pullback','trend_continuation','overheated'} else 'REJECT'
    if exp=='gap_above_zone_not_started': return 'WAIT_BREAKOUT' if structure=='transition' else 'LEFT_WATCH'
    return 'WAIT_BREAKOUT' if structure in {'base_not_started','transition'} else 'LEFT_WATCH'

def components(cr,g):
    research={'pass':30,'watch':18,'driver_review_required':8,'earnings_confirmation_required':6}.get(cr.get('research_status'),0)
    triage=clamp(float(cr.get('triage_score') or 0)/8,0,15); bridge=15 if cr.get('forward_bridge_valid') else 0
    gap=clamp(float(g.get('gap_to_reference_mid_pct') or 0)/2,-15,25) if g.get('valuation_reference_status')=='available' else -5
    structure={'breakout':15,'pullback':14,'trend_continuation':12,'base_not_started':6,'transition':4,'overheated':-8,'damaged':-20}.get(g.get('structure_type'),0)
    zone={'safe_buy_zone':10,'reasonable_buy_zone':7,'deep_discount_review':2,'large_gap_above_buy_zone':4,'remaining_gap_above_buy_zone':2,'priced_in':-8}.get(g.get('value_gap_state'),0)
    chase={'low':5,'medium':0,'high':-10}.get(g.get('chase_risk'),0); quality=-6 if cr.get('deducted_profit_verification_required') else 3
    return {'research':round(research+triage,2),'forward_bridge':bridge,'expectation_gap':round(gap,2),'buy_zone':zone,'price_timing':structure,'chase_risk':chase,'earnings_quality_evidence':quality}

def main():
    company=load(COMPANY); gap=load(GAP); cmap=company.get('companies') or {}; grows=gap.get('companies') or {}; ranked=[]
    for code in company.get('selected_for_valuation_codes') or []:
        cr=cmap.get(code) or {}; g=grows.get(code) or {}; state=choose_state(cr,g); comps=components(cr,g); total=round(sum(comps.values()),2)
        primary=(cr.get('driver_links') or [{}])[0].get('driver_id') if cr.get('driver_links') else None
        production_ready=bool(cr.get('production_evidence_ready') and g.get('production_valuation_ready') and state in {'PRIORITY_INFLECTION','RIGHT_PARTICIPATE','LEFT_WATCH'})
        shadow_ready=bool(cr.get('research_status')=='pass' and g.get('valuation_reference_status')=='available' and state in {'PRIORITY_INFLECTION','RIGHT_PARTICIPATE','LEFT_WATCH','WAIT_BREAKOUT'})
        blockers=[]
        if cr.get('deducted_profit_verification_required'): blockers.append('deducted_profit_verification_required')
        if cr.get('driver_review_required'): blockers.append('driver_mapping_review_required')
        if g.get('valuation_reference_status')!='available': blockers.append('fundamental_valuation_anchor_required')
        if not g.get('production_valuation_ready'): blockers.append('formal_buy_zone_required')
        row={'code':code,'name':cr.get('name') or g.get('name') or code,'state':state,'current_price':g.get('current_price'),'primary_driver':primary,'driver_links':cr.get('driver_links') or [],'earnings_direction':cr.get('earnings_direction'),'research_status':cr.get('research_status'),'forward_bridge_valid':cr.get('forward_bridge_valid'),'forward_bridges':cr.get('forward_bridges') or [],
             'expectation_gap_state':g.get('expectation_gap_state'),'value_gap_state':g.get('value_gap_state'),'gap_to_reference_mid_pct':g.get('gap_to_reference_mid_pct'),'fundamental_anchor_range':g.get('fundamental_anchor_range'),'value_anchor_range':g.get('value_anchor_range'),'safe_buy_range':g.get('safe_buy_range'),'reasonable_buy_range':g.get('reasonable_buy_range'),'formal_buy_zone':g.get('formal_buy_zone'),'valuation_anchor_status':g.get('valuation_anchor_status'),'independent_v2_anchor_count':g.get('independent_v2_anchor_count'),'implied_zone_valuation':g.get('implied_zone_valuation'),
             'structure_type':g.get('structure_type'),'structure_action':g.get('structure_action'),'chase_risk':g.get('chase_risk'),'score_components':comps,'diagnostic_score':total,'shadow_priority_eligible':shadow_ready,'production_publish_eligible':production_ready,'blockers':sorted(set(blockers)),'invalidation_conditions':cr.get('invalidation_conditions') or [],'reason':f"research={cr.get('research_status')}; value={g.get('value_gap_state')}; expectation={g.get('expectation_gap_state')}; structure={g.get('structure_type')}; chase={g.get('chase_risk')}"}
        ranked.append(row)
    ranked.sort(key=lambda x:(-STATE_PRIORITY.get(x['state'],0),-float(x.get('diagnostic_score') or 0),x['code']))
    buckets={s:[x for x in ranked if x['state']==s] for s in STATE_PRIORITY}
    def pick(pool):
        out=[]; dc={}
        for x in pool:
            did=x.get('primary_driver') or 'unmapped'
            if dc.get(did,0)>=2: continue
            out.append(x); dc[did]=dc.get(did,0)+1
            if len(out)>=3: break
        return out
    shadow=pick([x for x in ranked if x.get('shadow_priority_eligible')]); prod=pick([x for x in ranked if x.get('production_publish_eligible')])
    payload={'schema_version':2,'mode':'shadow','generated_at':datetime.now(TZ).isoformat(),'reference_trade_date':gap.get('reference_trade_date') or company.get('reference_trade_date'),'ranked_count':len(ranked),'state_counts':{s:len(v) for s,v in buckets.items()},'shadow_priority_eligible_count':sum(1 for x in ranked if x.get('shadow_priority_eligible')),'production_publish_eligible_count':sum(1 for x in ranked if x.get('production_publish_eligible')),'shadow_top3':shadow,'production_top3':prod,'state_buckets':buckets,'ranked_opportunities':ranked,'discipline':['diagnostic score cannot repair evidence gaps','V2 safe/reasonable zones come only from V2 independent anchors','production requires recurring-profit evidence plus a formal buy zone','Top3 may be fewer than three']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ok','ranked':len(ranked),'states':payload['state_counts'],'formal_zone_rows':sum(1 for x in ranked if x.get('formal_buy_zone')),'shadow_top3':[x['code'] for x in shadow],'production_top3':[x['code'] for x in prod]},ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
