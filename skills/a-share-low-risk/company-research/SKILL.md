# 公司盈利研究 Skill

## 目的
把本期已完成盈利链拆解的节点映射到真正受益的主板公司，验证改善是否来自主营、是否有现金流支持、未来1–2季度是否仍有Forward Bridge。本Skill不发现景气行业，也不维护跨期公司名单。

## 输入
1. 本期`coverage_ledger`中进入deep并完成盈利链resolution的节点；
2. 本期确认的细分盈利链及直接利润变量；
3. Manifest指定的`data/research/company_industry_index.json`，仅用于股票与申万层级映射；
4. 本次实时获取的公司财报、公告、交易所披露、业绩预告/快报、订单/产销/价格/成本等公开经营证据。

公司识别必须从本期盈利链出发，不得先读取上一期公司名单、估值或历史机会名单再反向决定研究对象。

## 链内公司识别
优先研究对盈利链有直接实质业务暴露、Driver可传导至核心产品/业务，且产业地位、纯度、产能、订单、销量或成本优势可能形成主要受益的主板公司。

若同链存在2家及以上经济机制真正可比的主板公司，必须至少横向比较2家；有3家以上高可比对象时优先覆盖更多。不得因为第一家代表股证据完整就停止召回。

若确实只有1家高纯度主板可比公司，必须记录`singleton_reason`。

## 真正受益证据链
每家公司至少建立：
`盈利Driver → 具体业务/产品 → 收入/销量/价格/成本/毛利 → 扣非盈利/现金流 → Forward Bridge`

必查：收入与主营变化、归母净利润、扣非净利润/扣非EPS、可得时同比/环比、毛利率/利润率、经营现金流、一次性收益、与Driver直接相关的订单/出货/产销/价格/成本/业务量、Forward Bridge和失效条件。

## TTM纪律
缺一致预期时可用TTM扣非盈利作为构造Forward/正常化盈利的一个保守锚，但禁止半年报简单乘2。累计口径：`TTM = 上年全年 + 本年累计 - 上年同期累计`。周期/资源公司必须先判断是否需正常化。

## 链内比较完成定义
每条重点链必须输出：
- `compared_companies`：实际比较的主板公司；
- `comparison_complete`；
- `fundamental_best`：只看业务纯度、盈利兑现、现金流与持续性；
- `current_opportunity_best`：加入完整估值和价格结构后的当前最优，可为空；
- `opportunity_resolution_complete`；
- `singleton_reason`：仅单公司链需要。

存在2家及以上可比主板公司时，`comparison_complete=false`不得进入最终机会发布。

## valuation_set
**所有列入`compared_companies`且完成公司证据验证的公司，必须进入本次`valuation_set`。**

不再采用“比较很多公司、最后只估值最代表的一只”的捷径。进入公司层后对象数量已经有限，应逐只完成估值，才能判断：
- fundamental_best是否也是价值最好；
- 是否存在基本面次优但估值更有安全边际的公司；
- 当前机会是否因为价格而发生排序变化。

只有因业务暴露验证失败而被明确淘汰的公司可以不进入valuation_set，并必须写明淘汰原因。

## 每家公司最低输出
`why_now`、`driver_links`与暴露纯度、收入/归母/扣非变化、`margin_quality`、`cashflow_quality`、`one_off_risk`、`forward_bridge`、`evidence_for/evidence_against`、`invalidation_condition`、盈利方向与置信度。

## 持久化
公司研究只写本次`research_state.json`中的`companies`、`chain_comparisons`与`valuation_set`，不写独立公司池或候选文件。
