import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
mp=ROOT/'config/research_pipeline_manifest.json'
rp=ROOT/'config/research_runtime_policy.json'
m=json.loads(mp.read_text(encoding='utf-8'))
r=json.loads(rp.read_text(encoding='utf-8'))

m['schema_version']=31
v=m['valuation_resolution_contract']
v.update({
 'valuation_engine_version':2,
 'valuation_archetype_required':True,
 'valuation_archetypes':['resource_asset','spread_cyclical','order_backlog','growth_compounder','stable_cashflow','financial','special_situation'],
 'sw_level1_alone_cannot_determine_valuation_archetype':True,
 'base_case_required':True,
 'downside_case_required':True,
 'base_fair_value_required':True,
 'safe_price_ceiling_required':True,
 'safe_price_ceiling_is_value_eligibility_boundary':True,
 'fixed_discount_from_reasonable_lower_bound_forbidden':True,
 'repeat_conservatism_across_earnings_multiple_and_mos_forbidden':True,
 'secondary_method_must_use_independent_value_driver_family':True,
 'same_earnings_basis_with_different_multiple_is_not_independent_method':True,
 'market_reality_audit_required_when_safe_ceiling_gap_is_extreme':True,
 'resource_asset_requires_asset_or_cashflow_model':True,
 'resource_asset_single_fixed_pe_forbidden':True,
 'spread_cyclical_requires_spread_or_margin_normalization':True,
 'financial_requires_pb_roe_or_residual_income':True,
 'normalization_must_reflect_structural_capacity_or_mix_change':True,
 'mos_reference_ranges':{'low':[0.10,0.15],'medium':[0.15,0.25],'high':[0.25,0.35]},
 'archetype_model_contract':{
   'resource_asset':{'required_inputs':['commodity_price_anchor','production_or_equity_volume','unit_cost','capex','net_debt','asset_life_or_reserve_quality'],'primary_methods':['nav_dcf','normalized_ev_ebitda','fcf_dividend_capacity'],'independent_secondary_families':['nav_dcf','normalized_ev_ebitda','pb_roe','fcf_dividend_capacity']},
   'spread_cyclical':{'required_inputs':['product_price','feedstock_cost','spread','utilization_or_volume','normalized_margin'],'primary_methods':['normalized_ev_ebitda','spread_scenario_dcf'],'independent_secondary_families':['normalized_core_pe','roic_sanity','spread_scenario_dcf']},
   'order_backlog':{'required_inputs':['order_backlog','delivery_schedule','pricing','margin','capacity'],'primary_methods':['forward_ev_ebit','forward_pe'],'independent_secondary_families':['normalized_cashflow','pb_roe']},
   'growth_compounder':{'required_inputs':['forward_revenue','forward_core_earnings','margin','roic_or_roe','cash_conversion'],'primary_methods':['justified_forward_pe','forward_ev_ebit'],'independent_secondary_families':['dcf','fcf_yield','peg_sanity']},
   'stable_cashflow':{'required_inputs':['normalized_cashflow','capex','growth','capital_structure'],'primary_methods':['dcf','dividend_capacity','ev_ebitda','justified_pe'],'independent_secondary_families':['dcf','dividend_capacity','ev_ebitda','justified_pe']},
   'financial':{'required_inputs':['book_value','sustainable_roe','asset_quality','capital_constraint'],'primary_methods':['pb_roe','residual_income'],'independent_secondary_families':['pb_roe','residual_income']},
   'special_situation':{'required_inputs':['post_transaction_business','comparable_earnings_basis'],'primary_methods':['case_specific'],'independent_secondary_families':['case_specific']}
 }
})
for f in ['valuation_archetype','archetype_basis','scenario_analysis','primary_model_output','base_fair_value','downside_value','margin_of_safety_pct','safe_price_ceiling','valuation_quality_flags']:
    if f not in v['required_bridge_fields']: v['required_bridge_fields'].append(f)
a=v['extreme_valuation_deviation_audit']
a['requires_independent_value_driver_family']=True
a['same_eps_different_pe_fails_independence_test']=True

b=m['buy_point_contract']
b['value_eligible_requires_current_price_at_or_below_safe_price_ceiling']=True
b['safe_price_ceiling_is_hard_value_boundary']=True
b['safe_price_range_lower_bound_is_not_hard_eligibility_floor']=True
b['buy_price_range_must_equal_structure_entry_range_capped_by_safe_price_ceiling']=True
b['buy_price_range_must_equal_intersection_of_safe_price_range_and_structure_entry_range']=False
near=b['near_miss_ranking_contract']
near.update({
 'ranking_version':2,
 'review_required_excluded_from_distance_ranking':True,
 'avoid_excluded_from_primary_near_miss_ranking':True,
 'action_distance_is_primary_metric':True,
 'action_distance_formula':'max(value_gap_pct, structure_gap_pct, ceiling_structure_gap_pct, current_to_actionable_range_pct)',
 'near_threshold_pct':5.0,
 'watch_threshold_pct':15.0,
 'distance_bands':{'near':'<=5%','watch':'>5% and <=15%','far':'>15%'},
 'far_names_must_be_labeled_relative_closest_not_near':True,
 'safe_structure_range_gap_pct_deprecated':True,
 'required_metrics':['near_miss_tier','distance_band','value_gap_pct','structure_gap_pct','ceiling_structure_gap_pct','current_to_actionable_range_pct','action_distance_pct','valuation_confidence_penalty','current_missing','next_trigger'],
 'sort_order':['near_miss_tier asc','action_distance_pct asc','valuation_confidence_penalty asc','fundamental_score desc','stock_code asc']
})

