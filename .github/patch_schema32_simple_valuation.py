from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
mp=ROOT/'config/research_pipeline_manifest.json'
rp=ROOT/'config/research_runtime_policy.json'
m=json.loads(mp.read_text(encoding='utf-8'))
r=json.loads(rp.read_text(encoding='utf-8'))

m['schema_version']=32
v=m['valuation_resolution_contract']
v['valuation_engine_version']=3
v['default_path']='relative_earnings_valuation'
v['default_path_principle']='normal profitable companies use PE/dynamic PE + PB/ROE + level3 peers + earnings growth, with 180d market sanity; complex absolute valuation is exception-only'
v['complex_model_is_exception_not_default']=True
v['default_path_required_inputs']=['core_forward_eps','current_pe_or_ttm_pe','dynamic_pe_if_available','pb','roe_if_available','core_profit_growth','level3_peer_pe_median','level3_peer_pb_median','price_180d_low','price_180d_median','price_180d_high','price_180d_percentile']
v['default_path_required_outputs']=['fair_pe_low','fair_pe_mid','fair_pe_high','pe_basis','pb_cross_check','peer_valuation_check','market_180d_sanity_check','base_fair_value','reasonable_price_range','margin_of_safety_pct','safe_price_ceiling']
v['fair_pe_construction_contract']={
 'primary_anchor':'level3_peer_pe_median_and_company_dynamic_pe',
 'growth_adjustment_required':True,
 'profit_quality_adjustment_required':True,
 'pb_roe_cross_check_required':True,
 'peer_comparison_required':True,
 'company_current_pe_is_reference_not_automatic_fair_pe':True,
 'market_180d_is_sanity_check_not_sole_intrinsic_value_input':True,
 'fair_pe_must_be_explained_not_fixed_by_level1_industry':True
}
v['forward_eps_contract']={
 'use_deducted_or_core_earnings':True,
 'annualize_only_when_seasonality_is_reasonably_stable':True,
 'otherwise_use_internal_forward_range_from_recent_quarters_and_guidance':True,
 'material_share_change_requires_current_or_forward_diluted_share_count':True
}
v['pb_cross_check_contract']={
 'pb_is_secondary_for_normal_companies':True,
 'compare_with_level3_peers':True,
 'roe_or_asset_quality_should_explain_material_pb_premium_or_discount':True,
 'material_pe_pb_conflict_triggers_exception_review':True
}
v['market_sanity_contract']={
 'history_window_trading_days':180,
 'required_statistics':['low','median','high','percentile'],
 'if_model_value_is_far_outside_180d_range_and_fundamentals_have_not_structurally_changed_trigger_audit':True,
 'historical_price_cannot_override_clear_earnings_or_business_structural_change':True,
 'market_price_is_sanity_check_not_truth':True
}
v['exception_path_triggers']=['negative_or_unusable_pe','major_restructuring','nonrecurring_earnings_dominant','financial_balance_sheet_business','extreme_cycle_peak_or_trough','pe_pb_peer_conflict','model_vs_180d_market_conflict','business_model_break']
v['exception_path_models']=['pb_roe','residual_income','ev_ebitda','nav_dcf','fcf_dcf','case_specific']
v['resource_asset_fixed_pe_only_valuation_forbidden']=False
v['spread_cyclical_requires_spread_or_margin_normalization']=False
v['base_case_required']=False
v['downside_case_required']=False
v['valuation_archetype_required']=False
v['normal_company_complex_archetype_forbidden_as_default']=True
v['single_mos_application_required']=True
v['fixed_discount_from_reasonable_lower_bound_forbidden']=True
v['safe_price_ceiling_formula']='base_fair_value * (1 - margin_of_safety_pct)'
v['mos_reference_ranges']={'high_confidence':[0.10,0.15],'medium_confidence':[0.15,0.20],'low_confidence':[0.20,0.25]}
v['extreme_valuation_deviation_audit']['default_response']='recheck_forward_eps_peer_pe_pb_and_180d_sanity_before_any_complex_model'
v['extreme_valuation_deviation_audit']['complex_secondary_method_only_if_simple_rechecks_do_not_resolve']=True

# Replace required fields: keep old compatibility fields but add simple-path fields.
for f in ['fair_pe_low','fair_pe_mid','fair_pe_high','pe_basis','current_pe','dynamic_pe','pb','peer_pe_median','peer_pb_median','core_profit_growth','pb_cross_check','peer_valuation_check','market_180d_sanity_check','valuation_path']:
    if f not in v['required_bridge_fields']: v['required_bridge_fields'].append(f)

