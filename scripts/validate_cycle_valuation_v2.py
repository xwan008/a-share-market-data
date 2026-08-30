from __future__ import annotations

import json, sys
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/research/pipeline/cycle_valuation.json'; POLICY=ROOT/'config/cycle_valuation_policy.json'

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def rng(v): return isinstance(v,list) and len(v)==2 and all(isinstance(x,(int,float)) for x in v) and v[0]<=v[1]
def day(v):
    try: return date.fromisoformat(str(v)[:10])
    except Exception: return None

def main():
    out=load(OUT); cfg=load(POLICY); errors=[]; rows=out.get('companies',[]); seen=set(); declared={str(x).zfill(6) for x in out.get('cycle_codes',[])}
    ref=day(out.get('reference_trade_date')); max_anchor=int(out.get('max_anchor_age_days',7)); regime_age=out.get('cycle_regime_age_days'); max_regime=out.get('max_cycle_regime_age_days')
    if not isinstance(rows,list): errors.append('companies_not_list'); rows=[]
    for r in rows:
        code=str(r.get('code')).zfill(6); tag=r.get('cycle_tag'); seen.add(code); p=dict(cfg.get('subchain_policies',{}).get(tag,{})); p.update(cfg.get('company_overrides',{}).get(code,{})); mode=r.get('valuation_mode') or p.get('valuation_mode','commodity_anchor_normalized')
        if not p: errors.append(f'{code}:missing_cycle_policy')
        if r.get('valuation_status') not in {'valid','unavailable'}: errors.append(f'{code}:bad_status')
        if not r.get('valuation_model') or not r.get('forward_earnings_basis') or not r.get('invalidation_condition'): errors.append(f'{code}:missing_contract_fields')
        if r.get('valuation_status')!='valid':
            if not r.get('reason'): errors.append(f'{code}:unavailable_without_reason')
            continue
        for k in ('reasonable_multiple_range','value_anchor_range','safe_buy_range','reasonable_buy_range'):
            if not rng(r.get(k)): errors.append(f'{code}:bad_{k}')
        for k in ('consensus_eps_current_year','consensus_eps_next_year','forward_12m_eps_proxy','normalized_forward_eps'):
            if not isinstance(r.get(k),(int,float)) or r.get(k)<=0: errors.append(f'{code}:missing_{k}')
        if not r.get('cycle_regime') or not r.get('cycle_regime_summary') or not r.get('cycle_regime_evidence'): errors.append(f'{code}:missing_regime')
        if not isinstance(r.get('bear_base_bull_forward_eps'),list) or len(r.get('bear_base_bull_forward_eps'))!=3: errors.append(f'{code}:missing_scenarios')
        if mode=='commodity_anchor_normalized':
            anchors=r.get('commodity_anchors')
            if not anchors: errors.append(f'{code}:machine_mode_without_anchors')
            if isinstance(anchors,list) and ref:
                for a in anchors:
                    d=day((a or {}).get('last_date'))
                    if not d or not -1 <= (ref-d).days <= max_anchor: errors.append(f'{code}:stale_anchor:{(a or {}).get("symbol")}')
        elif mode=='conservative_consensus_cycle':
            h=r.get('anchorless_cycle_haircut')
            if not isinstance(h,(int,float)) or not 0.60<=h<=1.0: errors.append(f'{code}:bad_anchorless_haircut')
            if r.get('commodity_anchors') not in ([],None): errors.append(f'{code}:anchorless_mode_has_anchors')
            if not isinstance(r.get('low_risk_eps_pre_haircut'),(int,float)) or r.get('low_risk_eps_pre_haircut')<=0: errors.append(f'{code}:missing_guarded_eps')
        else: errors.append(f'{code}:unknown_valuation_mode:{mode}')
    if seen!=declared: errors.append(f'declared_mismatch:{len(seen)}!={len(declared)}')
    if not isinstance(regime_age,int) or not isinstance(max_regime,int) or not -7<=regime_age<=max_regime: errors.append('registry_stale')
    print(json.dumps({'status':'PASS' if not errors else 'FAIL','cycle_count':len(rows),'errors':errors[:50]},ensure_ascii=False)); return 0 if not errors else 2

if __name__=='__main__': raise SystemExit(main())
