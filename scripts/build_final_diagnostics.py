from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LEFT=ROOT/'data/research/pipeline/left_valuation_scan.json'
RIGHT=ROOT/'data/research/pipeline/right_structure_scan.json'
FINAL=ROOT/'data/research/pipeline/final_selection.json'
OUT=ROOT/'data/research/pipeline/final_diagnostics.json'

def load(p): return json.loads(p.read_text(encoding='utf-8'))

def main():
    l=load(LEFT); r=load(RIGHT); f=load(FINAL)
    lb={x['code']:x for x in l.get('companies',[])}
    rb=r.get('companies',{})
    left_rows=[]
    for c in f.get('left_set_codes',[]):
        a=lb[c]; b=rb[c]
        left_rows.append({
            'code':c,'name':a.get('name') or b.get('name'),'current_price':b.get('current_price'),
            'value_anchor_range':a.get('value_anchor_range'),'safe_buy_range':a.get('safe_buy_range'),'reasonable_buy_range':a.get('reasonable_buy_range'),
            'left_conclusion':a.get('left_conclusion'),'structure_state':b.get('structure_state'),
            'first_effective_resistance':b.get('first_effective_resistance'),'upside_pct':b.get('upside_to_first_resistance_pct'),
            'support_invalidation':b.get('support_invalidation'),'risk_reward':b.get('risk_reward'),'right_conclusion':b.get('conclusion'),
        })
    right_rows=[]
    for c in f.get('right_set_codes',[]):
        a=lb[c]; b=rb[c]
        right_rows.append({
            'code':c,'name':a.get('name') or b.get('name'),'current_price':b.get('current_price'),
            'value_anchor_range':a.get('value_anchor_range'),'safe_buy_range':a.get('safe_buy_range'),'reasonable_buy_range':a.get('reasonable_buy_range'),
            'valuation_status':a.get('valuation_status'),'valuation_model':a.get('valuation_model'),'left_conclusion':a.get('left_conclusion'),'left_reason':a.get('reason'),
            'structure_state':b.get('structure_state'),'first_effective_resistance':b.get('first_effective_resistance'),
            'upside_pct':b.get('upside_to_first_resistance_pct'),'support_invalidation':b.get('support_invalidation'),
            'risk_reward':b.get('risk_reward'),'right_conclusion':b.get('conclusion'),
        })
    out={'left_only':left_rows,'right_only':right_rows}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__': main()