# Buy point / near miss simplification.
b=m['buy_point_contract']
b['value_eligible_requires_current_price_at_or_below_safe_price_ceiling']=True
near=b['near_miss_ranking_contract']
near['ranking_version']=3
near['primary_definition']='distance to executable buy point using only value gap and structure gap'
near['required_metrics']=['missing_hard_conditions','value_gap_pct','structure_gap_pct','action_distance_pct','distance_band','current_missing','next_trigger']
near['action_distance_formula']='max(value_gap_pct, structure_gap_pct) when both measurable; if structure unavailable, rank after measurable names within same missing_hard_conditions'
near['sort_order']=['missing_hard_conditions asc','distance_band asc','action_distance_pct asc','fundamental_score desc','stock_code asc']
near['near_threshold_pct']=5.0
near['watch_threshold_pct']=15.0
near['far_names_must_be_labeled_relative_closest_not_near']=True
near['avoid_excluded_from_primary_near_miss_ranking']=True

# Completion gate simplify.
g=m['completion_gate_contract']
for k in ['all_non_review_valuations_have_archetype','all_non_review_valuations_have_base_and_downside_cases','resource_and_spread_cyclical_valuations_use_archetype_specific_models','extreme_deviation_secondary_models_pass_independent_driver_test']:
    if k in g: g[k]=False
g['all_normal_non_review_valuations_have_simple_relative_inputs']=True
g['all_normal_non_review_valuations_have_peer_and_pb_cross_checks']=True
g['all_normal_non_review_valuations_have_180d_market_sanity']=True
g['all_non_review_valuations_have_base_fair_value_and_safe_price_ceiling']=True
g['exception_companies_have_explicit_exception_trigger_and_model']=True
g['near_miss_action_distance_complete_when_eligible_universe_nonempty']=True

# runtime
r['schema_version']=12
s=r['stage_execution_policy']
for k in ['valuation_archetype_required_before_model_execution','resource_asset_fixed_pe_only_valuation_forbidden','spread_cyclical_fixed_pe_only_valuation_forbidden','base_and_downside_scenarios_required_for_non_review_valuation','extreme_deviation_secondary_method_must_use_independent_value_driver_family','same_eps_different_pe_is_not_independent_secondary_method','required_archetype_input_completeness_must_be_audited','generic_pe_fallback_when_archetype_inputs_missing_forbidden','primary_secondary_model_family_independence_must_be_audited']:
    if k in s: s[k]=False
s.update({
 'normal_profitable_company_uses_simple_relative_valuation_by_default':True,
 'default_valuation_requires_pe_dynamic_pe_pb_core_growth_level3_peers':True,
 'default_valuation_requires_180d_market_sanity':True,
 'complex_absolute_valuation_is_exception_only':True,
 'exception_trigger_required_before_complex_model':True,
 'safe_price_ceiling_required_for_value_eligibility':True,
 'single_margin_of_safety_application_required':True,
 'near_miss_uses_value_gap_and_structure_gap':True,
 'near_miss_missing_hard_conditions_must_be_retained_as_step_count':True
})
r['write_policy']['new_state_must_include_valuation_engine_v3_fields']=True

mp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
rp.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')