g=m['completion_gate_contract']
g.update({
 'all_non_review_valuations_have_archetype':True,
 'all_non_review_valuations_have_base_and_downside_cases':True,
 'all_non_review_valuations_have_base_fair_value_and_safe_price_ceiling':True,
 'resource_and_spread_cyclical_valuations_use_archetype_specific_models':True,
 'extreme_deviation_secondary_models_pass_independent_driver_test':True,
 'near_miss_action_distance_complete_when_eligible_universe_nonempty':True
})

# runtime
r['schema_version']=11
s=r['stage_execution_policy']
s.update({
 'valuation_archetype_required_before_model_execution':True,
 'sw_level1_only_valuation_model_selection_forbidden':True,
 'resource_asset_fixed_pe_only_valuation_forbidden':True,
 'spread_cyclical_fixed_pe_only_valuation_forbidden':True,
 'base_and_downside_scenarios_required_for_non_review_valuation':True,
 'safe_price_ceiling_required_for_value_eligibility':True,
 'fixed_discount_from_reasonable_lower_bound_forbidden':True,
 'extreme_deviation_secondary_method_must_use_independent_value_driver_family':True,
 'same_eps_different_pe_is_not_independent_secondary_method':True,
 'near_miss_action_distance_is_primary_sort_metric':True,
 'near_miss_far_names_must_be_labeled_far':True
})
r['write_policy']['new_state_must_include_valuation_engine_v2_fields']=True

mp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
rp.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')

# Orchestrator: replace valuation section + near-miss section.
op=ROOT/'skills/a-share-low-risk/orchestrator/SKILL.md'
t=op.read_text(encoding='utf-8')
start=t.index('## 8. VALUATION')
end=t.index('## 9. PRICE STRUCTURE')
new='''## 8. VALUATION：经济价值驱动优先\nvaluation_set每家公司执行 Valuation Engine V2。\n\n硬门：\n1. 先识别 `valuation_archetype`，申万一级行业不能单独决定模型；\n2. 非review公司必须有 `base_case + downside_case + base_fair_value + safe_price_ceiling`；\n3. resource_asset 禁止固定低PE单模型，必须使用NAV/DCF、正常化EV/EBITDA、FCF/股息能力等资产/现金流方法；\n4. spread_cyclical 必须显式研究产品-原料价差、开工与正常化利润率；\n5. financial 必须执行PB-ROE或Residual Income；\n6. 正常化必须反映已发生的产能、资源量、产品结构变化，不能机械回归旧年度利润；\n7. 极端偏离的第二模型必须更换价值驱动家族，同一EPS换另一个PE倍数不算独立模型；\n8. 安全价硬边界是 `safe_price_ceiling`，MOS只作用一次，禁止“压盈利+低倍数+再折合理价下沿”的重复保守化。\n\n'''
t=t[:start]+new+t[end:]
# update buy point wording
old='`buy_price_range = safe_price_range ∩ structure_entry_range`'
t=t.replace(old,'`buy_price_range = structure_entry_range ∩ (-∞, safe_price_ceiling]`')
t=t.replace('只有：\n`value_eligible=true + timing_eligible=true + buy_price_range非空`','只有：\n`current_price <= safe_price_ceiling + timing_eligible=true + buy_price_range非空`')
# replace near miss section to EOF
nm=t.index('## 接近买点榜（Near-miss Ranking）')
newnm='''## 接近买点榜（Near-miss Ranking V2）\n\n【当前低风险买点】仍只允许 `buyable_now`，绝不为了凑榜降低价值或结构门槛。\n\nNear-miss 的含义改为：**距离成为可执行买点还需要多大实际变化**，而不是旧版按区间字段字典序排序。\n\n对所有完整非review且非avoid公司计算：\n- `value_gap_pct`：当前价下降到 `safe_price_ceiling` 所需幅度；已价值合格为0；\n- `structure_gap_pct`：当前价到有效结构入场区最近边界的距离；\n- `ceiling_structure_gap_pct`：结构入场区整体高于安全上限时，两者最近边界距离；若结构区已有部分位于安全上限以内则为0；\n- `current_to_actionable_range_pct`：有效可执行区存在时，当前价到该区最近边界距离；\n- `action_distance_pct = max(上述可测硬距离)`，表示当前最大的阻塞距离；\n- `valuation_confidence_penalty`：估值不确定性越高，排序越靠后。\n\n距离标签：\n- `near`：<=5%；\n- `watch`：>5%且<=15%；\n- `far`：>15%。\n\n排序：`near_miss_tier → action_distance_pct → valuation_confidence_penalty → 基本面得分 → 股票代码`。\n\nTop10仍必须输出；如果最接近的公司也超过15%，必须明确写“相对最接近，但仍远离买点”，不能把35%、60%的价值缺口包装成“接近买点”。\n\n该榜只做当期展示，不得持久化为候选池或下一轮发现种子。\n'''
t=t[:nm]+newnm
op.write_text(t,encoding='utf-8')

