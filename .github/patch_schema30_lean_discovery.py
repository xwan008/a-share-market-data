from pathlib import Path
import json

ROOT=Path('.')

# Manifest -> schema30 lean prompt-first discovery.
mp=ROOT/'config/research_pipeline_manifest.json'
m=json.loads(mp.read_text(encoding='utf-8'))
m['schema_version']=30
m['stage_order']=[
    'data_health','taxonomy_coverage','market_prosperity_search',
    'level3_profitability_verification','profit_chain_decomposition',
    'chain_company_light_screen','chain_company_comparison_and_dedup',
    'valuation','price_structure','buy_point_synthesis','completion_gate'
]

c=m['scan_cadence_contract']
c['full_scan_unit']='prompt_full_market_prosperity_search'
c['bootstrap_rule']='没有当前schema有效基线时，先通过Prompt基于当前公开证据做一次全市场景气搜索；将所有识别出的景气方向映射到相关申万三级行业并完成盈利验证，再进入公司层。'
c['friday_full_scan_rule']='每周五18:00重新从当前公开证据做Prompt全市场景气搜索，不从上周方向名单起步；对本周识别出的所有景气方向映射到相关三级行业并重验盈利状态。'
c['successful_bootstrap_next_full_scan']='bootstrap可立即生成有效基线；最近一个Friday 18:00仍按正式锚点重新做全市场景气搜索。'
c['weekly_full_prompt_search_required']=True
c['weekly_full_does_not_require_level1_level2_status_matrix']=True
c['persistent_level1_level2_prosperity_labels_forbidden']=True
c['full_346_level3_profitability_review_required']=False
c['selected_prosperity_directions_expand_all_relevant_level3']=True
c['selected_prosperity_directions_may_not_be_top_n_capped']=True
c['level3_verification_scope']='Prompt全市场景气搜索识别出的全部景气方向，经taxonomy映射后覆盖的相关三级行业；未映射到景气方向的三级节点只做taxonomy routing。'
c['daily_incremental_discovery_scope']='基于最近有效周度景气方向/三级盈利基线，Prompt搜索过去约24小时新增产业证据；只对新增、移除或实质变化的景气方向及其三级行业更新。'
for k in ['weekly_full_market_discovery_expected_counts','weekly_full_market_discovery_reviews_all_level1_level2']:
    c.pop(k,None)

m.pop('market_prosperity_discovery_contract',None)
m['market_prosperity_search_contract']={
    'purpose':'用Prompt和当前公开证据广泛、轻量地回答“最近哪些A股对应产业正在出现真实经营景气改善”，只输出有研究价值的景气方向；不维护31一级+134二级逐项状态矩阵。',
    'method':'prompt_full_market_search',
    'full_market_search_required_each_weekly_full':True,
    'full_market_search_does_not_require_level1_level2_status_rows':True,
    'persistent_level1_level2_status_rows_forbidden':True,
    'taxonomy_is_routing_after_search_not_search_state_machine':True,
    'search_must_not_start_from_previous_focus_list':True,
    'search_must_not_start_from_previous_companies_or_opportunities':True,
    'search_coverage_discipline':['资源品/能源','基础化工/材料','制造/设备','科技/电子/通信/计算机','消费','医药','金融地产','公用事业/交通运输','农业及其他可能出现盈利拐点的产业'],
    'preferred_evidence':['行业利润/利润率','产品价格或价差','库存','开工率/产能利用率','订单/出货/销量/产量','进出口/供需','代表性公司经营数据','真实改变供需或成本的政策'],
    'market_price_or_sector_return_cannot_be_primary_evidence':True,
    'top_n_or_fixed_count_selection_forbidden':True,
    'required_direction_fields':['direction_id','direction_name','taxonomy_refs','recent_change_window','why_now','leading_variables','evidence_basis','falsifiers','selected_for_level3_verification'],
    'selection_rule':'凡当前证据足以支持真实经营景气改善或明确值得三级拆分验证的方向全部输出；不得因已发现若干方向而停止搜索。',
    'weekly_baseline_contents':['selected_prosperity_directions','verified_level3_profitability_states'],
    'daily_incremental_rule':'搜索自基线/上次运行以来新增公开证据；允许新增方向、移除已失效方向或更新既有方向，不要求重新给全市场一级/二级行业逐项打标签。'
}

