# A股低风险榜 V2 Shadow

本目录保存V2影子产物，不覆盖V1正式文件。

V2目标：从正在改善的细分盈利驱动中，寻找未来1–2季度仍有兑现预期、但股价尚未充分定价的公司；优先寻找“基本面已拐、价格刚启势”。

## 当前自动闭环
1. `earnings_anomaly_recall.json`：全主板盈利异常宽召回，不使用价格/估值/T1/T2。
2. `earnings_driver_scan.json`：把产业证据转成细分盈利Driver状态；历史T1/T2不控制准入。
3. `company_research.json`：合并Driver暴露、盈利异常、周度深验；形成公司研究骨架、Forward Bridge、review队列和估值队列。
4. `valuation_reference.json`：V2独立生成第一基本面估值锚，不读取V1估值数值。普通公司使用Forward PE，金融使用Forward ROE/PB，周期股使用正常化盈利。
5. `valuation_anchors.json`：形成三锚框架：A基本面价值锚、B同行Forward PE/PB估值锚、C公司自身180日历史成本锚；完成锚冲突检查，并生成正式`safe_buy_range`与`reasonable_buy_range`。
6. `full_market_price_structure.json`：全主板独立180日价格结构，不受基本面候选池限制。
7. `price_expectation_gap.json`：读取正式买入区间，判断当前价位于安全区、合理区、区间上方、已充分定价或估值待复核，再与价格结构合成预期差状态。
8. `opportunity_ranking.json`：固定输出基本面锚、价值锚、安全买入区、合理买入区、当前价格位置和结构状态，并分别形成Shadow Top3与Production Top3。

## 估值与买点纪律
- 公允价值与买入区间分层：先回答“值多少钱”，再回答“什么价格值得承担风险”。
- V2估值不得读取V1 numeric result，避免旧共同池、旧折价和旧买点重新渗透。
- 正式买点至少需要A基本面锚 + B同行锚或C历史成本锚。
- A与B严重冲突时输出`valuation_divergence`，不平均、不强行生成区间。
- 有显式`low_risk_multiple_range`的公司直接使用该entry multiple，不再叠加统一0.8/0.9折价。
- 周期股必须先正常化盈利；无统一商品锚时只允许一个保守周期因子，禁止structural haircut与regime haircut重复相乘。
- 历史价格只校准entry，不能因为过去股价高而抬高基本面公允价值。
- 正式安全/合理区必须反推隐含PE/PB，保证数值可解释。

## 证据纪律
- 缺少扣非/主营、现金流、一次性收益、Driver映射或Forward Bridge时，必须显式标记review/blocker，不能静默删除。
- 风险警示证券仍保留全市场扫描覆盖，但不能进入低风险主榜。
- 一致预期或关键市场数据不足时允许没有正式买点；不使用H1简单年化制造伪精度。
- 分数只能排序，不能修复证据缺口。

生产替换仍需满足Manifest中的Production Gate与连续Shadow验证要求。
