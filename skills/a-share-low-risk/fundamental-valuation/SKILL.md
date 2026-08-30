# 非周期公司左侧估值 Skill

## 目的
把非周期公司的左侧价值判断固定为“前瞻盈利来源 → 业务估值政策 → 价值锚 → 安全/合理买入区”，禁止因一次半年报年化或当前股价反推合理PE。

## 输入
- 已通过 `earnings-validation` 的共同资格池公司。
- `config/valuation_policy_registry.json`。
- 最新财报、管理层指引、订单/出货/客户/产品结构、竞争格局。
- 机构一致预期：优先通过 `akshare.stock_profit_forecast_em` 获取当前年度/下一年度EPS及研报数。
- 当前价格仅用于最后比较价格位置。

## 前瞻盈利来源优先级
1. 多机构一致预期EPS（达到Registry要求的最小研报数）。
2. 明确管理层盈利指引 + 可审计公司级盈利模型。
3. 分季度/分业务模型推导未来4季度。
4. `H1 EPS×2`只能作为诊断参考，**不能单独形成正式价值锚**；对消费电子、出口、季节性交付等明显季节性公司尤其禁止。

## 固定算法
1. 判断是否属于商品/价差高敏感业务；若是，物理转交 `cycle-valuation`，本Skill不得处理。
2. 从一致预期/公司模型建立Forward EPS或未来12个月盈利中枢，并记录来源、机构数、下一年度增长。
3. 从 `valuation_policy_registry` 读取业务/公司估值政策；公司override必须包含可审计理由和复核触发条件，不能因为股价上涨而提高PE。
4. 合理倍数必须考虑增长持续性、ROE/现金流、竞争格局、业务质量与周期属性。若政策缺失，输出`unavailable`，不得临时拍PE。
5. `fair_value_floor = forward_E × multiple_low`，同时计算完整价值锚区间。
6. 安全买入区与合理买入区按Registry定义的相对fair-value-floor折价计算；安全区必须比合理区具有更高安全边际。
7. 当前价最后进入比较，形成 `safe_buy_zone / reasonable_buy_zone / above_buy_zone`。

## 输出
至少包含：
- `code/name/current_price`
- `forecast_source / forecast_report_count`
- 当前年/下一年一致预期EPS及增长（可获得时）
- `valuation_model`
- `forward_earnings_basis`
- `reasonable_multiple_range` 与 `multiple_rationale`
- `value_anchor_range`
- `safe_buy_range`
- `reasonable_buy_range`
- `valuation_status`
- `invalidation_condition`

## 硬规则
- 正式`valuation_status=valid`时，前瞻盈利不能仅来自`H1×2`。
- TTM PE/PB只能交叉检查，不是价值锚生成器。
- 当前价、技术突破、HH/HL、市场热度不能进入合理估值倍数因果输入。
- 公司/业务估值政策必须版本化；若盈利预期或增长结构达到`review_trigger`，先重审倍数，再生成价值锚。
- 所有正式价值锚必须可从Forward E和合理倍数重新计算。