v=m['level3_profitability_verification_contract']
v.pop('selected_level2_expands_all_child_level3',None)
v.pop('selected_level1_without_resolved_level2_expands_all_descendant_level3',None)
v['prosperity_direction_must_map_to_taxonomy_before_company_research']=True
v['every_mapped_relevant_level3_requires_real_evidence_review']=True
v['mapping_rule']='每个景气方向必须通过taxonomy_refs映射到相关一级/二级/三级节点；若映射到一级或二级，则展开其与该景气逻辑相关的全部三级子行业，禁止只挑最强几个。'
v['unselected_level3_not_required_for_weekly_profitability_review']=True
v['unselected_level3_must_record_routing_reason']='not_selected_by_prosperity_search'

cov=m['coverage_contract']
led=cov['ledger_contract']
led['required_node_fields']=['code','name','level','parent_code','accounted_for','routing_status','routing_reason']
led['allowed_routing_status']=['taxonomy_reference','selected_for_level3_verification','not_selected_by_prosperity_search','verified_level3']
for k in ['allowed_trend','allowed_strength','allowed_breadth','allowed_confidence','allowed_scan_depth','allowed_evidence_scope','deep_trigger_rule','daily_no_trigger_node_may_carry_forward_valid_baseline','selected_level3_each_node_requires_real_evidence_review','selected_level3_generic_unconfirmed_placeholder_forbidden']:
    led.pop(k,None)
led['accounted_for_definition']='Coverage只证明31/134/346 taxonomy节点可被路由；一级/二级不维护景气状态。三级真实盈利状态只存在于level3_profitability_verification中。'
led['taxonomy_coverage_and_profitability_verification_are_separate']=True
led['level1_level2_are_routing_only_not_prosperity_state']=True
led['unselected_level3_may_be_taxonomy_only']=True
led['instantiate_all_taxonomy_nodes_before_market_prosperity_search']=True
led.pop('instantiate_all_taxonomy_nodes_before_market_prosperity_discovery',None)
cov.pop('prosperity_and_level3_gate',None)
cov['prosperity_search_and_level3_gate']={
    'weekly_full_requires_prompt_full_market_search':True,
    'weekly_full_does_not_require_31_134_status_rows':True,
    'selected_direction_count_may_be_zero_but_must_not_be_top_n_capped':True,
    'every_selected_direction_must_have_taxonomy_mapping':True,
    'every_mapped_relevant_level3_must_be_evidence_reviewed':True,
    'unselected_level3_need_only_complete_taxonomy_routing':True,
    'daily_incremental_requires_valid_baseline_not_older_than_days':7
}

rs=m['research_state_contract']['required_top_level_sections']
rs=[('market_prosperity_search' if x=='market_prosperity_discovery' else x) for x in rs]
if 'level3_profitability_verification' not in rs:
    rs.insert(rs.index('profit_chains'),'level3_profitability_verification')
m['research_state_contract']['required_top_level_sections']=rs

g=m['completion_gate_contract']
for k in ['all_level1_level2_prosperity_discovery_complete','no_prosperity_discovery_top_n_truncation']:
    g.pop(k,None)
g['market_prosperity_prompt_search_complete']=True
g['no_prosperity_search_top_n_truncation']=True
g['all_selected_directions_have_taxonomy_mapping']=True
g['all_mapped_relevant_level3_profitability_verified']=True

po=m['public_output']
po['sections']=[('全市场景气搜索' if x in {'全市场景气发现','全市场盈利景气雷达'} else x) for x in po['sections']]
if '全市场景气搜索' not in po['sections']:
    po['sections'].insert(1,'全市场景气搜索')
