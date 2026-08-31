# 价格、估值锚与预期差 Skill

## 目的
先独立完成公司价值与低风险买点，再判断基本面改善已经被股价交易多少。固定原则：**以盈利为基、以估值为锚、以历史估值分位与历史价格为参照**。公允价值、买入区间、历史参照、价格结构四者必须分层，最后才汇总为预期差状态。

# A. 第一基本面估值锚：先分类，再估值
V2不得读取V1估值数值。估值顺序固定为：`真实盈利 → 盈利类型 → Forward/正常化盈利 → 合理估值倍数 → Fair Value`。

1. **成长/稳定经营**：Forward EPS × 合理PE。合理PE必须受未来1–2年增长持续性、盈利质量和Forward Bridge约束；输出next-year growth与PEG sanity。正向远期增长不能自动抬买点，增长转弱必须压制低风险倍数。
2. **金融**：Forward ROE → PB合理带；PE只做辅助sanity。
3. **商品/强周期**：先识别商品/供需Regime和周期位置，再把Forward或TTM扣非盈利还原为正常化EPS/ROE，结合PB与周期合理倍数估值。禁止直接资本化当前高商品价格对应的高利润。
4. **周期反身性纪律**：低PE可能来自周期顶部利润暴增，并不天然便宜；高PE可能来自周期底部利润塌陷，并不天然昂贵。判断必须回到正常化盈利、资产回报与商品周期位置。
5. 周期风险禁止重复折价：`single_cycle_factor = min(structural_factor, base_regime_factor)`；商品正常化与6–18个月regime不得重复表达同一风险。

输出第一锚：`data/research/v2/valuation_reference.json`。

# B. 独立确认与历史参照
- **A Fundamental Fair Value**：与公司盈利类型匹配的公司自身基本面主锚。
- **B Independent Valuation Confirmation**：经济口径可比的同行PE/PB、PB-ROE、周期正常化或其他独立基本面估值方法。只有估值单位一致、样本有效且经济口径可比时才计入确认锚。
- **C Historical Reference**：公司自身180日复权价格分布及可得的历史估值分位。C仅回答“市场过去如何定价/当前处于什么位置”，不是内在价值锚。

### 硬纪律
- C不得计入`independent_anchor_count`。
- C不得参与Fair Value加权、平均、取交集或投票。
- C不得裁剪、抬高、压低或创造安全/合理买入区。
- 有效A/B出现重大经济冲突时可触发`valuation_divergence`；不得强行平均。
- A与历史价格显著偏离只记`history_reference_divergence`诊断。若当前价显著低于安全区下沿，进入`deep_discount_review`排查价值陷阱，而不是因为历史低价自动判便宜。

输出：`data/research/v2/valuation_anchors.json`。

# C. 安全买入区 / 合理买入区
## 核心原则
买入区不是历史成本区，而是Fair Value在不确定性约束下的Margin of Safety区间。

- 当前价不能进入估值公式，只能在区间形成后判断位置。
- 正式区间至少需要A + 1把有效独立基本面/可比估值确认；C不能补足门槛。
- 无显式entry multiple时，使用版本化`safe_to_fair_floor / reasonable_to_fair_floor`从A的Fair Value下沿产生区间。
- 有显式`low_risk_multiple_range`时直接由盈利基准×entry multiple形成买入区，禁止再叠加统一折价。

## 成长/稳定经营
- 主锚：Forward EPS × 合理PE。
- 合理PE必须经过成长持续性校验；PEG仅作倍数与增长是否失配的sanity，不允许机械把PEG=1当唯一真值。
- 若次年盈利明显弱于当前年，低风险倍数必须受版本化growth cap约束；远期高增长不得自动抬升当前买点。

## 金融
- 主锚：Forward ROE-PB；PE辅助。
- 同行PB只有口径可比时才是B确认。
- 180日成本不进入PB合理带。

## 资源/强周期
- 先正常化EPS/ROE，再结合PB、周期合理倍数与商品Regime形成Fair Value。
- TTM扣非EPS fallback必须先去除周期windfall后才能资本化。
- 买入区来自正常化Fair Value的安全边际，而不是从当前低PE直接推导。

## 区间Sanity
每个正式区间必须输出：`fundamental_anchor_range / safe_buy_range / reasonable_buy_range / independent_anchor_count / history_reference / implied PE或PB / valuation_model / earnings_basis`。

# D. 全市场独立价格状态
价格结构必须先扫描所有具备新鲜180日历史的主板股票，不能由基本面候选池定义。风险警示证券仍扫描，但不得进入低风险机会候选。

结构类型：`base_not_started / transition / breakout / pullback / trend_continuation / overheated / damaged`。

Breakout必须价格突破+成交量确认+收盘位置确认；机械基准可使用`volume_ratio_1d_vs_20d >= 1.15`或`volume_ratio_5d_vs_20d >= 1.05`，且`close_location_pct >= 55`。Pullback的20日相对市场强度不得显著弱于市场，机械基准`>= -2%`。

# E. 价值位置与预期差
价值位置：`safe_buy_zone / reasonable_buy_zone / large_gap_above_buy_zone / remaining_gap_above_buy_zone / priced_in / deep_discount_review / valuation_review_required`。

与价格结构组合后形成：`safe_zone_not_started / reasonable_zone_not_started / gap_just_starting / trend_confirmed_gap_remaining / gap_above_zone_not_started / priced_in_or_overheated / fundamental_price_conflict / valuation_review_required`。

当前价高于合理区上沿时，即使趋势强且仍有公允价值空间，也只能作为Shadow趋势/持有观察；显著低于安全区下沿必须先完成价值陷阱复核。

## 输出
- `data/research/v2/valuation_reference.json`
- `data/research/v2/valuation_anchors.json`
- `data/research/v2/full_market_price_structure.json`
- `data/research/v2/price_expectation_gap.json`
