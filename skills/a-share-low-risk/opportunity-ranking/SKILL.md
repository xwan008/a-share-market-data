# 最终机会排序 Skill

## 目的
把公司盈利研究、预期差和价格状态整合成可执行机会榜。最终排序不再机械要求“LEFT ∩ RIGHT”才有资格展示，而是明确区分左侧关注、刚启势、趋势参与、过热等待等状态；其中“基本面已拐 + 价格刚启势”是最高优先级。

## 输入
- `data/research/v2/company_research.json`
- `data/research/v2/price_expectation_gap.json`
- `data/research/v2/full_market_price_structure.json`
- 数据健康与sanity validator状态

## 核心排序维度
1. `earnings_quality`：主营/扣非盈利兑现、现金流、一次性收益风险。
2. `forward_visibility`：未来1–2季度Bridge的可验证性。
3. `expectation_gap`：盈利改善相对股价定价是否仍有空间。
4. `price_timing`：未启动 / 初启 / 趋势确认 / 回踩 / 过热 / 破坏。
5. `valuation_sanity`：估值是否合理、是否存在模型分歧。

分数只能用于同状态候选排序，不能取代资格解释。每只股票必须有自然语言理由。

## 机会状态
- `LEFT_WATCH`：盈利改善明确、预期差较大，但价格尚未确认；适合观察而非追买。
- `WAIT_BREAKOUT`：基本面成立、价格临近关键平台，等待确认突破。
- `PRIORITY_INFLECTION`：盈利改善明确 + 预期差仍大 + 股价刚启势/低风险突破；V2最核心机会。
- `RIGHT_PARTICIPATE`：趋势确认且预期差仍有剩余，追高风险可接受。
- `WAIT_PULLBACK`：趋势很强但已过热/乖离过大。
- `REJECT`：盈利逻辑失效、预期已充分交易、结构破坏或估值sanity失败。

## 产业链集中度
最终榜允许同一盈利驱动链出现多家公司，但避免霸榜：
- 研究池估值前保留3–5家；
- 最终主榜同一driver原则上展示不超过2家；
- 如果存在板块共振，可在“同行共振”字段展示额外公司，但不挤占主榜。

## Top3
Top3优先从`PRIORITY_INFLECTION`中产生，其次才考虑`RIGHT_PARTICIPATE`或高质量`LEFT_WATCH`。

禁止：
- 为凑3只降低标准；
- 因纯技术强势忽略盈利质量；
- 因纯低估忽略盈利仍在恶化；
- 把估值sanity失败的股票放进Top3。

## 每只输出固定回答
- 为什么进入研究池；
- 哪条盈利驱动正在改善；
- 未来1–2季度为什么可能继续；
- 股价已经反映多少；
- 当前价格状态是什么；
- 现在最合理动作是什么；
- 失效条件是什么。

## 输出
V2 shadow期写入：`data/research/v2/opportunity_ranking.json`。

在通用经济/结构不变量、历史回放和连续影子运行未完成验证前，所有结果必须标记 `mode=shadow`，不得覆盖V1正式榜单。测试与Validator必须case-free，不得使用固定股票、固定价格区间或历史人工结论作为PASS/FAIL条件。