po.pop('prosperity_discovery_must_show_all_selected_directions',None)
po.pop('level3_verification_must_be_grouped_under_selected_prosperity_directions',None)
po['prosperity_search_must_show_all_selected_directions']=True
po['level3_verification_must_be_grouped_under_prosperity_directions']=True
mp.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Runtime policy schema10.
rp=ROOT/'config/research_runtime_policy.json'
r=json.loads(rp.read_text(encoding='utf-8'))
r['schema_version']=10
sc=r['state_compatibility']
sc['valid_industry_baseline_conditions']=[
    'manifest schema matches current schema',
    'taxonomy coverage contains exact 31/134/346 routing nodes',
    'Prompt full-market prosperity search completed without Top-N truncation',
    'every selected prosperity direction has taxonomy mapping and all mapped relevant level3 profitability verification complete',
    'prosperity search and level3 gate passed',
    'weekly baseline age is within manifest freshness limit',
    'baseline data cutoff and latest completed trade date are explicit'
]
d=r['discovery_policy']
d.pop('current_full_market_level1_level2_discovery_cannot_be_replaced_by_previous_focus_list',None)
d['weekly_prompt_full_market_prosperity_search_cannot_be_replaced_by_previous_focus_list']=True
d['persistent_level1_level2_prosperity_status_forbidden']=True
d['prosperity_selection_top_n_forbidden']=True
d['selected_direction_level3_expansion_cap_forbidden']=True
s=r['stage_execution_policy']
for k in ['coverage_ledger_must_be_instantiated_before_market_prosperity_discovery','weekly_full_scan_must_review_all_level1_level2_for_prosperity','prosperity_discovery_must_precede_level3_profitability_verification','selected_level2_must_expand_all_child_level3','selected_unresolved_level1_must_expand_all_descendant_level3','daily_incremental_requires_all_level1_level2_trigger_checks']:
    s.pop(k,None)
