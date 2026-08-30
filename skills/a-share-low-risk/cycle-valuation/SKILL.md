# 周期/资源股估值 Skill

## 目的
强制周期股先由商品/价差决定未来盈利中枢，避免“历史高增长+低PE→直接给价值锚”，并禁止把`commodity_anchor_required`当成流程终点。

## 适用
有色、煤炭、油气、化工及其他利润与商品/价差高度绑定公司。当前机器可执行的资源锚配置见 `config/cycle_valuation_policy.json`。

## 固定依赖链
1. 识别主要利润来源及商品/价差暴露；多商品公司必须给主次/权重。紫金矿业等多商品公司不得只看单一铜价。
2. 获取商品/成本锚的当前值、20/60日中枢、60日高点回撤及20/60日趋势。机器可读连续合约优先通过AKShare日线获取。
3. 结合未来6–18个月供需研究判断当前价格偏强/中性/偏弱是否可持续；程序价格锚负责量化，LLM研究负责解释供需和失效条件。
4. 建立未来1–2季度bear/base/bull商品情景；输入成本锚方向必须与商品售价锚相反处理。
5. 将商品情景通过公司/细分链`earnings_sensitivity`映射到Forward EPS/利润中枢。机构一致预期可以作为基准盈利，但必须经过商品情景压力测试，不能绕过商品锚。
6. 只有完成1–5后才能应用周期业务合理估值并计算价值锚、安全买入区与合理买入区。
7. 所有周期候选必须生成`cycle_valuation.json`记录；资源链若机器锚可取得，不允许直接返回`unavailable`。

## 输出
- `cycle_tag`
- `commodity_anchors`（当前/MA20/MA60/高点回撤/方向/权重）
- `profit_sensitivity`
- `bear_base_bull_anchor_factor`
- `bear_base_bull_forward_eps`
- `reasonable_multiple_range`
- `value_anchor_range`
- `safe_buy_range / reasonable_buy_range`
- `key invalidation`
- `valuation_status`

## 硬规则
- 商品锚明显转弱，必须下修未来盈利/价值锚；商品锚改善则只能通过盈利情景上修，不能直接抬估值倍数。
- 资源链（当前至少铜矿资源、电解铝）只要商品锚和Forward EPS数据可得，就必须完成情景计算；`commodity_anchor_required`不是合法终点。
- 若关键行情接口或一致预期确实不可得，可输出`unavailable`，但必须记录具体`anchor_errors`/数据缺口，Validator负责核验。
- 进入周期股左侧研究后不能因为计算复杂而跳过处理。
