# 公司盈利研究 Skill

## 目的
把本期已经完成盈利链拆解的节点映射到真正受益的主板公司，验证改善是否来自主营、是否有现金流支持、未来1–2季度是否仍有Forward Bridge。本Skill不发现景气行业，也不维护跨期公司名单。

## 输入
1. 本期`coverage_ledger`中已经进入deep并完成盈利链resolution的节点；
2. 本期确认的细分盈利链及直接利润变量；
3. Manifest指定的`data/research/company_industry_index.json`，仅用于股票与申万层级映射；
4. 本次实时获取的公司财报、公告、交易所披露、业绩预告/快报、订单/产销/价格/成本等公开经营证据。

公司识别必须从本期盈利链出发，不得先读取上一期公司名单或历史机会名单再反向决定研究对象。

## 链内公司识别
优先研究对该盈利链有直接实质业务暴露、Driver可传导至核心产品/业务、且产业地位/纯度/产能/订单/销量/成本优势可能形成主要受益的主板公司。

若同链存在2家及以上经济机制真正可比的主板公司，必须至少横向比较2家；有3家以上高可比对象时优先覆盖更多。不得因为第一家代表股证据完整就停止召回。

若确实只有1家高纯度主板可比公司，必须记录`singleton_reason`，说明为什么不存在第二家真正可比对象。

## 真正受益证据链
每家公司至少建立：
`盈利Driver → 具体业务/产品 → 收入/销量/价格/成本/毛利 → 扣非盈利/现金流 → Forward Bridge`
无法建立时只能观察或复核。

## 必查证据
收入与主营变化；归母净利润；扣非净利润/扣非EPS；可得时的同比/环比；毛利率/利润率；经营现金流；一次性收益；与Driver直接相关的订单/出货/产销/价格/成本/业务量；Forward Bridge和失效条件。

## TTM纪律
缺一致预期时可用TTM扣非盈利作保守参考，禁止半年度简单乘2。累计口径：`TTM = 上年全年 + 本年累计 - 上年同期累计`。周期/资源公司必须先判断是否需正常化。

## 降级条件
扣非盈利为负或明显恶化；高增主要来自一次性收益；现金流与利润长期背离且无法解释；Driver与主营暴露弱；Forward Bridge依赖不可验证假设；出现推翻主营改善的反向证据。

## 链内比较完成定义
每条重点链必须输出：
- `compared_companies`：实际比较的主板公司及核心差异；
- `comparison_complete`：是否完成充分横向比较；
- `fundamental_best`：只看业务纯度、盈利兑现、现金流与持续性谁最好；
- `current_opportunity_best`：加入估值和价格后当前谁最值得关注，可为空；
- `opportunity_resolution_complete`：该链是否已经得到“有当前机会/无当前机会/估值无法可靠确认因而暂不发布”的明确结论；
- `singleton_reason`：仅单公司链需要。

存在2家及以上可比主板公司时，`comparison_complete=false`不得进入最终机会发布。可以继续研究估值草稿，但不能把代表股视作链内最佳结论。

## 每家公司最低输出
`why_now`、`driver_links`与暴露纯度、收入/归母/扣非变化、`margin_quality`、`cashflow_quality`、`one_off_risk`、`forward_bridge`、`evidence_for/evidence_against`、`invalidation_condition`、`earnings_direction`与置信度。

## 进入估值与持久化
完成链内比较后，再让最有代表性的公司进入最终估值解析，优先直接暴露、盈利兑现、产业地位、Bridge持续性和现金流质量。这个集合只存在于本次执行内部，不写独立名单。公司研究只写本次`research_state.json`中的`companies`与`chain_comparisons`。
