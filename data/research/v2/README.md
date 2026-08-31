# A股低风险研究 V2 Shadow

当前V2采用 `prompt_first_research`：开放式研究由Prompt完成，Skill只约束研究纪律，代码只维护机械数据与计算。

## 当前V2长期数据只有3类
1. `earnings_anomaly_recall.json`：全主板盈利异常机械宽召回，用于补漏，不决定行业景气。
2. `full_market_price_structure.json`：全主板独立价格结构扫描，只用于交易时机。
3. `research_state.json`：唯一Prompt研究状态，集中保存 `market_discovery / profit_chains / chain_comparisons / valuations / opportunities / diagnostics`。

## 研究主链
`全市场景气发现 → 盈利链拆解 → 链内公司比较 → 公司盈利验证 → 分类估值 → 价格结构 → 当前机会`

### 链内公司比较
重点盈利链不能拿第一只代表股直接当最佳股。存在多个直接受益主板公司时，应先比较多个对象，并分别给：
- `fundamental_best`：业务暴露、主营/扣非、现金流和Forward Bridge综合最强；
- `current_opportunity_best`：加入估值与价格时机后，当前最值得关注；
- 两者可以不同；如果没有低风险当前机会，允许为空。

### Fair Value → 低风险区
正式估值必须显示桥接：
`盈利基础 → Fair方法/倍数或关键假设 → Fair Value → 不确定性 → 安全边际原因 → 低风险买入区`

不能只给两个区间而解释不了差异。同行估值、历史PE/PB、历史价格只作sanity/reference。

## 保留的代码
当前V2自动化只长期运行：
- `scripts/build_v2_earnings_anomaly_recall.py`
- `scripts/build_v2_full_market_price_structure.py`

旧Driver激活、company_research中间生成器、valuation reference/anchors、expectation gap、opportunity ranking、repair/fallback和closed-loop validators已退出当前架构。

## Shadow原则
Production Gate未开启前必须标注：**V2影子研究，不发布正式买点**。当前重点验证跨期稳定性，而不是为榜单凑出买点。
