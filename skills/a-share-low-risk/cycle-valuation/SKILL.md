# 周期/资源股估值 Skill

## 目的
强制周期股先由商品/价差决定未来盈利中枢，避免“历史高增长+低PE→直接给价值锚”。

## 适用
有色、煤炭、油气、化工及其他利润与商品/价差高度绑定公司。

## 固定依赖链
1. 识别主要利润来源及商品/价差暴露；多商品公司给主次/敏感度。
2. 商品/价差：当前中枢、20/60日趋势、近期高点回撤、反弹强度。
3. 未来6–18个月供需：新增供给、库存、需求、成本、政策/贸易约束。
4. 建立未来1–2季度 bear/base/bull 情景；禁止默认沿用近期高点。
5. 将情景映射为收入、毛利率、利润/正常化EPS。
6. 只有完成1–5后，才能应用合理估值并计算价值锚。

## 输出
- commodity_anchors
- profit_sensitivity
- bear/base/bull commodity assumptions
- bear/base/bull forward earnings
- reasonable valuation range
- scenario value anchors
- key invalidation

## 硬规则
- 商品锚明显转弱，必须下修未来盈利/价值锚，或明确价值锚暂不可确认。
- 若关键敏感度数据不可得，输出 `valuation_status=unavailable`，不能猜精确区间。
- 进入周期股左侧研究后不能因为计算复杂而跳过处理。
