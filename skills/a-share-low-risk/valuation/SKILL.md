# 估值 Skill — Valuation Engine V2

## 目的
回答 `valuation_set` 中每家公司的真实内在价值、安全价格上限与估值位置，为最终买点提供独立价值基础。

本 Skill 的核心纪律不是“尽量保守”，而是：**模型必须和公司的经济价值驱动匹配；保守性只能通过明确的情景与 Margin of Safety 表达，不能通过多轮重复压低盈利、倍数和价格来叠加。**

固定主线：
`真实核心盈利 → 公司行动/股本审计 → 价值驱动类型 → Forward/正常化经营情景 → 主模型 → 真独立第二模型/异常审计 → Base Fair Value → Reasonable Range → Downside Scenario → Margin of Safety → Safe Price Ceiling → 估值位置`

## 1. 公司行动、股本与核心盈利先行
Forward/正常化盈利前必须检查：
- 当前总股本/稀释股本及对比期变化；
- 换股吸收合并、重大资产重组、定增、拆并股；
- 历史利润是否追溯调整；
- 主营是否切换；
- 归母净利润是否被非经常损益污染。

股本变化达到 Manifest 阈值时，禁止“历史EPS × 增长率”。使用总扣非/核心盈利除以当前或 Forward 稀释股本重建每股盈利。

非经常损益占归母净利润达到 30% 及以上时，受污染归母利润不得进入 Forward Bridge；必须改用扣非/核心盈利。无法取得足够核心盈利证据才允许 `review_required:nonrecurring_earnings_dominant`。

## 2. 先识别 Valuation Archetype，不能只看申万一级行业
每家公司必须输出 `valuation_archetype` 与 `archetype_basis`。允许的主要类型：

1. `resource_asset`：矿山、油气、煤炭等价值主要来自资源储量、产量、商品价格、成本与资产寿命；
2. `spread_cyclical`：化工、冶炼、部分材料，价值主要来自产品-原料价差、开工、产量与正常化利润率；
3. `order_backlog`：船舶、重型装备、部分工程资本品，价值主要来自订单、交付、价格、产能与毛利率；
4. `growth_compounder`：电子、通信、软件及其他具有可验证增长、ROIC/现金流支撑的成长公司；
5. `stable_cashflow`：消费、公用事业、交通、成熟制造等稳定现金流业务；
6. `financial`：银行、券商、保险等资产负债表驱动业务；
7. `special_situation`：重大重组、业务切换、资产处置主导等特殊情形。

申万分类只能帮助路由，**不得单独决定估值模型**。同一行业不同公司可以属于不同 archetype。

## 3. 不同 Archetype 必须使用不同价值驱动

### 3.1 resource_asset
禁止把资源股统一套“6–10x PE”。必须显式研究：
- 核心商品价格锚：当前价格、近年中枢/成本曲线、供需与合理正常化区间；
- 可销售产量/权益产量及未来1–2年增量；
- 单位现金成本/完全成本；
- 资本开支、净债务、资源寿命/储量质量；
- 税费、少数股东及重要权益矿影响。

主模型优先：`NAV/DCF` 或 `normalized EV/EBITDA`。
独立第二模型：另一价值驱动家族，例如 `NAV/DCF ↔ normalized EV/EBITDA`、`FCF/dividend capacity ↔ EV/EBITDA`、必要时 `PB/ROE` sanity。

像紫金矿业这类多金属、产量仍在扩张的公司，必须把铜/金/锂等产量增长与项目投产纳入 Forward 资产/现金流，而不能用“上一年利润70% + 当期30%”简单压回历史中枢。

### 3.2 spread_cyclical
化工、冶炼等必须研究：
`产品价格 - 原料成本 = 价差 → 开工率/销量 → 正常化毛利/EBITDA`。

主模型优先：`normalized EV/EBITDA` 或价差情景 DCF；
第二模型：正常化核心盈利 PE / ROIC sanity。
不得仅因为属于“周期行业”统一使用固定低PE。

### 3.3 order_backlog
必须研究：
`在手订单 → 未来交付 → 单价 → 毛利率 → 产能利用率 → 未来1–2年核心盈利`。

主模型可用 `forward EV/EBIT / forward PE`；第二模型使用订单覆盖下的正常化现金流或 ROE/PB。短期利润高增不能直接永久资本化，但已锁定订单也不能被机械压回旧周期低谷。

### 3.4 growth_compounder
至少构造未来1–2年核心 EPS/FCF，并检查：
- 收入增长与订单/出货；
- 毛利率/费用率；
- ROIC/ROE；
- 现金转换；
- 资本强度；
- 增长可见度。

主模型：`justified forward PE / EV-EBIT`；第二模型：`DCF/FCF yield/PEG sanity`。PE 倍数不能只由行业标签决定。

### 3.5 stable_cashflow
主模型根据业务采用 `DCF / dividend capacity / EV-EBITDA / justified PE`，重点看现金流稳定性、资本开支、定价权与可持续增长。

### 3.6 financial
必须使用 `PB-ROE / residual income` 等资产负债表模型；缺少一致预期不能直接 review，必须用公开ROE、净资产、资产质量、资本约束自行构造区间。

