# 非周期公司左侧估值 Skill

## 目的
把非周期公司的左侧价值判断固定为“前瞻盈利来源 → 估值模型归属 → 理论业务估值 → 低风险PE/ PB锚 → 安全/合理买入区”，禁止因行业景气、一次半年报年化、当前股价或临时拍PE直接抬高买入区。

核心原则：**行业理论PE不是低风险买点PE。** 左侧榜的目标不是回答牛市里公司最高可以给多少倍，而是回答在当前年度可验证盈利基础上，什么价格才具有足够安全边际。

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

## PE模型的固定原则
1. **当前年度一致预期EPS是低风险买点的主盈利锚。** 在2026年，正式PE买点首先锚定2026 EPS。
2. 下一年度EPS是盈利持续性检查，不是自动抬价器：
   - 2027增长不能机械提高2026低风险买点PE；
   - 2027增速低、持平或下降时，可以压低允许的低风险PE；
   - 若2026利润包含明显一次性/非经常性收益，应进入公司级归一化或更保守PE覆盖，不能因2026表观EPS高就给高价值锚。
3. `multiple_range`表示业务/行业在盈利兑现时的**理论公允PE区间**，不得直接等同安全/合理买入PE。
4. 真正用于左侧买点的是`low_risk_multiple_range`：
   - 优先读取经过审计的公司级`low_risk_multiple_range`；
   - 没有公司级覆盖时，理论PE下限必须接受下一年度盈利持续性的增长护栏；
   - 低风险PE只能等于或低于理论业务PE，不得高于理论业务PE。
5. 输出必须同时保留：
   - `theoretical_business_multiple_range`
   - `business_fair_value_range`
   - `reasonable_multiple_range`（实际低风险PE）
   - `value_anchor_range`（实际低风险价值锚）
   这样理论成长估值和实际买点不会再混淆。

## 默认低风险PE持续性护栏
若公司没有显式`low_risk_multiple_range`，使用下一年度一致预期增长约束理论PE下限：
- 下一年增长 <= 0%：低风险PE下限最高13倍；
- 0%～10%：最高15倍；
- 10%～20%：最高18倍；
- 20%～35%：最高20倍；
- 35%～50%：最高22倍；
- >50%：最高24倍。

这是**上限护栏**，不是自动给予相应PE。例如业务理论PE本来只有13倍，即使增长很高也仍然只能使用13倍附近的低风险下限。

## 买入区算法
PE公司：
1. `2026 consensus EPS × low_risk PE下限 = low-risk fair floor`。
2. 默认安全买入区 = fair floor × 0.78～0.90。
3. 默认合理买入区 = fair floor × 0.90～1.00。
4. 公司级政策可以进一步收紧，但不能因为行业热度扩大。
5. 当前价格最后进入比较，形成`safe_buy_zone / reasonable_buy_zone / above_buy_zone`。

因此，一个公司即使行业理论估值是20～28倍，如果公司级低风险PE只有12～16倍，左侧榜必须按12倍附近的fair floor生成买入区，而不是按20倍生成。

## 典型校准案例
- 长高电气：2026 EPS为主锚；2027盈利预期下降且2026存在显著非经常性收益影响，理论电网设备18～25倍不能直接作为买点，低风险PE按13～16倍。
- 天赐材料：2026盈利强修复，但电解液/六氟利润仍受产品价格、原料成本、供需和产能利用率影响，理论成长PE与低风险买点分离，低风险PE按12～16倍。
- 苏美达：订单能见度高但业务仍偏制造/供应链，低风险PE按10～12倍，不把远期订单全部资本化。
- 璞泰来：设备订单支撑成长，但材料业务仍有价格和产能周期，低风险PE按17～21倍。

这些公司级范围是版本化政策，可在盈利结构、现金流、订单质量或行业竞争格局发生实质变化时重审，而不是永久固定。

## 估值模型归属
1. 商品/价差高敏感业务物理转交 `cycle-valuation`。
2. 普通非周期公司使用版本化Forward PE业务模型或公司override。
3. 券商/保险不得停在`PB_ROE_bridge_required`：券商执行Forward ROE-PB桥；保险在统一可机器读取EV缺失时执行显式标记为proxy的Forward ROE-PB桥，PE仅作交叉检查。
4. 一次性投资收益/资产处置显著污染利润的公司，必须进入`normalization_required`或显式公司级保守估值政策，在归一化风险未解决前不得使用高行业PE。
5. 一致预期不足可以输出`consensus_insufficient`；这是数据不足，不是估值政策缺失。
6. **任何进入非周期估值阶段的公司都必须拥有版本化估值政策；`unsupported_policy`数量必须为0，否则Validator硬失败。**

## 金融PB模型
金融公司继续执行Forward ROE-PB，不受上述PE增长护栏机械替代：
1. 从报告BVPS/市场PB构造可审计BVPS桥；
2. 用当前年/下一年EPS形成Forward ROE；
3. 按Registry的ROE-PB区间形成价值锚；
4. PE仅作交叉检查。

## 输出
至少包含：
- `code/name/current_price`
- `forecast_source / forecast_report_count`
- 当前年/下一年一致预期EPS
- `valuation_model / valuation_basis_unit / policy_status / execution_state`
- `forward_earnings_basis`
- PE模型：`theoretical_business_multiple_range / growth_pe_floor_cap / low_risk_pe_method / reasonable_multiple_range`
- PE模型：`business_fair_value_range / value_anchor_range`
- `safe_buy_range / reasonable_buy_range`
- PE模型的市场Forward PE；PB模型的BVPS代理/市场PB/Forward ROE
- `valuation_status / invalidation_condition`
- 顶层`policy_coverage`

## 硬规则
- 正式`valuation_status=valid`时，前瞻盈利不能仅来自`H1×2`。
- 在当前年度内，下一年度正增长不得直接抬高低风险买点盈利锚或PE；下一年度恶化可以压低PE。
- 行业/业务理论PE不得直接作为低风险买入PE，除非公司级政策明确审计后确认二者相同。
- 当前价、技术突破、HH/HL、市场热度不能进入合理估值倍数因果输入。
- 公司/业务估值政策必须版本化；若盈利预期或增长结构达到`review_trigger`，先重审倍数，再生成价值锚。
- 所有正式价值锚必须可从当前年度Forward E或BVPS/Forward ROE与低风险倍数重新计算。
- `unsupported_policy > 0`时，本阶段不得PASS。
