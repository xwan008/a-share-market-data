# A股低风险榜 V2 Shadow

本目录只保存V2影子产物，不覆盖V1正式文件。

V2核心目标：从正在改善的细分盈利驱动中，寻找未来1–2季度仍有兑现预期、但股价尚未充分定价的公司；优先寻找“基本面已拐、价格刚启势”。

机械扫描产物：
- `earnings_anomaly_recall.json`：全主板盈利异常宽召回，不使用价格/估值/T1/T2。
- `full_market_price_structure.json`：全主板独立180日价格结构，不受基本面候选池限制。

需要研究/LLM生成的V2产物：
- `earnings_driver_scan.json`
- `company_research.json`
- `price_expectation_gap.json`
- `opportunity_ranking.json`

生产替换条件：黄金测试集通过 + 历史回放通过 + 至少3个交易日shadow观察。
