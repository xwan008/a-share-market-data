# A股低风险研究 Skills

这是正式生产研究链，不使用 shadow，也不通过递增数字 schema 管理研究规则。

唯一主链：

`Data Gate → 每次全市场Prompt轻召回 → taxonomy映射 → 三级行业周度全量/日度增量 → 公司准入 → 盈利链 → Company Mapping Gate → 公司全集轻筛 → survivor比较/去重 → 估值 → 独立价格结构 → 买点交集 → Near-miss → Completion Gate → 正式发布`

## 状态边界
跨期只允许保留一类基本面研究状态：
- `data/research/industry_state.json`：紧凑的三级行业盈利基线，是唯一跨期基本面记忆。

机械价格结构独立保存为 `data/research/full_market_price_structure.json`，它属于市场机械数据，不属于上一轮研究结果。

**不持久化上一轮正式榜单。** 公司、盈利链关系、估值、当前买点、Near-miss 和最终榜单均只存在于本轮执行上下文；下一轮必须重新生成，禁止读取任何上一轮研究结果来恢复、续跑、缩小搜索范围或直接发布。

禁止周度机会池、候选池、T2池、独立公司池、估值缓存和 `research_state.json`。

## 发现与刷新不是一回事
Prompt景气发现**每次运行都从全市场做轻召回**，不能被上一期方向限制。

周度/日度差异只作用于三级行业深度盈利研究：周度重建/重验当前发现方向下的三级行业基线；日度只对有新增或变化证据的三级节点做深度刷新。

## 公司准入
允许进入公司层的三级状态：
- `trend=improving`；
- `trend=stable AND breadth=divergent`。

后者只扩大研究资格，不降低估值、安全边际、价格结构或买点门槛。

## 证据
Manifest `authoritative_data` 是仓库机械数据白名单，不是全部证据来源。正式研究必须使用当前公开基本面证据：公司公告/财报、交易所、官方统计、行业协会/产业数据、订单/产销、产品价格/价差、库存/开工/利用率等。

## 四个 Skill
- `orchestrator`：总流程、Data Gate、三级状态、Company Mapping Gate、Completion Gate、发布；
- `company-research`：盈利链公司全集召回、轻筛、横向比较、去重；
- `valuation`：核心盈利、三级同行相对估值、安全价；
- `price-structure`：独立技术结构、入场区间、失效条件。

规则契约由 `config/research_runtime_policy.json` 与 `config/research_pipeline_manifest.json` 共同定义；修改规则时应同步更新相关Skill与契约测试，而不是增加 schema 序号。