s['coverage_ledger_must_be_instantiated_before_market_prosperity_search']=True
s['weekly_full_requires_prompt_full_market_prosperity_search']=True
s['weekly_full_must_not_build_level1_level2_status_matrix']=True
s['prosperity_search_must_precede_level3_profitability_verification']=True
s['prosperity_search_top_n_forbidden']=True
s['every_selected_direction_must_map_to_relevant_level3']=True
s['every_mapped_relevant_level3_must_be_profitability_verified']=True
s['unselected_level3_may_remain_taxonomy_only']=True
s['daily_incremental_uses_prompt_search_for_new_or_changed_prosperity_evidence']=True
wp=r['write_policy']
wp.pop('new_state_must_include_market_prosperity_discovery_and_level3_verification',None)
wp['new_state_must_include_market_prosperity_search_and_level3_verification']=True
rp.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Rewrite orchestrator with lean discovery, preserve company/valuation/buy-point rigor.
op=ROOT/'skills/a-share-low-risk/orchestrator/SKILL.md'
old=op.read_text(encoding='utf-8')
company_tail=old[old.index('## 5. 全链公司轻筛'):]
company_tail=company_tail.replace('## 5. 全链公司轻筛','## 5. 全链公司轻筛',1)
head='''# A股低风险研究 V2 编排 Skill\n\n## 目标\n执行唯一主链：\n`数据健康 → Prompt全市场景气搜索 → 景气方向taxonomy映射 → 相关三级行业盈利验证 → 盈利链递归拆解 → 链内全部公司轻筛 → survivor横向比较 → 跨链去重 → 逐公司完整估值 → 价格结构 → 买点交集 → 接近买点榜 → Completion Gate`\n\n核心原则：**发现阶段广而轻，验证阶段窄而深。** 景气发现是搜索问题，三级盈利验证才是结构化状态问题。\n\n跨期只允许保留“景气方向 + 已验证三级盈利状态”的市场基线。一级/二级行业只承担taxonomy路由，不维护逐项景气状态；上一期公司、估值、机会和接近买点榜不得成为下一轮发现种子。\n\n## 1. DATA HEALTH\n确认主板范围、最近完整交易日、最新行情、历史数据和全市场价格结构新鲜。机械数据陈旧时fail closed。\n\n## 2. 第一层：Prompt全市场景气搜索\nweekly_full直接基于当前公开证据做一次全市场搜索，回答：**最近1~3个月哪些A股对应产业的真实经营景气正在改善，或者出现足以值得三级盈利验证的明确拐点？**\n\n这是广而轻的Prompt研究，不建立31个一级+134个二级行业逐项状态表。搜索时必须主动覆盖资源/能源、化工/材料、制造/设备、科技、消费、医药、金融地产、公用事业/交通运输、农业等主要经济板块，不能只从熟悉方向、旧名单或当日热点出发，也不能发现几个方向后提前停止。\n\n优先证据：行业利润/利润率、产品价格或价差、库存、开工率/产能利用率、订单/出货/销量/产量、进出口/供需、代表性公司经营数据，以及真正改变供需或成本的政策。板块涨幅、ETF强弱和市场情绪只能辅助，不能成为景气第一证据。\n\n输出只保存真正被识别出的景气方向，每个方向记录：`direction_name / taxonomy_refs / recent_change_window / why_now / leading_variables / evidence_basis / falsifiers`。**禁止Top-N或固定数量截断。**\n\n## 3. 第二层：景气方向映射到三级行业\n景气方向只是研究入口，不直接筛股票。使用申万taxonomy把每个方向映射到相关一级/二级/三级节点。\n\n若方向映射到一级或二级行业，必须展开与该景气逻辑相关的全部三级子行业，不能只挑表现最强的几个；例如Prompt发现“煤炭景气改善”，要继续验证动力煤、焦煤等相关三级；发现“基础化工改善”，要向下定位哪些化工三级链真正受益。\n\n未被本次景气搜索覆盖的三级行业只保留taxonomy routing，不要求当期做完整盈利研究，这不属于遗漏。\n\n## 4. 第三层：三级盈利验证与盈利链拆解\n只对被景气方向映射出的相关三级行业逐一做真实盈利验证，形成结构化状态：`trend / strength / breadth / confidence / evidence_basis / leading_variables / profit_driver`。\n\n- `trend=improving`：必须继续拆出真实盈利链，确认Driver、领先变量、利润传导、Forward Bridge和失效条件；\n- `deteriorating`或明显`divergent`：可保留诊断，但不能直接进入公司机会筛选；\n- 只有`verified level3 improving + resolved profit chain + confirmed profit transmission`才允许进入公司层。\n\n周度基线只保存：**本周Prompt识别出的景气方向 + 这些方向下已验证的三级盈利状态**。\n\n日度增量不重做全市场状态矩阵，只用Prompt搜索过去约24小时新增证据：是否新增景气方向、已有方向是否失效/增强、已验证三级盈利状态是否需要改变。有触发才更新相关链；无实质变化就carry forward。\n\n'''
op.write_text(head+company_tail,encoding='utf-8')

# README.
readme=ROOT/'data/research/v2/README.md'
readme.write_text('''# Low-risk research runtime data\n\nThis directory contains only current-runtime artifacts:\n- `full_market_price_structure.json`: mechanical full-market timing snapshot.\n- `research_state.json`: the only persisted Prompt research result; it may be absent when no valid current-schema run exists.\n\nThe current baseline follows a lean prosperity-first design: use a broad Prompt-based full-market search to discover only the industries/themes with recent real-economy prosperity or profitability improvement, then map those directions through the SW taxonomy and perform evidence-based profitability verification only on the relevant level-3 industries. Level-1 and level-2 industries are routing taxonomy, not a persistent prosperity status matrix.\n\nWeekly baseline memory contains only selected prosperity directions plus verified level-3 profitability states. Daily runs search for incremental new evidence and update only affected directions/chains. Previous companies, valuations, opportunities and near-miss rankings may not seed a new company discovery run.\n\nPublic fundamental/industry evidence is researched at run time. No independent weekly pool, candidate cache, T2 cache or duplicated valuation output may be persisted. `research_state.manifest_schema` must equal the current Manifest schema.\n''',encoding='utf-8')

