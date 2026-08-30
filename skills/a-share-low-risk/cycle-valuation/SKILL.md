# 周期/资源股估值 Skill

## 目的
强制周期股先由“跨年度Forward盈利 + 未来6–18个月供需周期 + 商品/价差”决定盈利中枢，避免“当前高利润+低PE→直接给价值锚”，并禁止把`commodity_anchor_required`当成流程终点。

## 适用
有色、煤炭、油气、化工及其他利润与商品/价差高度绑定公司。机器锚配置见 `config/cycle_valuation_policy.json`；未来6–18个月结构化周期状态见 `config/cycle_regime_registry.json`。

## 固定依赖链
1. 识别主要利润来源及商品/价差暴露；多商品公司必须给主次/权重。紫金矿业不得只看单一铜价。
2. 获取**当前年度与下一年度**一致预期EPS，构建Forward-12m盈利代理。利润可能处于高点时禁止只用当前年度EPS。
3. 读取结构化6–18个月周期状态：供给恢复/新增产能、需求趋势、库存、政策/地缘扰动，并记录证据、复核日期与失效条件。
4. 获取商品/成本锚当前值、20/60日中枢、高点回撤及20/60趋势。短期价格锚只能作为有上限的近端修正，不能推翻中期供需状态。
5. 建立bear/base/bull周期情景，并映射到Forward-12m EPS。输入成本锚方向必须与售价锚相反处理。
6. 根据当前周期阶段选择版本化合理估值倍数。高利润/供给正常化阶段不能把峰值EPS按扩张期高倍数永久资本化。
7. 输出市场Forward PE（当前年/下一年/Forward-12m代理）作为交叉检查，明确区分“看起来低PE”与“真正低估”。
8. 只有完成1–7后才能计算价值锚、安全买入区与合理买入区。

## 电解铝特别规则
- 必须同时看铝售价与氧化铝成本。
- 必须显式纳入未来供给恢复、库存重建和需求正常化风险。
- “当前铝价高、氧化铝成本低”只能说明近端吨铝利润强，不能自动推出未来6–18个月盈利继续处于同一高位。
- 如果市场因未来复产/供给过剩预期而压低Forward PE，必须先判断该预期是否合理，再决定这是预期差还是低PE陷阱。

## 输出
- `cycle_tag`
- 当前年/下一年一致预期EPS与增长
- `forward_12m_eps_proxy / forward_eps_weights`
- `market_forward_pe_current_year / next_year / 12m_proxy`
- `commodity_anchors`
- `cycle_regime / cycle_regime_summary / cycle_regime_evidence / cycle_regime_scores`
- `short_term_anchor_effect_on_eps`
- `bear_base_bull_regime_factor`
- `bear_base_bull_forward_eps`
- `reasonable_multiple_range`
- `value_anchor_range`
- `safe_buy_range / reasonable_buy_range`
- `invalidation_condition / valuation_status`

## 硬规则
- 资源股正式估值必须同时有当前年与下一年一致预期盈利；缺下一年盈利时不得用当前高利润替代。
- 资源股正式估值必须有未过期的6–18个月周期Registry；过期或缺失则显式`unavailable`并触发更新。
- 商品锚明显转弱必须下修；商品锚改善只能作为受限的近端修正，不能直接抬估值倍数。
- 中期供需处于normalizing/oversupply风险时，必须通过Forward盈利情景和周期阶段倍数反映，而不是等现货价格先跌完才调整。
- 若关键行情接口或一致预期确实不可得，可输出`unavailable`，但必须记录具体数据缺口。
- 进入周期股左侧研究后不能因为计算复杂而跳过处理。
