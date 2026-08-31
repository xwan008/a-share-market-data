# A股低风险研究 V2 Shadow

当前V2采用 `prompt_first_research`：开放式研究由Prompt完成，Skill只约束研究纪律，代码只维护必要的机械数据与计算。

## 当前V2长期数据只有2类
1. `full_market_price_structure.json`：全主板独立价格结构扫描，只用于交易时机。
2. `research_state.json`：唯一Prompt研究状态，集中保存 `market_discovery / profit_chains / chain_comparisons / companies / valuations / opportunities / diagnostics`。

不再把全市场盈利异常公司扫描作为主流程补漏机制。主要补漏责任放在“行业 → 盈利链”的高质量拆解。

## 研究主链
`全市场景气发现 → 盈利链递归拆解 → 链内公司比较 → 公司盈利验证 → 分类估值 → 价格结构 → 当前机会`

## 盈利链分辨率
最终盈利链不是固定行业层级，也不限制每个行业只能展示几条。

在停止拆分前必须确认：
1. 链内公司共享基本相同的直接盈利Driver；
2. 可以用基本相同的一组领先变量持续跟踪；
3. Driver到收入/销量/成本/毛利的利润传导基本一致；
4. 公司之间可以真正比较谁受益更大。

如果不同原料路线、产品/工艺、应用场景、客户资本开支来源或成本结构会改变盈利机制，就继续拆分。

如果继续拆分只是把公司名称分组，而盈利Driver、领先变量和利润传导没有实质变化，则停止，避免为了细而细。

`industry_scan_universe.json`只用于大行业覆盖防漏，不是产业链答案池；当期产业链必须由Prompt从当期证据开放式研究得到，不使用当前对话中的行业、产业链或股票名单作为发现起点。

### 链内公司比较
重点盈利链不能拿第一只代表股直接当最佳股。存在多个直接受益主板公司时，应先比较多个对象，并分别给：
- `fundamental_best`：业务暴露、主营/扣非、现金流和Forward Bridge综合最强；
- `current_opportunity_best`：加入估值与价格时机后，当前最值得关注；
- 两者可以不同；如果没有低风险当前机会，允许为空。

### Fair Value → 低风险区
正式估值必须显示桥接：
`盈利基础 → Fair方法/倍数或关键假设 → Fair Value → 不确定性 → 安全边际原因 → 低风险买入区`

不能只给两个区间而解释不了差异。同行估值、历史PE/PB、历史价格只作sanity/reference。

## 保留的V2机械代码
当前V2自动化只长期运行：
- `scripts/build_v2_full_market_price_structure.py`

旧盈利异常召回、Driver激活、company_research中间生成器、valuation reference/anchors、expectation gap、opportunity ranking、repair/fallback和closed-loop validators均退出当前架构。

## Shadow原则
Production Gate未开启前必须标注：**V2影子研究，不发布正式买点**。当前重点验证产业链拆分质量、跨期稳定性和估值稳定性，而不是为榜单凑出买点。