# Valuation skill replace entirely.
val=ROOT/'skills/a-share-low-risk/valuation/SKILL.md'
val.write_text('''# 估值 Skill — Valuation Engine V3（交易筛选估值）\n\n## 目的\n本任务不是给企业做投行级绝对估值，而是回答：**当前价格相对公司的核心盈利能力、三级同行和自身近180日市场定价，贵不贵；合理区间大概在哪；有没有足够安全边际。**\n\n核心原则：**默认简单，异常升级。** 正常盈利公司禁止默认使用NAV/DCF等重模型。\n\n## 1. Normal Valuation Path（默认路径）\n适用于扣非/核心盈利为正、主营口径可比、没有重大重组/一次性污染、PE仍有经济意义的绝大多数公司。\n\n固定顺序：\n`核心盈利 → Forward核心EPS → 当前PE/TTM PE/动态PE → 同三级行业PE横比 → 盈利增速调整 → PB/ROE交叉验证 → 180日市场sanity → 合理PE区间 → 合理价格区 → 一次MOS → Safe Price Ceiling`\n\n### 1.1 Forward核心EPS\n优先使用扣非/核心盈利。半年报只有在季节性较稳定时才可合理年化；否则结合Q1/Q2边际、公司指引、订单/销量等构造Forward区间。股本发生重大变化时必须用当前/Forward稀释股本重算EPS。\n\n### 1.2 PE主锚\n必须获取并记录：\n- 当前/TTM PE；\n- 动态PE（可得时）；\n- 同三级行业可比公司PE中位数与分位；\n- 公司核心盈利增速。\n\n合理PE不是固定行业表，而是从“三级同行中位数 + 公司自身动态PE + 盈利增长/质量”构造并解释。\n\n基本原则：\n- 盈利增速、ROE/现金质量明显优于同行，可允许合理溢价；\n- 盈利增速低于同行或现金质量差，应折价；\n- 当前PE只是参考，不能直接把当前估值复制成合理估值。\n\n### 1.3 PB/ROE交叉验证\nPB不是正常公司的主模型，但必须作为第二视角。比较公司PB与三级同行PB中位数，并结合ROE/资产质量解释溢价或折价。\n\n典型异常：PE看起来很便宜，但PB很高且ROE不支持；或PE很贵，但PB/ROE与高质量资产明显支持。出现明显冲突时进入Exception Path，而不是机械平均。\n\n### 1.4 180日市场sanity check\n必须读取最近180个交易日：价格low/median/high、当前价格percentile，最好同时使用可得的历史估值分位。\n\n用途是检查模型是否明显脱离市场现实：\n- 如果模型合理价长期远低于过去180日主要交易区，而盈利又在改善且没有结构性恶化，优先怀疑模型；\n- 如果基本面发生结构性变化，历史价格只能参考，不能强行把合理价拉回历史区间。\n\n180日市场数据是sanity，不是“市场永远正确”。\n\n### 1.5 合理价与安全价\n先形成 `fair_pe_low/mid/high`，再用Forward核心EPS得到 `reasonable_price_range` 与 `base_fair_value`。\n\nMOS只应用一次：\n`safe_price_ceiling = base_fair_value × (1 - MOS)`\n\n参考：高置信10%–15%，中等15%–20%，低置信20%–25%。不得再对合理价下沿重复打折。\n\n## 2. Exception Path（仅异常公司）\n只有以下情况才升级复杂模型：\n- PE为负或没有经济意义；\n- 重大重组/主营切换；\n- 一次性收益显著污染；\n- 银行/保险等资产负债表业务；\n- 极端周期顶部/底部导致TTM PE失真；\n- PE与PB/同行出现无法解释的重大冲突；\n- 模型与180日市场定价严重冲突且简单复核不能解释；\n- 商业模式发生断裂。\n\n异常模型可使用 PB-ROE、Residual Income、EV/EBITDA、NAV/DCF、FCF/DCF 或 case-specific。必须记录 `exception_trigger`，没有触发不得升级复杂模型。\n\n## 3. 极端偏离审计\n若合理价与当前价偏离达到Manifest阈值，先做简单复核：\n1. Forward核心EPS是否错；\n2. 股本/重组/一次性收益是否错；\n3. 三级同行PE/PB是否取错；\n4. 盈利增速与现金质量调整是否合理；\n5. 180日市场sanity是否出现强冲突。\n\n只有上述仍无法解释，才升级复杂模型。禁止为了证明极端估值而直接堆NAV/DCF。\n\n## 4. 必须输出\n正常公司至少输出：\n`current_price / price_date / current_pe / dynamic_pe / pb / core_profit_growth / peer_pe_median / peer_pb_median / fair_pe_low-mid-high / pe_basis / pb_cross_check / peer_valuation_check / market_180d_sanity_check / reasonable_price_range / base_fair_value / margin_of_safety_pct / safe_price_ceiling / valuation_position / falsifiers / valuation_path=normal_relative`。\n\n异常公司必须额外输出：\n`valuation_path=exception / exception_trigger / exception_method / exception_evidence`。\n\n## 5. Completion纪律\n- valuation_set逐只执行；\n- 正常公司必须完成PE主锚、PB/ROE交叉验证、三级同行比较和180日sanity；\n- 异常公司必须有明确异常触发，不得默认走复杂模型；\n- Safe Price Ceiling只应用一次MOS；\n- 估值完成不代表可买，最终仍与独立价格结构结合。\n''',encoding='utf-8')

