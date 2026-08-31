# A股低风险研究 V2 编排 Skill

## 目标
V2从正在改善的细分盈利驱动中，找到未来1–2季度仍有兑现逻辑、但股价尚未充分定价的公司，并最终形成可解释的**基本面公允价值锚、低风险估值、安全买入区、合理买入区、历史参照和价格状态**。

核心内核：
1. 先找盈利改善，不先找形态。
2. 研究单位是盈利驱动链，不是宽泛行业或T1/T2等级。
3. 以盈利为基、以估值为锚、以历史估值分位和历史价格为参照。
4. 先识别盈利类型，再选择估值模型；先回答“值多少钱”，再回答“什么价格值得买”。
5. 历史价格不能证明内在价值，不能参与估值投票，也不能成为正式确认锚。
6. 成长股Fair PE与低风险Entry PE必须分离：增长可以验证估值，但不能仅凭远期高增长抬升买点。
7. 最好的机会通常是“基本面已拐、价格刚启势”，而不是极端便宜或已经大涨。

## 唯一编排入口
先读取`config/research_pipeline_manifest.json`。业务Skill仍只有：`earnings-driver-scan / company-research / price-expectation-gap / opportunity-ranking`；估值参考与买点属于`price-expectation-gap`的机器执行子阶段。

## 固定执行阶段
### 0 DATA_HEALTH
检查主板全集、最新交易日、180日OHLCV、财务源、公司索引。数据缺失要显式披露，不能解释为“没有机会”。

### 1 EARNINGS_ANOMALY_RECALL + EARNINGS_DRIVER_SCAN
全主板机械宽召回，并独立识别细分盈利Driver。大行业只导航，Driver必须有直接盈利变量、正向证据、未来1–2季度传导和失效条件。历史T1/T2不控制准入，confidence不进入估值公式。

### 2 COMPANY_RESEARCH
召回取`Driver直接暴露 ∪ 盈利异常 ∪ 周度全市场深验`。公司级验证必须回答主营/扣非、现金流、一次性收益、Forward Bridge和失效条件。估值前每条Driver仅轻压缩到约3–5家，不提前只留1家。

### 3 VALUATION_REFERENCE：按盈利类型形成第一基本面锚
V2必须自己重建，不读取V1估值数值。固定顺序是：`真实盈利 → 盈利类型 → Forward/正常化盈利 → 合理估值倍数 → Fair Value → 低风险估值约束`。

- **成长/稳定经营**：Fair Value = 当年Forward EPS × 版本化业务PE；低风险Entry PE必须再由次年一致预期EPS的成长持续性约束。无公司显式`low_risk_multiple_range`时，必须调用版本化`growth_floor_caps`动态压缩Entry PE；当次年增长达到PEG有效阈值时，再用PEG上限检查Entry PE，但PEG只允许压低或限制，不能抬高Entry PE。缺次年一致预期时不得生成正式成长股Entry估值。
- **金融**：Forward ROE → PB合理带，PE只作辅助sanity。
- **资源/强周期**：先判断商品价格/供需Regime与利润处于周期何处，再正常化EPS/ROE，以PB和周期合理倍数估值。机械低PE常可能来自周期顶部高利润，机械高PE可能来自周期底部低利润，禁止把当前高景气利润直接资本化。

周期纪律：有商品锚时“长期中性商品条件去windfall”和“6–18个月regime”必须解释不同经济含义；无商品锚时只使用一个`single_cycle_factor=min(structural_factor, base_regime_factor)`，禁止结构折价与regime折价重复相乘。

`valuation_reference.json`对成长股必须同时保留Fair PE/Fair Value和成长约束后的Entry PE/Entry Value reference；二者不得混为一个区间。

### 4 VALUATION_ANCHORS：独立基本面确认与Margin of Safety
- **A Fundamental Fair Value**：公司自身、与盈利类型匹配的主估值锚。
- **B Independent Valuation Confirmation**：经济口径可比的同行PE/PB、PB-ROE、周期正常化或其他独立基本面估值方法。只有口径可比、样本有效时才可计入确认锚。
- **C History Reference**：公司自身180日复权价格和历史估值分位，仅作参照，不是内在价值锚，不计入`independent_anchor_count`。

