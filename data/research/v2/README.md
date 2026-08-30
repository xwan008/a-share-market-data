# A股低风险榜 V2 Shadow

本目录保存V2影子产物，不覆盖V1正式文件。

V2目标：从正在改善的细分盈利驱动中，寻找未来1–2季度仍有兑现预期、但股价尚未充分定价的公司；优先寻找“基本面已拐、价格刚启势”。

## 当前自动闭环
1. `earnings_anomaly_recall.json`：全主板盈利异常宽召回，不使用价格/估值/T1/T2。
2. `earnings_driver_scan.json`：把产业证据转成细分盈利Driver状态；历史T1/T2不控制准入。
3. `company_research.json`：合并Driver暴露、盈利异常、周度深验；形成公司研究骨架、Forward Bridge、review队列和估值队列。
4. `valuation_reference.json`：为估值队列建立一把可审计numeric reference；能用版本化Forward PE/PB自动重建的直接覆盖，周期正常化/政策/共识/市场数据不足则显式review_required。旧V1安全/合理买入区不继承。
5. `full_market_price_structure.json`：全主板独立180日价格结构，不受基本面候选池限制。
6. `price_expectation_gap.json`：只读取V2 valuation reference并结合价格状态，判断盈利改善相对当前股价还剩多少预期差。
7. `opportunity_ranking.json`：输出LEFT_WATCH / WAIT_BREAKOUT / PRIORITY_INFLECTION / RIGHT_PARTICIPATE / WAIT_PULLBACK / REJECT，并分别给出Shadow Top3与Production Top3。

## 证据纪律
- 缺少扣非/主营、现金流、一次性收益、Driver映射或Forward Bridge时，必须显式标记review/blocker，不能静默删除。
- 一把numeric reference只够做Shadow预期差研究；少于两个真正独立V2估值锚不得形成正式买点。
- 风险警示证券仍保留全市场扫描覆盖，但不能进入低风险主榜。
- 周期股缺正常化盈利/商品锚时不能硬套普通Forward PE。
- 分数只能排序，不能修复证据缺口。

生产替换仍需满足Manifest中的Production Gate与连续Shadow验证要求。
