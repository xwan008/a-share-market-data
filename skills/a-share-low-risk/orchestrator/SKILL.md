# A股低风险研究 V2 编排 Skill

## 目标
V2从正在改善的细分盈利驱动中，找到未来1–2季度仍有兑现逻辑、但股价尚未充分定价的公司，并最终形成可解释的**基本面估值锚、价值锚、安全买入区、合理买入区和价格状态**。

核心内核：
1. 先找盈利改善，不先找形态。
2. 研究单位是盈利驱动链，不是宽泛行业或T1/T2等级。
3. 公允价值和低风险买点分层：先回答“值多少钱”，再回答“什么价格值得买”。
4. 估值至少两把独立锚交叉，禁止重复折价和用当前价反推目标价。
5. 最好的机会通常是“基本面已拐、价格刚启势”，而不是极端便宜或已经大涨。

## 唯一编排入口
先读取`config/research_pipeline_manifest.json`。业务Skill仍只有：`earnings-driver-scan / company-research / price-expectation-gap / opportunity-ranking`；估值参考与多锚买点属于`price-expectation-gap`的机器执行子阶段。

## 固定执行阶段
### 0 DATA_HEALTH
检查主板全集、最新交易日、180日OHLCV、财务源、公司索引。数据缺失要显式披露，不能解释为“没有机会”。

### 1 EARNINGS_ANOMALY_RECALL + EARNINGS_DRIVER_SCAN
全主板机械宽召回，并独立识别细分盈利Driver。大行业只导航，Driver必须有直接盈利变量、正向证据、未来1–2季度传导和失效条件。历史T1/T2不控制准入，confidence不进入估值公式。

### 2 COMPANY_RESEARCH
召回取`Driver直接暴露 ∪ 盈利异常 ∪ 周度全市场深验`。公司级验证必须回答主营/扣非、现金流、一次性收益、Forward Bridge和失效条件。估值前每条Driver仅轻压缩到约3–5家，不提前只留1家。

### 3 VALUATION_REFERENCE：第一基本面锚
V2必须自己重建，不读取V1估值数值：
- 普通成长/制造：当年Forward EPS × 版本化业务PE；
- 金融：Forward ROE → PB合理带；
- 周期：正常化盈利 → 周期PE。

周期纪律：有商品锚时“长期中性商品条件去windfall”和“6–18个月regime”必须解释不同经济含义；无商品锚时只使用一个`single_cycle_factor=min(structural_factor, base_regime_factor)`，禁止结构折价与regime折价重复相乘。

输出`valuation_reference.json`，只回答公允基本面价值，不直接生成最终买点。

### 4 VALUATION_ANCHORS：独立交叉与正式买点
三锚：
- A 基本面价值锚；
- B 同行Forward PE/PB估值锚；
- C 公司自身180日历史成本锚。

A决定价值，B检查倍数是否脱离同行，C校准低风险entry。正式安全/合理区至少需要A+(B或C)。A/B公允中值偏离>45% => `valuation_divergence`，不得强行平均。

买点：
- 普通公司无显式entry multiple时，以公允下沿的82%–90%形成基本面安全边界、90%–100%形成合理边界，再由P10/P25/P35/P60与MA60校准；
- 有显式`low_risk_multiple_range`时直接使用entry multiple，禁止再叠加统一折价；
- 金融以PB/ROE为主并反推PB sanity；
- 周期使用细分政策自己的safe/reasonable-to-fair-floor，当前商品走强不能抬低风险买点。

输出`valuation_anchors.json`，必须包含`fundamental_anchor_range / value_anchor_range / safe_buy_range / reasonable_buy_range / independent_anchor_count / implied PE或PB`。

### 5 FULL_MARKET_PRICE_STRUCTURE
对全部有新鲜180日历史的主板独立扫描，不能只扫描基本面候选。至少识别`base_not_started / transition / breakout / pullback / trend_continuation / overheated / damaged`。Breakout要求价格+成交量+收盘位置确认；Pullback要求20日相对强度不显著弱于市场；创新高不能因无历史压力被判弱。

### 6 PRICE_EXPECTATION_GAP
在正式估值区间形成后判断当前价位置：安全区、合理区、区间上方仍有空间、充分定价、深度折价待复核或估值未完成。再与独立价格结构合成预期差状态。

### 7 OPPORTUNITY_RANKING
每只候选固定输出：股票/代码/当前价、盈利Driver、Forward Bridge、基本面锚、价值锚、安全区、合理区、当前价值位置、价格结构、追高风险、动作、失效条件和blocker。

优先寻找：`盈利改善明确 + Forward Bridge成立 + 正式估值区成立 + 预期差仍在 + 价格刚启势/低风险回踩`。

Shadow可以展示高研究价值但尚缺正式买点的公司；Production必须同时满足公司证据ready、正式买点ready和合格价格状态。Top3允许少于3只或为空。

## 经济常识 Validator
至少拦截：
- 同一风险在EPS、regime、PE/PB和买点区重复折价；
- A/B严重冲突仍生成正式买点；
- 少于2锚生成正式买点；
- 安全区与合理区顺序异常；
- 正式区间无法反推可解释PE/PB；
- 历史价格反向抬高基本面公允价值；
- 右侧因无上方压力淘汰创新高，或因不在基本面池而未扫描。

触发必须`sanity_check_failed / valuation_divergence / review_required`，不得通过分数修复。

## Shadow原则
在历史回放与连续Shadow验证完成前不覆盖V1正式榜单。V1只保留对照，不得把其估值数值、旧买点、共同池右侧边界或T1/T2准入逻辑注入V2。Validator必须case-free，不得用固定股票、固定价格区间或人工历史答案作为PASS条件。
