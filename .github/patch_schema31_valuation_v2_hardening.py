import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
mp=ROOT/'config/research_pipeline_manifest.json'; rp=ROOT/'config/research_runtime_policy.json'
m=json.loads(mp.read_text(encoding='utf-8')); r=json.loads(rp.read_text(encoding='utf-8'))
assert m['schema_version']==31
v=m['valuation_resolution_contract']; b=m['buy_point_contract']; n=b['near_miss_ranking_contract']
# Eliminate dual value-eligibility semantics.
b['value_eligible_requires_current_price_at_or_below_safe_upper_bound']=False
b['legacy_safe_upper_bound_value_eligibility_deprecated']=True
b['value_eligible_requires_current_price_at_or_below_safe_price_ceiling']=True
# Make model completeness auditable.
for f in ['valuation_input_completeness','primary_model_family','market_reality_audit']:
    if f not in v['required_bridge_fields']: v['required_bridge_fields'].append(f)
v.update({
 'required_archetype_inputs_must_be_present_or_explicitly_supplemented':True,
 'missing_archetype_critical_input_cannot_be_replaced_by_generic_pe':True,
 'missing_archetype_critical_input_after_public_evidence_search_requires_review_or_explicit_low_confidence_blocker':True,
 'primary_model_family_required':True,
 'secondary_model_family_required_when_secondary_model_runs':True,
 'primary_and_secondary_model_family_must_differ_when_independence_required':True,
 'market_reality_audit_trigger_multiple':1.5,
 'market_reality_audit_must_report_market_implied_assumption_gap_not_reanchor_value':True,
 'valuation_quality_flags_required':['archetype_inputs_complete','core_earnings_clean','no_repeated_conservatism','model_independence_passed_or_not_required','market_reality_audit_passed_or_not_required']
})
# Near miss: retain hard-condition step count; use action distance inside the step tier.
metrics=n['required_metrics']
if 'missing_hard_conditions' not in metrics: metrics.insert(2,'missing_hard_conditions')
n.update({
 'missing_hard_conditions_is_step_count_not_primary_numeric_distance':True,
 'near_miss_tier_definition':{
   'one_step':'exactly one hard condition remains',
   'two_step':'exactly two hard conditions remain',
   'multi_step':'three or more hard conditions remain',
   'buyable_now':'separate current-opportunity list, not near-miss'
 },
 'qualitative_structure_wait_allowed_when_value_eligible':True,
 'unmeasurable_structure_distance_must_not_be_fabricated':True,
 'sort_order':['near_miss_tier by missing_hard_conditions asc','measurable action_distance_pct asc','valuation_confidence_penalty asc','fundamental_score desc','stock_code asc']
})
# Runtime matching hard gates.
s=r['stage_execution_policy']
s.update({
 'legacy_safe_upper_bound_value_eligibility_forbidden':True,
 'required_archetype_input_completeness_must_be_audited':True,
 'generic_pe_fallback_when_archetype_inputs_missing_forbidden':True,
 'primary_secondary_model_family_independence_must_be_audited':True,
 'near_miss_missing_hard_conditions_must_be_retained_as_step_count':True,
 'near_miss_unmeasurable_structure_distance_must_not_be_fabricated':True
})
mp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8'); rp.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
# Tests
p=ROOT/'tests/test_valuation_engine_v2_contract.py'; x=p.read_text(encoding='utf-8')
x += '''\n\ndef test_v2_has_one_value_boundary_and_input_completeness_gate():\n    v=m()['valuation_resolution_contract']; b=m()['buy_point_contract']\n    assert b['value_eligible_requires_current_price_at_or_below_safe_upper_bound'] is False\n    assert b['value_eligible_requires_current_price_at_or_below_safe_price_ceiling'] is True\n    assert v['required_archetype_inputs_must_be_present_or_explicitly_supplemented'] is True\n    assert v['missing_archetype_critical_input_cannot_be_replaced_by_generic_pe'] is True\n    assert v['primary_and_secondary_model_family_must_differ_when_independence_required'] is True\n\ndef test_near_miss_combines_step_count_and_action_distance():\n    n=m()['buy_point_contract']['near_miss_ranking_contract']\n    assert 'missing_hard_conditions' in n['required_metrics']\n    assert n['missing_hard_conditions_is_step_count_not_primary_numeric_distance'] is True\n    assert n['qualitative_structure_wait_allowed_when_value_eligible'] is True\n    assert n['unmeasurable_structure_distance_must_not_be_fabricated'] is True\n'''
p.write_text(x,encoding='utf-8')
print('valuation v2 hardening prepared')