## 4. 情景先于倍数：必须有 Base 与 Downside
每家非 review 公司至少构造：
- `base_case`：当前公开证据下最可能的未来1–2年经营情景；
- `downside_case`：关键 Driver 回到保守但仍合理水平时的情景；
- 可选 `upside_case`，只能用于不确定性描述，不能用于降低安全边际。

资源/周期公司必须让商品价格、价差、产量、成本等在情景中显式出现；成长公司必须让收入、利润率、ROIC/现金流出现。

**正常化不是自动回归旧年度利润。** 如果产能、资源量、产品结构或竞争优势发生结构性提升，正常化基础必须反映新的经营能力。

## 5. 真独立第二模型
“同一EPS × 8倍PE”与“同一EPS × 10倍PE”不算两个独立模型。

独立第二模型必须至少改变一个核心价值驱动家族：
- earnings multiple ↔ DCF/FCF；
- resource NAV ↔ normalized EV/EBITDA；
- PB-ROE ↔ residual income；
- order-forward PE ↔ normalized cash flow。

触发极端估值偏离时必须有真独立第二模型。若两个模型都只依赖同一盈利基数和不同倍数，审计视为失败。

## 6. Base Fair Value 与 Reasonable Range
每个执行成功的模型必须输出自己的 `model_value_low / model_value_base / model_value_high / key_inputs / confidence`。

最终：
- `base_fair_value`：来自主模型与独立模型的证据加权中枢；
- `reasonable_price_range`：围绕 Base Case 的模型/情景合理区间，而不是悲观情景到乐观情景的无限大包络；
- `downside_value`：单独保存，不和 reasonable range 混为一谈。

当前市场价格只能用于判断位置和触发审计，**不得反向把 Base Fair Value 调到接近市价**。

## 7. Margin of Safety：只折一次
旧做法“先把盈利压低 → 再给低倍数 → 再对合理价下沿打75%–85%”属于重复保守化，禁止使用。

新的核心字段是：`safe_price_ceiling`。

原则：
`Safe Price Ceiling = Base Fair Value × (1 - MOS)`，并结合 downside case 做一致性检查。

MOS 根据：
- 经营不确定性；
- 周期敏感度；
- 资本强度/杠杆；
- 模型间稳定性；
- 数据质量。

默认参考区间而非机械常数：
- low uncertainty：约10%–15%；
- medium：约15%–25%；
- high：约25%–35%。

若模型本身已经显式采用很保守的 downside 经营假设，不得再次无解释叠加极端 MOS。

`safe_price_range` 可作为展示性的偏好入场带，但**价值硬条件只看 current_price <= safe_price_ceiling**。价格低于展示带下沿不能因此变成“不满足价值”；极低价格应触发基本面/模型复核。

## 8. 极端偏离与市场现实审计
满足 Manifest 极端偏离条件时必须：
1. 复核股本、重组与核心盈利；
2. 复核 archetype 是否选错；
3. 复核正常化/Forward 情景是否忽略结构性产量、成本或业务变化；
4. 执行真独立第二模型；
5. 比较模型中枢差异。

若 Safe Price Ceiling 与当前价差距极大，也必须输出 `market_reality_audit`：说明市场当前隐含的盈利/倍数假设与模型差异在哪里。它是 sanity check，不允许直接用市价修改内在价值。

无法解释的巨大偏离必须 `review_required:model_instability`，而不是制造一个看似精确但经济上荒谬的安全价。

## 9. 必须输出的估值桥
至少包括：
- `current_price / price_date`；
- `valuation_archetype / archetype_basis`；
- `earnings_type / earnings_basis`；
- `current_share_count / share_count_basis`；
- `corporate_action_check / earnings_bridge_integrity`；
- `scenario_analysis`（至少base/downside）；
- `primary_method / primary_model_output`；
- `secondary_method / secondary_model_output`（按规则要求时）；
- `base_fair_value`；
- `reasonable_price_range`；
- `downside_value`；
- `uncertainty / margin_of_safety_pct / margin_of_safety_reason`；
- `safe_price_ceiling`；
- `safe_price_range`（仅展示带，可选下沿意义必须说明）；
- `valuation_position`；
- `falsifiers`；
- `valuation_quality_flags`；
- `valuation_attempt_complete / model_execution_status`。

## 10. valuation_position
至少使用：
`below_safe / in_safe_zone / fair / above_fair / materially_overvalued / review_required`。

其中 `below_safe / in_safe_zone` 的价值资格以 `safe_price_ceiling` 为核心，而不是展示带下沿。

## 11. review_required 是异常出口，不是偷懒出口
只允许重大重组口径断裂、核心盈利无法剥离、关键数据不可得、模型严重不稳定、商业模式断裂等实质异常。

缺一致预期、缺现成Forward EPS、需要自己构造商品价格/价差/订单情景，都不是 review 理由。

## Completion纪律
- valuation_set每家公司必须先完成 archetype 识别；
- 非review公司必须有 base/downside、Base Fair Value、合理价与 Safe Price Ceiling；
- resource_asset / spread_cyclical / financial 等不能只使用单一PE法；
- 所有极端偏离必须有真独立第二模型或转review；
- 估值完成不代表可以买，最终仍由价值资格与独立价格结构共同决定。

## 持久化
只写本次 `research_state.json` 的 `valuations`。旧估值不能作为本期内在价值输入，不写独立估值缓存。
