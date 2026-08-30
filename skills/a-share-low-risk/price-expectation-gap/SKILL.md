# 价格、估值锚与预期差 Skill

## 目的
先独立完成公司价值与低风险买点，再判断基本面改善已经被股价交易多少。公允价值、买入区间、价格结构三者必须分层计算，最后才汇总为预期差状态。

# A. 第一基本面估值锚
V2不得读取V1估值数值。

1. 稳定成长/制造：当年Forward EPS × 版本化业务PE区间；次年盈利只做耐久性检查，不能因乐观远期增长自动抬买点。
2. 券商/保险等金融：Forward ROE → PB合理带；PE只做辅助sanity。
3. 商品/强周期：先把一致预期盈利还原到正常化盈利，再给周期PE。机器商品锚使用长期中性商品/成本；无统一商品锚的周期链使用当年EPS、次年下行保护和单一周期保守因子。
4. 周期风险禁止重复折价：无商品锚周期的`single_cycle_factor = min(structural_factor, base_regime_factor)`，禁止两者继续乘算；商品正常化与6–18个月regime必须分别解释“去除当前windfall”和“未来供需情景”，不能重复表达同一风险。

输出第一锚：`data/research/v2/valuation_reference.json`。

# B. 独立交叉锚
正式低风险买点采用三锚框架：

- **A Fundamental Anchor**：上述公司自身基本面估值，是价值主锚。
- **B Peer Valuation Anchor**：东方财富同行估值比较；普通公司优先使用当年Forward PE同行P25/P50，金融使用PB-MRQ同行P25/P50。它只检查我们给出的估值倍数是否脱离同行，不覆盖公司自身盈利逻辑。
- **C Historical Market-cost Anchor**：公司自身180日复权价格分布，至少120个交易日；使用P10/P20/P25/P35/P50/P60与MA60。它是成本/交易锚，不是基本面公允价值。

### 锚冲突
- A与B都可用时比较两者公允价值中值；偏离超过45% => `valuation_divergence`。
- divergence时不得强行平均、不得生成正式安全/合理区。
- B缺失不是自动失败；A+C仍可形成低风险entry，但必须明确B unavailable。

输出：`data/research/v2/valuation_anchors.json`。

# C. 安全买入区 / 合理买入区
## 核心原则
- 先形成A，再形成买点；绝不能看当前股价后倒推估值。
- 正式区间至少需要A+(B或C)两把独立锚。
- C只负责校准entry，不允许因为过去股价高就抬高公允价值。
- 当前价不能进入估值公式，只能在区间形成后判断位置。

## 普通公司
若公司没有显式`low_risk_multiple_range`：
- 基本面安全边界：公允下沿 × 82%–90%；
- 基本面合理边界：公允下沿 × 90%–100%；
- 再使用180日P10/P25/P35/P60与MA60约束实际entry。

若公司已有显式`low_risk_multiple_range`：
- 直接由当年EPS × entry multiple形成低风险基本面买点；
- **禁止再叠加统一0.8/0.9折价**；
- 历史成本仍可限制区间，但不能二次折价同一风险。

## 金融
- 基本面锚来自Forward ROE/PB；
- 同行PB和自身180日成本作交叉；
- 安全/合理区生成后必须反推隐含PB；不允许用高波动净利润PE代替主估值。

## 周期
- 先正常化EPS；
- 使用细分周期政策自带`safe_to_fair_floor`与`reasonable_to_fair_floor`；
- 180日成本只校准entry；
- 当前商品价格短期走强不能抬高低风险买点。

## 区间Sanity
每个正式区间必须输出：
- `fundamental_anchor_range`
- `value_anchor_range`
- `safe_buy_range`
- `reasonable_buy_range`
- `independent_anchor_count`
- PE模型反推`safe_implied_pe/reasonable_implied_pe`，PB模型反推对应PB。

# D. 全市场独立价格状态
价格结构必须先扫描所有具备新鲜180日历史的主板股票，不能由基本面候选池定义。风险警示证券仍扫描，但不得进入低风险机会候选。

结构类型：`base_not_started / transition / breakout / pullback / trend_continuation / overheated / damaged`。

Breakout必须价格突破+成交量确认+收盘位置确认；机械基准可使用`volume_ratio_1d_vs_20d >= 1.15`或`volume_ratio_5d_vs_20d >= 1.05`，且`close_location_pct >= 55`。Pullback的20日相对市场强度不得显著弱于市场，机械基准`>= -2%`。

# E. 价值位置与预期差
价值位置：
- `safe_buy_zone`
- `reasonable_buy_zone`
- `large_gap_above_buy_zone`
- `remaining_gap_above_buy_zone`
- `priced_in`
- `deep_discount_review`
- `valuation_review_required`

与价格结构组合后形成：
- `safe_zone_not_started`
- `reasonable_zone_not_started`
- `gap_just_starting`
- `trend_confirmed_gap_remaining`
- `gap_above_zone_not_started`
- `priced_in_or_overheated`
- `fundamental_price_conflict`
- `valuation_review_required`

`gap_just_starting`仍是最高优先级，但只有盈利研究、估值锚和结构确认全部成立时才能进入Production候选。

## 输出
- `data/research/v2/valuation_reference.json`
- `data/research/v2/valuation_anchors.json`
- `data/research/v2/full_market_price_structure.json`
- `data/research/v2/price_expectation_gap.json`