# Orchestrator valuation + near miss sections.
op=ROOT/'skills/a-share-low-risk/orchestrator/SKILL.md'
t=op.read_text(encoding='utf-8')
start=t.index('## 8. VALUATION')
end=t.index('## 9. PRICE STRUCTURE')
t=t[:start]+'''## 8. VALUATION：默认简单，异常升级\nvaluation_set每家公司执行 Valuation Engine V3。\n\n正常盈利公司默认使用：`Forward扣非EPS × 合理PE`，合理PE由当前/动态PE、同三级行业PE中位数、核心盈利增速共同决定，并用PB/ROE与180日市场位置交叉验证。禁止正常公司默认进入NAV/DCF重模型。\n\n只有PE失真、重大重组、一次性污染、金融资产负债表业务、极端周期、PE/PB/同行严重冲突、模型与180日市场严重冲突等异常才升级PB-ROE/EV-EBITDA/NAV/DCF等Exception Path。\n\n安全价只做一次MOS：`safe_price_ceiling = base_fair_value × (1-MOS)`。\n\n'''+t[end:]
nm=t.index('## 接近买点榜（Near-miss Ranking')
t=t[:nm]+'''## 接近买点榜（Near-miss Ranking V3）\n\n正式买点仍只允许 `buyable_now`。即使当前买点为0，也必须输出Top10。\n\n排序只回答“离可执行买点还有多远”：\n- `missing_hard_conditions`：价值不合格 +1；结构不合格 +1；avoid排除；\n- `value_gap_pct`：当前价降到safe_price_ceiling所需幅度，已满足为0；\n- `structure_gap_pct`：当前价到有效structure_entry_range最近边界距离，位于区间内为0；无有效结构区记不可测；\n- `action_distance_pct = max(value_gap_pct, structure_gap_pct)`（两者均可测时）。\n\n标签：near≤5%，watch 5%–15%，far>15%。\n排序：`missing_hard_conditions → distance_band → action_distance_pct → 基本面得分 → 股票代码`。结构距离不可测者在同缺失条件内排在可测者之后。\n\nTop10每只必须写【还缺什么】和【下一触发条件】；第1名若仍>15%，明确写“相对最接近，但仍远离买点”。榜单只当期展示，不做候选池。\n'''
op.write_text(t,encoding='utf-8')

# Tests updates/additions.
for p in ROOT.glob('tests/*.py'):
    x=p.read_text(encoding='utf-8')
    x=x.replace('== 31','== 32').replace("== 11","== 12")
    if p.name=='test_valuation_engine_v2_contract.py':
        p.unlink(); continue
    p.write_text(x,encoding='utf-8')

(ROOT/'tests/test_valuation_engine_v3_contract.py').write_text('''import json\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parents[1]\ndef m(): return json.loads((ROOT/'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))\ndef r(): return json.loads((ROOT/'config/research_runtime_policy.json').read_text(encoding='utf-8'))\n\ndef test_schema32_uses_simple_default_valuation():\n    v=m()['valuation_resolution_contract']\n    assert m()['schema_version']==32\n    assert v['valuation_engine_version']==3\n    assert v['default_path']=='relative_earnings_valuation'\n    assert v['complex_model_is_exception_not_default'] is True\n    assert v['normal_company_complex_archetype_forbidden_as_default'] is True\n\ndef test_normal_path_has_pe_pb_peer_growth_and_180d_sanity():\n    v=m()['valuation_resolution_contract']\n    req=v['default_path_required_inputs']\n    for k in ['core_forward_eps','current_pe_or_ttm_pe','pb','core_profit_growth','level3_peer_pe_median','level3_peer_pb_median','price_180d_median','price_180d_percentile']:\n        assert k in req\n    assert v['fair_pe_construction_contract']['pb_roe_cross_check_required'] is True\n    assert v['market_sanity_contract']['history_window_trading_days']==180\n\ndef test_complex_model_needs_exception_trigger():\n    v=m()['valuation_resolution_contract']\n    assert 'major_restructuring' in v['exception_path_triggers']\n    assert 'negative_or_unusable_pe' in v['exception_path_triggers']\n    assert 'nav_dcf' in v['exception_path_models']\n    assert r()['stage_execution_policy']['exception_trigger_required_before_complex_model'] is True\n\ndef test_single_mos_and_safe_ceiling():\n    v=m()['valuation_resolution_contract']\n    assert v['single_mos_application_required'] is True\n    assert v['safe_price_ceiling_formula']=='base_fair_value * (1 - margin_of_safety_pct)'\n    assert v['fixed_discount_from_reasonable_lower_bound_forbidden'] is True\n\ndef test_near_miss_v3_is_simple_distance():\n    n=m()['buy_point_contract']['near_miss_ranking_contract']\n    assert n['ranking_version']==3\n    assert n['required_metrics']==['missing_hard_conditions','value_gap_pct','structure_gap_pct','action_distance_pct','distance_band','current_missing','next_trigger']\n    assert 'max(value_gap_pct, structure_gap_pct)' in n['action_distance_formula']\n''',encoding='utf-8')

# Old state must remain absent; never relabel.
sp=ROOT/'data/research/v2/research_state.json'
if sp.exists(): sp.unlink()
print('schema32 simple valuation contract prepared')
