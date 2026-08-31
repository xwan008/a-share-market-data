# A股低风险榜 V2 Shadow

本目录保存Prompt-first V2的机械输入与单一研究状态，不覆盖V1历史产物。

## 当前架构
`开放式全市场景气发现 → 盈利链拆解 → 公司盈利验证 → 分类估值 → 价格结构 → 机会综合`

前两步由当次Prompt根据最新公开证据完成；GitHub不再保存预填行业signal或Driver激活答案。

## 保留的机械数据
1. `earnings_anomaly_recall.json`：全主板盈利异常宽召回。它只负责发现“哪些公司值得进一步看”，不负责决定景气行业。
2. `full_market_price_structure.json`：全主板独立价格结构扫描。它只回答价格时机，不参与内在价值计算。

## Prompt研究状态
`research_state.json`是V2唯一的Prompt研究持久化状态，集中保存：
- `market_discovery`：全行业横向比较后的景气发现；
- `profit_chains`：改善行业向下拆出的真实盈利链；
- `companies`：公司业务暴露与财务验证；
- `valuations`：分类估值、Fair Value、不确定性和买入区；
- `opportunities`：最终研究机会与动作；
- `diagnostics`：数据缺口、反向证据和需要复核的问题。

## 已移除的旧V2派生层
不再维护：
- 预填`current_industry_scan_signals`；
- `industry_scan.json`答案表；
- `earnings_driver_scan.json`激活表；
- A/B/C估值锚投票；
- `valuation_anchors.json`；
- `price_expectation_gap.json`状态机；
- `shadow_crosscheck.json`；
- 旧`opportunity_ranking.json`。

## 研究纪律
- 覆盖清单只用于防漏，不是候选答案池；
- 不能从股票倒推产业链；
- 公司受益必须回到主营/扣非、现金流和业务暴露；
- 周期利润必须正常化后再估值；
- 同行和历史只作sanity/reference，不参与内在价值投票；
- 价格结构只回答“何时买”；
- 新架构完成连续Shadow验证前，所有输出都必须标注“V2影子研究，不发布正式买点”。