# Tests: bump schema references and old buy-point assertion.
for p in [ROOT/'tests/test_research_contract.py',ROOT/'tests/test_research_state_coverage_ledger.py']:
    x=p.read_text(encoding='utf-8').replace('schema30','schema31').replace('== 30','== 31')
    x=x.replace("assert b['buy_price_range_must_equal_intersection_of_safe_price_range_and_structure_entry_range'] is True", "assert b['buy_price_range_must_equal_intersection_of_safe_price_range_and_structure_entry_range'] is False\n    assert b['buy_price_range_must_equal_structure_entry_range_capped_by_safe_price_ceiling'] is True")
    p.write_text(x,encoding='utf-8')
prt=ROOT/'tests/test_research_runtime_policy.py'
x=prt.read_text(encoding='utf-8').replace("assert p['schema_version'] == 10","assert p['schema_version'] == 11")
prt.write_text(x,encoding='utf-8')

newtest=ROOT/'tests/test_valuation_engine_v2_contract.py'
newtest.write_text('''import json\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parents[1]\ndef m(): return json.loads((ROOT/'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))\ndef r(): return json.loads((ROOT/'config/research_runtime_policy.json').read_text(encoding='utf-8'))\n\ndef test_schema31_valuation_engine_v2():\n    v=m()['valuation_resolution_contract']\n    assert m()['schema_version']==31\n    assert v['valuation_engine_version']==2\n    assert v['valuation_archetype_required'] is True\n    assert v['sw_level1_alone_cannot_determine_valuation_archetype'] is True\n    assert v['base_case_required'] and v['downside_case_required']\n    assert v['base_fair_value_required'] and v['safe_price_ceiling_required']\n    assert v['fixed_discount_from_reasonable_lower_bound_forbidden'] is True\n    assert v['repeat_conservatism_across_earnings_multiple_and_mos_forbidden'] is True\n\ndef test_resource_and_cycle_models_are_not_fixed_pe_shortcuts():\n    v=m()['valuation_resolution_contract']\n    assert v['resource_asset_single_fixed_pe_forbidden'] is True\n    assert v['resource_asset_requires_asset_or_cashflow_model'] is True\n    assert v['spread_cyclical_requires_spread_or_margin_normalization'] is True\n    assert 'nav_dcf' in v['archetype_model_contract']['resource_asset']['primary_methods']\n    assert 'normalized_ev_ebitda' in v['archetype_model_contract']['spread_cyclical']['primary_methods']\n\ndef test_secondary_model_is_genuinely_independent():\n    v=m()['valuation_resolution_contract']\n    assert v['secondary_method_must_use_independent_value_driver_family'] is True\n    assert v['same_earnings_basis_with_different_multiple_is_not_independent_method'] is True\n    assert v['extreme_valuation_deviation_audit']['same_eps_different_pe_fails_independence_test'] is True\n\ndef test_safe_ceiling_replaces_double_discount_logic():\n    b=m()['buy_point_contract']\n    assert b['safe_price_ceiling_is_hard_value_boundary'] is True\n    assert b['safe_price_range_lower_bound_is_not_hard_eligibility_floor'] is True\n    assert b['buy_price_range_must_equal_structure_entry_range_capped_by_safe_price_ceiling'] is True\n\ndef test_near_miss_uses_action_distance_and_labels_far_names():\n    n=m()['buy_point_contract']['near_miss_ranking_contract']\n    assert n['ranking_version']==2\n    assert n['action_distance_is_primary_metric'] is True\n    assert n['near_threshold_pct']==5.0\n    assert n['watch_threshold_pct']==15.0\n    assert n['far_names_must_be_labeled_relative_closest_not_near'] is True\n    assert n['avoid_excluded_from_primary_near_miss_ranking'] is True\n    assert r()['stage_execution_policy']['same_eps_different_pe_is_not_independent_secondary_method'] is True\n''',encoding='utf-8')

# Current schema30 valuations are invalid under V2; do not relabel them.
sp=ROOT/'data/research/v2/research_state.json'
if sp.exists(): sp.unlink()

readme=ROOT/'data/research/v2/README.md'
rt=readme.read_text(encoding='utf-8')
rt += '\n\nValuation Engine V2 (schema31): valuation archetype is economic-driver based; safe_price_ceiling replaces repeated discounts from a conservative lower bound; same-EPS/different-PE does not count as an independent secondary model.\n'
readme.write_text(rt,encoding='utf-8')
print('schema31 valuation v2 contract prepared')
