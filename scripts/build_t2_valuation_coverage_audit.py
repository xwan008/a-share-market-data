from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'data/research/pipeline/common_qualification_pool.json'; FUND=ROOT/'data/research/pipeline/fundamental_valuation.json'; CYCLE=ROOT/'data/research/pipeline/cycle_valuation.json'; OUT=ROOT/'data/research/pipeline/t2_valuation_coverage_audit.json'
TZ=ZoneInfo('Asia/Shanghai')
STRUCTURAL_KEYS=('unsupported_policy','machine_anchor_policy_missing','cycle_policy_missing_machine_readable_anchor','commodity_anchor_fetch_failed','cycle_regime_missing_or_stale','missing_valuation_row')
DATA_KEYS=('consensus_insufficient','forward_consensus_insufficient','market_data_missing','normalization_required','current_price_missing','input_data_insufficient')

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def classify(row):
    text=' '.join(str(row.get(k) or '') for k in ('execution_state','reason','valuation_model'))
    if any(k in text for k in STRUCTURAL_KEYS): return 'structural'
    if any(k in text for k in DATA_KEYS): return 'data'
    return 'other'

def recalled_tags(gate_row: dict) -> list[str]:
    tags=gate_row.get('recall_tags')
    if isinstance(tags,list) and tags:
        return sorted(set(str(x) for x in tags if x))
    fallback=[]
    fallback.extend(gate_row.get('t2_tags') or [])
    fallback.extend(gate_row.get('conditional_t1_tags') or [])
    return sorted(set(str(x) for x in fallback if x))

def main():
    common=load(COMMON); fund=load(FUND); cycle=load(CYCLE)
    rows={str(r.get('code')).zfill(6):r for r in fund.get('companies',[])}
    rows.update({str(r.get('code')).zfill(6):r for r in cycle.get('companies',[])})
    groups=defaultdict(list); modes=defaultdict(set); gate=common.get('future_earnings_gate',{})
    for code in common.get('common_pool_codes',[]):
        code=str(code).zfill(6); g=gate.get(code) or {}
        for tag in recalled_tags(g):
            groups[tag].append(code); modes[tag].add(g.get('gate_mode') or 'unknown')
    details={}; structural_blind=[]; data_blind=[]
    for tag,codes in sorted(groups.items()):
        valid=[]; unavailable=[]; reasons=Counter(); structural=[]; data=[]; other=[]
        for code in sorted(set(codes)):
            r=rows.get(code)
            if not r:
                unavailable.append(code); reasons['structural']+=1; structural.append(code); continue
            if r.get('valuation_status')=='valid': valid.append(code); continue
            unavailable.append(code); bucket=classify(r); reasons[bucket]+=1
            if bucket=='structural': structural.append(code)
            elif bucket=='data': data.append(code)
            else: other.append(code)
        total=len(set(codes)); ratio=len(valid)/total if total else 1.0
        if total and not valid and structural: structural_blind.append(tag)
        if total and not valid and not structural: data_blind.append(tag)
        details[tag]={
            'recall_modes':sorted(modes.get(tag,[])),
            'candidate_count':total,'valid_valuation_count':len(valid),'valid_ratio':round(ratio,4),'valid_codes':valid,
            'unavailable_codes':unavailable,'structural_unavailable_codes':structural,'data_unavailable_codes':data,'other_unavailable_codes':other,
            'unavailable_reason_buckets':dict(reasons)
        }
    all_common=[str(x).zfill(6) for x in common.get('common_pool_codes',[])]
    valid_all=sum(1 for c in all_common if rows.get(c,{}).get('valuation_status')=='valid')
    overall_ratio=valid_all/len(all_common) if all_common else 1.0
    warnings=[]
    if overall_ratio<0.70: warnings.append(f'overall_formal_valuation_coverage_low:{overall_ratio:.1%}')
    for tag,d in details.items():
        if d['candidate_count']>=2 and d['valid_ratio']<0.5 and tag not in structural_blind:
            warnings.append(f'recalled_chain_data_coverage_low:{tag}:{d["valid_ratio"]:.1%}')
    status='PASS' if not structural_blind else 'FAIL'
    payload={
        'schema_version':2,'generated_at':datetime.now(TZ).isoformat(),'common_pool_count':len(all_common),
        'valid_valuation_count':valid_all,'overall_valid_ratio':round(overall_ratio,4),
        'recalled_chain_count':len(details),'recalled_chains':details,
        't2_chain_count':len(details),'t2_chains':details,
        'structural_blind_spot_tags':structural_blind,'data_coverage_blind_spot_tags':data_blind,'coverage_warnings':warnings,
        'hard_gate':{
            'rule':'Any active T1/T2 chain represented in the formal common pool must not have zero valid valuations because of a structural model, policy, anchor or regime defect. Analyst-consensus/data scarcity is disclosed separately and must never be interpreted as no opportunity.',
            'status':status
        }
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':status,'overall_valid_ratio':round(overall_ratio,4),'recalled_chain_count':len(details),'structural_blind_spots':structural_blind,'warnings':warnings[:10]},ensure_ascii=False))
    return 0 if status=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