# Tests: replace the schema29 discovery-focused contract tests with lean schema30 assertions.
t=ROOT/'tests/test_research_contract.py'
text=t.read_text(encoding='utf-8')
start=text.index('def test_manifest_schema29_and_stage_order():')
end=text.index('\ndef test_profit_chain_research_admission_cannot_use_top_n():')
new='''def test_manifest_schema30_and_stage_order():\n    m = manifest()\n    assert m['schema_version'] == 30\n    assert m['mode'] == 'shadow'\n    assert m['stage_order'] == [\n        'data_health', 'taxonomy_coverage', 'market_prosperity_search',\n        'level3_profitability_verification', 'profit_chain_decomposition',\n        'chain_company_light_screen', 'chain_company_comparison_and_dedup',\n        'valuation', 'price_structure', 'buy_point_synthesis', 'completion_gate'\n    ]\n    assert m['coverage_contract']['expected_counts'] == {'level1': 31, 'level2': 134, 'level3': 346}\n\n\ndef test_scan_cadence_is_prompt_search_then_selected_level3_verification():\n    c = manifest()['scan_cadence_contract']\n    assert c['full_scan_unit'] == 'prompt_full_market_prosperity_search'\n    assert c['weekly_full_prompt_search_required'] is True\n    assert c['weekly_full_does_not_require_level1_level2_status_matrix'] is True\n    assert c['persistent_level1_level2_prosperity_labels_forbidden'] is True\n    assert c['full_346_level3_profitability_review_required'] is False\n    assert c['selected_prosperity_directions_expand_all_relevant_level3'] is True\n    assert c['selected_prosperity_directions_may_not_be_top_n_capped'] is True\n    assert c['daily_incremental_between_full_scans'] is True\n\n\ndef test_prosperity_discovery_is_prompt_search_not_165_node_state_machine():\n    m = manifest()\n    d = m['market_prosperity_search_contract']\n    v = m['level3_profitability_verification_contract']\n    ledger = m['coverage_contract']['ledger_contract']\n    assert d['method'] == 'prompt_full_market_search'\n    assert d['full_market_search_does_not_require_level1_level2_status_rows'] is True\n    assert d['persistent_level1_level2_status_rows_forbidden'] is True\n    assert d['taxonomy_is_routing_after_search_not_search_state_machine'] is True\n    assert d['market_price_or_sector_return_cannot_be_primary_evidence'] is True\n    assert d['top_n_or_fixed_count_selection_forbidden'] is True\n    assert v['prosperity_direction_must_map_to_taxonomy_before_company_research'] is True\n    assert v['every_mapped_relevant_level3_requires_real_evidence_review'] is True\n    assert v['unselected_level3_not_required_for_weekly_profitability_review'] is True\n    assert ledger['level1_level2_are_routing_only_not_prosperity_state'] is True\n    assert ledger['required_node_fields'] == ['code','name','level','parent_code','accounted_for','routing_status','routing_reason']\n\n'''
text=text[:start]+new+text[end+1:]
# completion gate old assertions
text=text.replace("    assert g['all_level1_level2_prosperity_discovery_complete'] is True\n    assert g['no_prosperity_discovery_top_n_truncation'] is True\n    assert g['all_selected_directions_fully_expanded_to_level3'] is True\n    assert g['all_expanded_level3_profitability_verified'] is True\n", "    assert g['market_prosperity_prompt_search_complete'] is True\n    assert g['no_prosperity_search_top_n_truncation'] is True\n    assert g['all_selected_directions_have_taxonomy_mapping'] is True\n    assert g['all_mapped_relevant_level3_profitability_verified'] is True\n")
t.write_text(text,encoding='utf-8')