A决定Fair Value。B用于检查主模型是否脱离独立基本面/可比估值；有效A/B出现重大经济冲突时触发`valuation_divergence`，不得强行平均。A与历史价格明显偏离只记`history_reference_divergence`，本身不阻断正式区间。

正式安全/合理区：
- 成长/稳定经营已经形成成长约束后的`effective_entry_multiple_range`时，直接由当年Forward EPS × Entry PE形成低风险区间，不再叠加统一Fair Value折价；
- 有显式`low_risk_multiple_range`时同样直接使用entry multiple，禁止再次统一折价；
- 只有没有独立Entry multiple机制的路线，才使用版本化`safe_to_fair_floor / reasonable_to_fair_floor`从Fair Value形成Margin of Safety；
- 金融以PB/ROE为主并反推PB sanity；
- 周期必须先正常化盈利，再使用周期政策的safe/reasonable-to-fair-floor。

180日P10/P25/P50/P60、MA60等只能展示历史参照和交易位置，**不得裁剪、抬高或创造安全/合理区**。

正式买点仍至少需要A+一把有效独立基本面/可比估值确认。历史参照C永远不能补足这个门槛。

### 5 FULL_MARKET_PRICE_STRUCTURE
对全部有新鲜180日历史的主板独立扫描，不能只扫描基本面候选。至少识别`base_not_started / transition / breakout / pullback / trend_continuation / overheated / damaged`。Breakout要求价格+成交量+收盘位置确认；Pullback要求20日相对强度不显著弱于市场；创新高不能因无历史压力被判弱。

### 6 PRICE_EXPECTATION_GAP
估值区间形成后才判断当前价：安全区、合理区、区间上方、充分定价、深度折价待复核或估值未完成。当前价显著低于安全区下沿进入`deep_discount_review`，优先排查价值陷阱；高于合理区上沿只能趋势/持有观察。历史参照只帮助解释位置，不改变买入区。

### 7 OPPORTUNITY_RANKING
每只候选固定输出：股票/代码/当前价、盈利Driver、Forward Bridge、基本面Fair Value、低风险估值来源、独立确认锚、历史参照、安全区、合理区、当前价值位置、价格结构、追高风险、动作、失效条件和blocker。

优先寻找：`盈利改善明确 + Forward Bridge成立 + 估值模型匹配 + 低风险估值成立 + 正式买入区成立 + 当前真的在区间内 + 价格刚启势/低风险回踩`。

Shadow可以展示高研究价值但尚缺正式买点的公司；Production必须同时满足公司证据ready、正式买点ready和合格价格状态。Top3允许少于3只或为空。

## 经济常识 Validator
至少拦截：
- 估值模型与盈利类型不匹配；
- 成长股缺次年盈利持续性约束仍生成正式Entry PE；
- 成长股Entry PE高于理论Fair PE，或在PEG适用时突破PEG上限；
- 周期股直接资本化景气顶部利润；
- 同一风险在EPS、regime、PE/PB和买点区重复折价；
- 有效独立基本面估值严重冲突仍生成正式买点；
- 把180日价格当确认锚，或让历史价格裁剪/抬高基本面区间；
- 少于A+1把有效独立基本面确认仍发布正式买点；
- 安全区与合理区顺序异常；
- 正式区间无法反推可解释PE/PB；
- 右侧因无上方压力淘汰创新高，或因不在基本面池而未扫描。

触发必须进入相应`sanity_check_failed / valuation_divergence / valuation_model_mismatch / earnings_normalization_unready / valuation_sensitivity_high / review_required`状态，不得通过分数修复。

## Shadow原则
当前Manifest为shadow时只能发布V2影子研究，不得称为正式买点。在历史回放与连续Shadow验证完成前不覆盖V1正式榜单。V1只保留对照，不得把其估值数值、旧买点、共同池右侧边界或T1/T2准入逻辑注入V2。Validator必须case-free，不得用固定股票、固定价格区间或人工历史答案作为PASS条件。
