# 估值 Skill

## 目的
回答`valuation_set`中每家公司的：当前价格、合理价值区、安全价格区、估值位置，并为最终买点提供独立价值基础。进入估值层后禁止走捷径：不能拿短期高增长直接永久资本化，不能跨重大股本变化机械放大EPS，也不能因为模型给出极端低估就直接相信模型。

## 固定顺序
`真实盈利 → 公司行动/股本口径审计 → 盈利类型 → Forward/正常化盈利 → 主估值模型 → 第二模型/异常审计（如触发） → 合理价格 → 不确定性 → Margin of Safety → 安全价格 → 估值位置`

## 1. 先做公司行动与股本口径审计
在构造Forward EPS以前必须检查：
- 当前总股本/稀释股本；
- 对比期与当前期股本变化；
- 换股吸收合并、重大资产重组、定增、拆并股等；
- 历史利润口径是否因同一控制合并/追溯调整发生变化；
- 主营是否发生实质切换。

必须输出：
`current_share_count / share_count_basis / corporate_action_check / earnings_bridge_integrity`。

若股本变化达到Manifest阈值，禁止使用“历史EPS × 利润增长率”构造Forward EPS。优先用**总利润/扣非利润 → 当前或Forward稀释股本**重新计算每股盈利。

重大重组不必自动放弃估值，但必须先证明历史与未来盈利口径可比；无法证明时才进入`review_required:major_restructuring`。

## 2. 盈利类型与模型路线
- 成长/稳定：Forward或正常化EPS × justified PE，增长持续性、ROE/ROIC、利润率、现金转换、资本强度、可见度共同决定倍数。
- 金融：PB-ROE为主，关注可持续ROE、资产质量和资本充足。
- 资源/强周期：商品/价差/供需位置 → 正常化盈利/ROE → 周期中枢估值，并用PB/资产价值交叉验证。禁止把当期高景气利润直接乘成长PE。
- 订单型周期/资本品：订单、交付周期、价格、成本、产能、正常化毛利率 → 场景盈利 → 周期中枢估值。禁止因为H1利润增长很高就自动使用22–30x成长PE。

## 3. 缺一致预期时自行构造区间
没有卖方一致预期、Forward EPS或现成合理PE都不是停止理由。必须继续使用公开证据：年度/季度/TTM扣非、Q1/Q2边际、订单、销量、价格、产量、开工率、毛利率、成本、费用率、公司指引、供需与周期中枢等。

允许宽区间，不允许伪精确。预测越不确定，合理价值区越宽、MOS越高。

## 4. 主模型不能机械外推短期高增
Forward/正常化盈利至少回答：
- 当前高增中多少来自低基数、价格周期、一次性因素、并表或产能集中释放；
- 未来1–2年Driver能否维持；
- 对资源/订单型公司，当前景气利润与正常化利润的差距；
- 利润增速与可持续ROE/现金流是否匹配。

“2026H1利润+160% → 2026全年EPS同比+160% → 给成长PE”属于禁止的机械资本化。

## 5. 极端估值偏离审计
如果主模型出现Manifest定义的极端偏离，例如合理价值下沿已经达到当前价1.5倍以上，或当前价达到合理价值上沿1.5倍以上，必须启动`extreme_valuation_deviation_audit`。

审计必须包含：
1. 重新检查当前股本、历史EPS口径、重组/并购；
2. 重新检查周期位置与增长持续性；
3. 使用**独立第二估值方法**交叉验证，例如：PE ↔ DCF/PEG sanity、周期PE ↔ PB/EV-EBITDA/资产价值、订单周期PE ↔ 正常化ROE/PB；
4. 比较两种方法中枢差异。

若两种方法中枢差异超过Manifest阈值且无法解释，必须`review_required:model_instability`。极端低估不是“买入加分项”，而是“证明责任升级”。

## 6. 完整估值桥
每家公司至少记录：
- `current_price / price_date`；
- `earnings_type / earnings_basis`；
- `current_share_count / share_count_basis`；
- `corporate_action_check / earnings_bridge_integrity`；
- `primary_method / key_assumptions`；
- 触发极端偏离时的`secondary_method / extreme_valuation_deviation_audit`；
- `reasonable_price_assumption / reasonable_price_range`；
- `uncertainty`；
- `margin_of_safety_reason / safe_price_range`；
- `valuation_position`；
- `falsifiers`；
- `valuation_attempt_complete=true / model_execution_status`。

## 7. valuation_position
至少使用：`below_safe / in_safe_zone / fair / above_fair / materially_overvalued / review_required`。

当前价格只能用于**比较位置**和触发异常审计，不能反向修改合理价值本身。

## 8. 安全价格区
安全价格与合理价值必须来自同一盈利基础。MOS必须随不确定性、周期性、资本强度、估值模型稳定性调整，不能机械固定一个折扣然后不做解释。

安全区是价值条件，不等于当前买点。即使当前价进入安全区，如果价格结构仍`damaged`或未形成有效入场结构，最终动作仍应等待。

## 9. review_required：严格异常出口
仅允许Manifest列出的实质异常：重大重组口径断裂、一次性收益无法剥离、关键数据不可得、模型严重不稳定、商业模式断裂等。

不能因为缺一致预期、缺Forward EPS、需要正常化商品价格、半年报不能简单年化而停止。

使用时必须记录：
`valuation_attempt_complete=true / model_execution_status=blocked_after_full_attempt / review_exception_code / attempted_inputs / blocker_evidence / review_reason`。

## Completion纪律
- valuation_set每家公司都必须执行；
- 非review公司必须有合理价、安全价、估值位置；
- 所有触发极端偏离的公司必须完成第二模型审计或转review；
- 重点盈利链至少1家形成完整非review估值桥，才允许机会解析完成；
- 估值完成不代表可买，最终买点由Buy Point Contract将安全区与价格结构求交集。

## 持久化
只写本次`research_state.json`的`valuations`，不使用旧估值作为本期内在价值输入，不写独立估值缓存。
