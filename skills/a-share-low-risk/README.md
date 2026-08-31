# A股低风险研究 V2 Skills

当前V2采用 **Prompt-first research** 架构：开放式研究能力留给Prompt，Skill只保留长期稳定的研究纪律，代码只做机械数据与计算。

## 核心研究链
`全市场景气发现 → 盈利链拆解 → 公司盈利验证 → 分类估值 → 价格结构 → 机会综合`

其中前两步由Prompt完成，不再通过固定Driver Skill、T1/T2状态机或预填signal表决定答案。

## 四个核心 Skill
1. `orchestrator`：约束研究顺序、Prompt/Skill/Code边界和Shadow发布纪律。
2. `company-research`：约束公司业务暴露、扣非/主营、现金流、一次性因素与Forward Bridge证据。
3. `valuation`：约束成长/稳定、金融、资源周期等估值模型选择以及Fair Value与安全边际纪律。
4. `price-structure`：约束全市场独立价格结构扫描，只回答交易时机，不参与内在价值计算。

## 明确不Skill化的部分
- 当前哪些行业正在变好；
- 一个改善行业应该拆出哪些真实盈利链；
- 哪条新产业链值得研究；
- 最终行业/公司研究优先级。

这些属于开放式研究判断，应由每次执行时的Prompt根据最新公开证据完成。

## GitHub数据边界
长期保留的机械数据资产：
- 全市场盈利异常召回；
- 公司行业索引/Registry；
- 最新行情与历史OHLCV；
- 全市场价格结构扫描。

Prompt研究结论集中持久化到：
- `data/research/v2/research_state.json`

不再维护预填行业signal、Driver激活表、A/B/C估值锚投票、预期差状态机等多层派生数据。

## Shadow原则
新架构完成连续Shadow验证前，只能输出“V2影子研究，不发布正式买点”。
