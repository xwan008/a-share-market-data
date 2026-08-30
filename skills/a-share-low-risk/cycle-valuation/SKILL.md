# 周期/资源股估值 Skill

## 目的
为有色、煤炭、化工等利润与商品/价差高度绑定的公司建立**低风险买点估值**，不是计算牛市情景下的理论最高价值。

核心原则：
1. 当前年盈利是低风险估值的主锚，下一年乐观增长不能自动抬高买点；
2. 有可靠机器商品/成本序列时，先还原中性商品/成本水平下的正常化盈利；
3. 没有可靠机器商品序列时，不允许整条T2链因为“不会抓价格”而消失，改走更保守的`conservative_consensus_cycle`：当前年EPS主锚 + 下一年下行约束 + 结构折价；
4. 所有周期模型都必须判断未来6–18个月周期位置；
5. 所有周期模型最终都用公司自身180日市场价格分布校准安全/合理买入区；
6. 当前商品价格越强，不能机械地把低风险买入价越抬越高。

## 两种正式模式
### A. `commodity_anchor_normalized`
适用于铜、电解铝等存在稳定、可机器读取的售价/成本序列：
- 当前年/下一年一致预期 → Forward代理；
- 504交易日左右商品/成本中性价格；
- 剥离当前超额价差；
- 6–18个月周期Registry；
- 保守估值倍数；
- 180日价格校准。

### B. `conservative_consensus_cycle`
适用于动力煤、制冷剂、氨纶等产品结构/价差复杂或公开机器序列不稳定的周期链：
- 当前年一致预期EPS是主锚；
- 下一年EPS只能向下约束，不能因增长而抬高当前买点；
- 使用版本化`anchorless_normalization_haircut`主动折减可能含周期红利的盈利；
- 再乘结构化6–18个月bear/base/bull周期因子；
- 使用保守周期PE；
- 最后同样经过180日最低价/P10、MA60和基本面上限校准。

这个模式不是降低标准。它明确禁止用TTM PE、半年报简单年化或单一现货报价代替正式盈利锚。

## 固定依赖链
1. 识别主要利润来源及商品/价差暴露；多商品公司必须给主次/权重。
2. 正式周期估值原则上必须有当前年和下一年一致预期EPS。当前年是低风险主锚，下一年只允许向下约束。
3. 根据`config/cycle_valuation_policy.json`确定估值模式，禁止在代码中为行业临时写死分支。
4. `commodity_anchor_normalized`必须获取长期商品/成本序列并计算中性水平；当前高售价/低成本形成的超额利润只能下修正常化EPS，不能提高买点。
5. `conservative_consensus_cycle`必须使用版本化结构折价，不能因为缺商品序列直接`unavailable`，也不能退回TTM PE。
6. 所有正式周期估值必须读取`config/cycle_regime_registry.json`中的6–18个月结构状态。
7. 根据周期阶段选择版本化合理倍数，得到理论情景参考；`scenario_fair_value_range`不得直接叫价值锚。
8. 所有周期股读取本地180日复权价格：
   - 安全候选：180日最低价～P10；
   - 合理候选：P10～P60；
   - 合理上沿受正常化基本面公允下沿×宏观折价与MA60×1.06共同限制。
9. 最终输出`safe_buy_range / reasonable_buy_range / value_anchor_range`。

## 当前重点链规则
### 电解铝
必须同时看铝售价与氧化铝成本，并纳入未来供给恢复、库存重建和需求正常化风险。

### 铜矿/黄金
铜/金价格高位时一致预期EPS具有明显顺周期性；商品强势只能提高盈利兑现置信度，不能直接提高低风险买入区。紫金等多商品公司必须按利润贡献权重正常化。

### 动力煤
禁止继续把已失去可靠连续交易的动力煤期货符号当唯一硬锚。使用2026 EPS主锚、2027下行约束、煤炭周期结构折价与180日价格校准；煤价上涨本身不能抬高买点。

### 氟化工/制冷剂
配额约束可以支撑景气，但R32/R134a/R125产品结构和萤石/氢氟酸成本复杂，不能用单一价格序列伪装精确价差。使用保守一致预期周期模式，并对当前高价差进行结构折价。

### 氨纶
必须考虑氨纶价格、PTMEG/MDI成本、库存、开工、新增产能和出口。行业处于修复阶段时，低基数高增长不得直接换成高PE。

## 估值覆盖硬规则
- `T2景气`只说明值得研究，不允许因为估值引擎缺失把整条链静默排除。
- 每次估值运行必须生成`data/research/pipeline/t2_valuation_coverage_audit.json`。
- 若某条已进入共同池的T2链因为模型缺失、机器锚失效或周期Registry缺失而出现**0个正式可估值公司**，流水线硬失败。
- 一致预期覆盖不足属于数据覆盖问题，不允许伪造估值；必须进入coverage warning并在执行健康中披露，不能解释成“该板块没有机会”。
- 关键行情接口不可得时只能切换到已版本化的保守模式，禁止临时主观补价格。

## 输出
- `cycle_tag / valuation_mode`
- 当前年/下一年一致预期EPS与增长
- `forward_12m_eps_proxy`
- `normalized_forward_eps`
- 机器锚模式：`commodity_anchors / neutralization_factor`
- 保守无锚模式：`low_risk_eps_pre_haircut / low_risk_eps_guard_method / anchorless_cycle_haircut`
- `cycle_regime / cycle_regime_summary / cycle_regime_evidence`
- `bear_base_bull_regime_factor / bear_base_bull_forward_eps`
- `reasonable_multiple_range`
- `scenario_fair_value_range / normalized_base_fair_value_floor`
- `market_price_anchor_180d / price_calibration_method`
- `value_anchor_range / safe_buy_range / reasonable_buy_range`
- `invalidation_condition / valuation_status`

## 失败原则
- 缺当前年/下一年一致预期时，不用TTM PE或H1简单年化替代，显式`unavailable`并计入数据覆盖警告。
- 周期Registry过期或缺失，显式`unavailable`并触发结构覆盖审计。
- 机器锚模式关键商品/成本序列失败时不能默默排除整条产业链；应有版本化无锚模式时切换，否则硬失败等待模型补齐。
- 进入周期股左侧研究后不能因为计算复杂而跳过处理。
