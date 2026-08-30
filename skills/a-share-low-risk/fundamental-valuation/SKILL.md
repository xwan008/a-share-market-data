# 非周期公司左侧估值 Skill

## 目的
把非周期公司的左侧价值判断固定为“前瞻盈利来源 → 估值模型归属 → 价值锚 → 安全/合理买入区”，禁止因一次半年报年化、当前股价或临时拍PE产生价值锚。

## 输入
- 已通过 `earnings-validation` 的共同资格池非周期公司。
- `config/valuation_policy_registry.json`。
- 最新财报、管理层指引、订单/出货/客户/产品结构、竞争格局。
- 机构一致预期：优先通过 `akshare.stock_profit_forecast_em` 获取当前年度/下一年度EPS及研报数。
- 市场PB/动态PE仅作金融估值桥与交叉检查；当前价格最后才进入买入区判断。

## 前瞻盈利来源优先级
1. 多机构一致预期EPS（达到Registry要求的最小研报数）。
2. 明确管理层盈利指引 + 可审计公司级盈利模型。
3. 分季度/分业务模型推导未来4季度。
4. `H1 EPS×2`只能作为诊断参考，不能单独形成正式价值锚。

## 估值模型归属
1. 商品/价差高敏感业务物理转交 `cycle-valuation`。
2. 普通非周期公司使用版本化Forward PE业务模型或公司override。
3. 券商/保险不得停在`PB_ROE_bridge_required`：券商执行Forward ROE-PB桥；保险在统一可机器读取EV缺失时执行显式标记为proxy的Forward ROE-PB桥，PE仅作交叉检查。
4. 一次性投资收益/资产处置显著污染利润的公司，必须进入`normalization_required`，有估值政策但不得在归一化前形成正式锚。
5. 一致预期不足可以输出`consensus_insufficient`；这是数据不足，不是估值政策缺失。
6. **任何进入非周期估值阶段的公司都必须拥有版本化估值政策；`unsupported_policy`数量必须为0，否则Validator硬失败。**

## 固定算法
1. 读取一致预期与公司业务标签。
2. 映射到PE/PB等版本化模型并记录`valuation_basis_unit`。
3. PE模型：以正式Forward EPS × 合理PE区间形成价值锚，同时输出当前年/下一年Forward PE用于交叉检查。
4. 金融PB模型：从市场PB反推最新BVPS代理，用当前年/下一年一致预期EPS计算Forward ROE，再按Registry的ROE-PB区间形成价值锚。
5. 合理倍数必须考虑增长持续性、ROE/现金流、竞争格局、业务质量与周期属性；公司override必须有可审计理由。
6. 安全买入区与合理买入区按Registry定义的相对fair-value-floor折价计算。
7. 当前价最后进入比较，形成 `safe_buy_zone / reasonable_buy_zone / above_buy_zone`。
8. 输出`policy_coverage`审计账；支持政策数必须等于非周期公司数。

## 输出
至少包含：
- `code/name/current_price`
- `forecast_source / forecast_report_count`
- 当前年/下一年一致预期EPS
- `valuation_model / valuation_basis_unit / policy_status / execution_state`
- `forward_earnings_basis`
- `reasonable_multiple_range` 与 `multiple_rationale`
- `value_anchor_range`
- `safe_buy_range / reasonable_buy_range`
- PE模型的市场Forward PE；PB模型的BVPS代理/市场PB/Forward ROE
- `valuation_status / invalidation_condition`
- 顶层`policy_coverage`

## 硬规则
- 正式`valuation_status=valid`时，前瞻盈利不能仅来自`H1×2`。
- TTM PE/PB只能交叉检查，不是普通公司的价值锚生成器；金融PB模型例外是以BVPS与Forward ROE构成明确因果桥。
- 当前价、技术突破、HH/HL、市场热度不能进入合理估值倍数因果输入。
- 公司/业务估值政策必须版本化；若盈利预期或增长结构达到`review_trigger`，先重审倍数，再生成价值锚。
- 所有正式价值锚必须可从Forward E或BVPS/Forward ROE与合理倍数重新计算。
- `unsupported_policy > 0`时，本阶段不得PASS。