rt=ROOT/'tests/test_research_runtime_policy.py'
text=rt.read_text(encoding='utf-8').replace('# Schema29 CI checkpoint:', '# Schema30 CI checkpoint:').replace("assert p['schema_version'] == 9", "assert p['schema_version'] == 10")
old="""    assert s['weekly_full_scan_must_review_all_level1_level2_for_prosperity'] is True\n    assert s['weekly_full_scan_does_not_require_all_346_level3_profitability_reviews'] is True\n    assert s['prosperity_discovery_must_precede_level3_profitability_verification'] is True\n    assert s['prosperity_discovery_top_n_forbidden'] is True\n    assert s['selected_level2_must_expand_all_child_level3'] is True\n    assert s['selected_unresolved_level1_must_expand_all_descendant_level3'] is True\n    assert s['every_expanded_level3_must_be_profitability_verified'] is True\n    assert s['daily_incremental_requires_valid_weekly_baseline'] is True\n    assert s['daily_incremental_requires_all_level1_level2_trigger_checks'] is True\n"""
new="""    assert d['weekly_prompt_full_market_prosperity_search_cannot_be_replaced_by_previous_focus_list'] is True\n    assert d['persistent_level1_level2_prosperity_status_forbidden'] is True\n    assert s['weekly_full_requires_prompt_full_market_prosperity_search'] is True\n    assert s['weekly_full_must_not_build_level1_level2_status_matrix'] is True\n    assert s['weekly_full_scan_does_not_require_all_346_level3_profitability_reviews'] is True\n    assert s['prosperity_search_must_precede_level3_profitability_verification'] is True\n    assert s['prosperity_search_top_n_forbidden'] is True\n    assert s['every_selected_direction_must_map_to_relevant_level3'] is True\n    assert s['every_mapped_relevant_level3_must_be_profitability_verified'] is True\n    assert s['daily_incremental_requires_valid_weekly_baseline'] is True\n    assert s['daily_incremental_uses_prompt_search_for_new_or_changed_prosperity_evidence'] is True\n"""
text=text.replace(old,new)
rt.write_text(text,encoding='utf-8')

st=ROOT/'tests/test_research_state_coverage_ledger.py'
text=st.read_text(encoding='utf-8').replace('test_persisted_state_schema29_contract_when_present','test_persisted_state_schema30_contract_when_present').replace("== manifest['schema_version'] == 29", "== manifest['schema_version'] == 30")
# replace coverage validation block before confirmed chain comment
b1=text.index('    # Coverage exactness')
b2=text.index('    # All confirmed improving chains')
block='''    # Coverage is taxonomy routing only; prosperity/profitability state lives elsewhere.\n    ledger = state['coverage_ledger']\n    contract = manifest['coverage_contract']['ledger_contract']\n    required = set(contract['required_node_fields'])\n    level3_by_code = {}\n    for level in ('level1', 'level2', 'level3'):\n        expected = {node['code']: node for node in taxonomy['levels'][level]}\n        rows = ledger[level]\n        assert len(rows) == len(expected)\n        by_code = {row['code']: row for row in rows}\n        assert set(by_code) == set(expected)\n        if level == 'level3': level3_by_code = by_code\n        for code, row in by_code.items():\n            assert required.issubset(row)\n            assert row['name'] == expected[code]['name']\n            assert row['parent_code'] == expected[code]['parent_code']\n            assert row['level'] == level\n            assert row['accounted_for'] is True\n            assert row['routing_status'] in contract['allowed_routing_status']\n\n    assert isinstance(state['market_prosperity_search'], (dict, list))\n    verified = state['level3_profitability_verification']\n    rows = list(verified.values()) if isinstance(verified, dict) else verified\n    verified_by_code = {row['code']: row for row in rows}\n    for row in rows:\n        assert row['trend'] in {'improving','stable','deteriorating','unconfirmed'}\n        assert row['evidence_basis']\n\n'''
text=text[:b1]+block+text[b2:]
# confirmed chain derivation uses level3_by_code trend; change to verified_by_code
text=text.replace("if any(level3_by_code.get(code, {}).get('trend') == 'improving' for code in src):", "if any(verified_by_code.get(code, {}).get('trend') == 'improving' for code in src):")
st.write_text(text,encoding='utf-8')

print('schema30 lean discovery migration prepared')
