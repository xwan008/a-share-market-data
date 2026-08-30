# A股低风险研究 V2 Skills

V2重新对齐最初Prompt的内核：**从正在改善的细分盈利驱动中，寻找未来1–2季度仍有兑现预期、但股价尚未充分定价的公司；最优机会通常是“基本面已拐、价格刚启势”。**

## V2宪法
1. 先找盈利改善，不先找技术形态。
2. 研究单位是细分“盈利驱动链”，不是宽泛行业，也不是T1/T2等级。
3. 召回要宽，淘汰要晚；公司级盈利验证才是真正筛选。
4. 估值用于判断“贵/合理/便宜”，禁止重复折价和虚假精度。
5. 右侧价格结构必须全市场独立扫描，不能受左侧候选池限制。
6. 最优机会优先寻找“盈利改善明确 + 预期差仍大 + 股价刚启势”。
7. Validator首先检查经济合理性，其次才检查程序完整性。

## 核心 Skills（4+1）
1. `orchestrator`：仅负责数据版本、阶段顺序、失败隔离与发布；不参与股票判断。
2. `earnings-driver-scan`：识别制冷剂、MDI、AI服务器、高端PCB、重卡更新等具体盈利驱动。
3. `company-research`：驱动暴露 + 盈利异常 + 周度宽召回，并验证未来1–2季度盈利Bridge。
4. `price-expectation-gap`：估值交叉锚 + 全市场独立价格结构 + 预期差状态。
5. `opportunity-ranking`：输出 LEFT_WATCH / WAIT_BREAKOUT / PRIORITY_INFLECTION / RIGHT_PARTICIPATE / WAIT_PULLBACK / REJECT。

## 不再作为V2业务Skill的旧模块
以下旧目录只属于V1历史实现，不再出现在V2 Manifest：
- industry-scan
- t2-company-recall
- weekly-opportunity-scan
- earnings-validation
- fundamental-valuation
- cycle-valuation
- technical-structure
- final-selection

其中行情历史、周度全市场扫描、公司索引/Registry等**数据资产继续复用**，只是它们不再拥有独立的选股哲学。

## Shadow原则
V2在黄金测试集和历史回放通过之前，只写 `data/research/v2/*`，不得覆盖V1正式产物。V1当前结果保留作对照，但不再作为V2规则设计依据。
