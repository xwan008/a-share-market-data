# A股低风险研究 V2 编排 Skill

## 目标
执行唯一主链：
`数据健康 → 全市场Coverage → 盈利景气扫描 → 盈利链递归拆解 → 链内公司比较 → 逐公司完整估值 → 价格结构 → Completion Gate → 当前机会`

本Skill不建立周度机会池、候选池、T2池或跨期公司名单。允许跨期保留的只有**行业盈利状态基线**，且只能存在于当前`research_state.json`中，用于降低346个三级节点每日重复全扫的成本；它不是候选答案，也不能直接产生公司或买点。

## 1. DATA HEALTH
确认主板范围、最近完整交易日、最新行情、历史数据和全市场价格结构足够新鲜。机械行情数据陈旧时fail closed。公开证据不足只影响对应节点，不能等同于没有机会。

## 2. 扫描节奏：周度全量 + 日度增量
### 2.1 周度全量盈利普查
扫描基本单元是申万2021 **346个三级节点**。优先锚定周五18:00；若周五没有有效运行，则下一次可用18:00补做。若当前schema没有有效周度基线，则下一次18:00无论星期几都必须先做全量普查。

周度全量必须逐个三级节点真实检查当期公开盈利证据，不允许先挑熟悉行业或预先写一个deep名单。每个三级节点至少形成：
`trend / strength / breadth / confidence / evidence_basis / last_full_scan_date`。

四维含义：
- `trend`: `improving / stable / deteriorating / unconfirmed`，回答盈利方向；
- `strength`: `strong / normal / weak / unknown`，回答变化幅度；
- `breadth`: `broad / selective / divergent / unknown`，回答改善/恶化是否普遍；
- `confidence`: `high / medium / low`，回答证据充分程度。

禁止用统一文案“本期已检查但证据不足”批量填充346个节点并视作全量扫描完成。`unconfirmed`只能是实际查阅后仍无法形成方向判断的结果，必须写清证据缺口。

31个一级和134个二级节点可以由三级子节点聚合形成，但必须可审计；若存在一级/二级直接行业数据，也可作为交叉验证，不能替代三级逐节点检查。

### 2.2 日度18:00增量
有效周度基线不超过7天时，非全量日不重复深扫全部346节点，而是对每个三级节点检查是否出现新的触发证据：
- 新财报、业绩预告、快报；
- 行业统计更新；
- 产品价格/价差明显变化；
- 订单、出货、销量、产量变化；
- 库存、开工率、产能利用率变化；
- 重大公司公告；
- 产业供需、政策或外部事件。

有触发则重新判断四维状态；无触发可沿用周度基线，但必须记录`baseline_date`与`daily_trigger=false`，不得假装当天重新完成深度研究。

上一期state在18:00只允许提供**行业基线**，不得提供公司名单、盈利链答案、估值、机会名单作为本期发现起点。

## 3. COVERAGE LEDGER
运行开始时实例化31/134/346全部节点。每个节点唯一记录：
`code / name / level / parent_code / accounted_for / trend / strength / breadth / confidence / scan_depth / evidence_scope / evidence_basis / last_full_scan_date / baseline_date / daily_trigger / needs_profit_chain_research / profit_chain_resolution`。

`accounted_for=true`要求该节点在当前扫描模式下满足真实完成条件：
- 周度全量：三级节点必须完成真实证据复核；一级/二级必须完成可审计聚合或直接验证；
- 日度增量：必须有有效周度基线，并完成当日trigger check或明确carry forward。

深研触发：
- `trend`为`improving`或`deteriorating`；或
- `breadth`为`selective`或`divergent`。

命中任一条件必须`scan_depth=deep`、`needs_profit_chain_research=true`。`stable + broad`通常可shallow；`unconfirmed`只有在真实证据不足时才可shallow。

## 4. 盈利景气扫描
周度全量时，从346三级节点一个一个判断，不从公司倒推产业。至少关注：收入/利润、毛利率/利润率、产品价格/价差、订单/出货/销量/产量、库存/开工/产能利用率、出口/资本开支及行业特有领先变量。

日度增量时，只对触发节点重新研究并更新基线；没有触发的节点不因为市场价格涨跌改变基本面状态。

## 5. PROFIT CHAIN DECOMPOSITION
所有`needs_profit_chain_research=true`节点都必须进入盈利链研究。继续拆分直到同链公司基本共享：
1. 直接盈利Driver；
2. 领先变量；
3. 利润传导机制；
4. 可比业务暴露。

任一不满足继续按产品/服务、工艺路线、应用场景、客户需求、原料成本、供需/价格/价差拆分。`must_split/continue_split`不得悬空；证据确实不足可用`unconfirmed_with_evidence_gap`收口，但必须说明缺口。

## 6. CHAIN COMPANY COMPARISON + COMPANY RESEARCH
只从本期已确认盈利链出发识别主板公司。若同链有2家及以上真正可比公司，至少比较2家；有更多高可比对象时应继续覆盖，不得找到第一家代表股就停止。

每条重点链输出：`compared_companies / comparison_complete / fundamental_best / current_opportunity_best / opportunity_resolution_complete`。

**所有实际进入横向比较的公司都进入本次`valuation_set`。** 不再只选一只“最代表”的公司去估值，因为进入公司层后数量已经足够有限，可以逐只完成。

## 7. VALUATION：逐公司执行到底
对`valuation_set`每家公司都严格执行valuation Skill完整流程：
`真实盈利 → 盈利类型 → Forward/正常化盈利 → 模型执行 → 合理价格 → 敏感性/不确定性 → Margin of Safety → 安全价格 → 估值位置`。

不能因为缺少卖方一致预期或现成Forward EPS就停止；应利用公开财报、季度趋势、订单/销量/价格/成本/利润率等自行构造审慎的Forward或正常化盈利区间。

`review_required`只能作为经过完整研究尝试后的异常出口，不能作为“还没算完”的替代。重点链若所有公司都只能`review_required`，不能把该链视为估值解析完成并让Completion Gate通过。

## 8. PRICE STRUCTURE
只回答当前时机，不参与内在价值计算。对完成估值解析的公司输出结构状态、关键位、相对强弱、量能和动作。价格变化不得反向修改合理价格或安全价格。

## 9. COMPLETION GATE
Gate前必须满足：
- 31/134/346 exact match；
- 所有节点`accounted_for=true`；
- 周度全量时346三级节点逐一真实证据复核完成；日度增量时有效基线+逐节点trigger check完成；
- 所有deep节点均完成盈利链resolution；
- 无未解决`must_split/continue_split`；
- 重点链有可比主板公司时完成多公司比较；
- `valuation_set`中的每家公司都执行完整估值研究；
- 非`review_required`公司必须有合理价格、安全价格、估值位置；
- 每条重点链至少有1家公司完成非review的完整估值桥，才能把该链的`opportunity_resolution_complete=true`；
- 最终机会公司必须同时有完整估值桥和价格结构判断。

Gate失败：`status=incomplete_research`，不发布新的【当前机会】，也不得用不完整结果覆盖上一份有效完整state。

## 持久化边界
Prompt研究只写`data/research/v2/research_state.json`。周度盈利基线也只能是该state的一部分，不允许建立独立weekly文件。严禁候选池、公司池、机会池、周度Top榜等跨期答案缓存。

## 展示与Shadow
固定章节和公司列读取当前Manifest。当前机会可以为空，但空必须来自完成后的估值与价格判断，而不是因为估值没有继续执行。production gate未开启时使用Manifest当前label。
