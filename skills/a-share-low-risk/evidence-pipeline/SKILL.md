# 行业证据生产线 Skill

## 目标
把正式榜单中的“临场开放式行业搜索”前移为可重复、可审计的 Evidence Layer：

`市场数据完成 → 31行业 leading-anchor 采集 → 全 shard 盈利证据 → Evidence Gate → production bundle → ChatGPT Decision Layer`

当前仍为 **shadow rollout**。在真实数据连续验证并达到 strict_pass 前，不得替换旧正式生产。

## 1. 职责边界

### GitHub Actions / Evidence Layer
负责：
- 固定申万2021一级行业 31/31 全集；
- 按 `config/industry_leading_anchor_sources.json` 采集每个一级行业的第一锚；
- 本地完整解析 `data/shards/*.json`，形成财务/核心盈利 breadth；
- 记录来源、参考日期、更新频率、freshness 和采集错误；
- 生成 `industry_leading_anchors.json / industry_evidence.json / evidence_gate.json`；
- 发布与单一 commit SHA 绑定的 `a-share-production-bundle`。

### ChatGPT / Decision Layer
负责：
- 基于已准备证据判断 `improving / neutral / deteriorating / uncertain`；
- 解释领先变量向盈利的传导；
- 对冲突证据做有限补查；
- 三级准入、公司 Gates、估值与榜单。

Evidence Layer 不得机械输出行业景气结论。

## 2. Leading-anchor 规则

31 个一级行业必须全部在 source matrix 中有至少一个候选锚。采集层使用通用 adapter，而不是 31 套独立爬虫：
- `futures_basket`：商品/原料/价差相关行业；
- `akshare_table`：公开宏观、协会和行业表；
- `nbs_path`：国家统计局月度产业数据；
- `cpca_monthly`：乘用车销量；
- `movie_monthly`：电影票房；
- `health_commodity`：复用仓库已有商品锚。

候选按配置顺序回退。优先选择 fresh 且非 secondary 的锚；只有强锚不可用时才允许 secondary proxy 成为临时 primary，并必须保留 proxy_strength。

严禁：
- 用股票价格、行业指数涨跌、K线或技术结构作为产业景气第一锚；
- 用财报盈利 breadth 冒充领先变量；
- 为凑 31/31 把失败或 stale 数据伪装 fresh。

## 3. 固定证据槽位
每个一级行业至少包含：
- `leading_anchor`：订单、销量、价格/价差、库存、产量、出货、利用率、投资/招投标等适配第一锚；
- `earnings_confirmation`：最新核心盈利兑现；
- `negative_evidence`：反向盈利/产业证据。

每条证据必须带 `source / reference_date / frequency / freshness.status`。月频、周频、季频按自身发布周期判断 freshness，不能要求每天都有新值。

## 4. 全 shard 财务宽度层
每轮完整读取本地 `data/shards/*.json`，只使用 shard 自带 `industry_mapping_status / sw_level3_code` 向上归并一级行业，形成 core improving/deteriorating breadth、收入 breadth 与 headline profit 交叉证据。

必须记录 `shard_file_count / actual_shard_content_read_count / stock_records_read`，并要求内容读取数等于文件数。该层回答“盈利是否兑现”，不能代替 leading-anchor。

## 5. Evidence Gate
Shadow shape 至少要求：
- 31/31 一级行业 accounted；
- leading-anchor source collection 31/31 accounted；
- 全 shard 财务 breadth 完整解析；
- 证据 schema 与当前 builder 一致。

Strict 额外要求：
- 31/31 行业均有 fresh leading_anchor；
- 31/31 行业 earnings_confirmation 和 negative_evidence 均有效；
- `complete=31 / partial=0 / missing=0`；
- `strict_pass=true`。

## 6. Shadow → Strict
只有在真实 Actions 数据上连续多个交易日满足 strict 条件、主要数据源失败回退行为验证完成、production bundle 同 SHA 校验稳定后，才能把 orchestrator 切换为 production bundle 消费模式并瘦身正式 Prompt。

在切换前，shadow 产物只用于验证，不得冒充正式榜单研究已经完成。
