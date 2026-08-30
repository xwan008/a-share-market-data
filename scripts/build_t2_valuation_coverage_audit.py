from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'data/research/pipeline/common_qualification_pool.json'; FUND=ROOT/'data/research/pipeline/fundamental_valuation.json'; CYCLE=ROOT/'data/research/pipeline/cycle_valuation.json'; OUT=ROOT/'data/research/pipeline/t2_valuation_coverage_audit.json'
TZ=ZoneInfo('Asia/Shanghai')
STRUCTURAL_KEYS=('unsupported_policy','machine_anchor_policy_missing','cycle_policy_missing_machine_readable_anchor','commodity_anchor_fetch_failed','cycle_regime_missing_or_stale')
DATA_KEYS=('consensus_insufficient','forward_consensus_insufficient','market_data_missing','normalization_required','current_price_missing')

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def classify(row):
    text=' '.join(str(row.get(k) or '') for k in ('execution_state','reason','valuation_model'))
    if any(k in text for k in STRUCTURAL_KEYS): return 'structural'
    if any(k in text for k in DATA_KEYS): return 'data'
    return 'other'

def main():
    common=load(COMMON); fund=load(FUND); cycle=load(CYCLE); rows={str(r.get('code')).zfill(6):r for r in fund.get('companies',[])}; rows.update({str(r.get('code')).zfill(6):r for r in cycle.get('companies',[])})
    groups=defaultdict(list); gate=common.get('future_earnings_gate',{})
    for code in common.get('common_pool_codes',[]):
        code=str(code).zfill(6)
        for tag in (gate.get(code) or {}).get('t2_tags') or []: groups[tag].append(code)
    details={}; structural_blind=[]; data_blind=[]
    for tag,codes in sorted(groups.items()):
        valid=[]; unavailable=[]; reasons=Counter(); structural=[]; data=[]
        for code in sorted(set(codes)):
            r=rows.get(code)
            if not r:
                unavailable.append(code); reasons['missing_valuation_row']+=1; structural.append(code); continue
            if r.get('valuation_status')=='valid': valid.append(code); continue
            unavailable.append(code); bucket=classify(r); reasons[bucket]+=1
            (structural if bucket=='structural' else data if bucket=='data' else unavailable).append(code) if False else None
            if bucket=='structural': structural.append(code)
            elif bucket=='data': data.append(code)
        total=len(set(codes)); ratio=len(valid)/total if total else 1.0
        if total and not valid and structural: structural_blind.append(tag)
        if total and not valid and not structural: data_blind.append(tag)
        details[tag]={'candidate_count':total,'valid_valuation_count':len(valid),'valid_ratio':round(ratio,4),'valid_codes':valid,'unavailable_codes':unavailable,'structural_unavailable_codes':structural,'data_unavailable_codes':data,'unavailable_reason_buckets':dict(reasons)}
    all_common=[str(x).zfill(6) for x in common.get('common_pool_codes',[])]; valid_all=sum(1 for c in all_common if rows.get(c,{}).get('valuation_status')=='valid'); overall_ratio=valid_all/len(all_common) if all_common else 1.0
    warnings=[]
    if overall_ratio<0.70: warnings.append(f'overall_formal_valuation_coverage_low:{overall_ratio:.1%}')
    for tag,d in details.items():
        if d['candidate_count']>=2 and d['valid_ratio']<0.5 and tag not in structural_blind: warnings.append(f't2_data_coverage_low:{tag}:{d["valid_ratio"]:.1%}')
    status='PASS' if not structural_blind else 'FAIL'
    payload={'schema_version':1,'generated_at':datetime.now(TZ).isoformat(),'common_pool_count':len(all_common),'valid_valuation_count':valid_all,'overall_valid_ratio':round(overall_ratio,4),'t2_chain_count':len(details),'t2_chains':details,'structural_blind_spot_tags':structural_blind,'data_coverage_blind_spot_tags':data_blind,'coverage_warnings':warnings,'hard_gate':{'rule':'Any active T2 chain present in the common pool must not have zero valid valuations because of a structural model/anchor/regime defect. Analyst-consensus scarcity is reported separately and must never be silently interpreted as no opportunity.','status':status}}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'status':status,'overall_valid_ratio':round(overall_ratio,4),'structural_blind_spots':structural_blind,'warnings':warnings[:10]},ensure_ascii=False)); return 0 if status=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
