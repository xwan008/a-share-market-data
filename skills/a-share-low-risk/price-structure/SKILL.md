# 价格结构 Skill

## 目的
价格结构只回答：**当前是否从左侧价值区开始出现止跌/转折确认、转折是否有效、哪里失效。**

它不能回答公司值多少钱，不能反向修改 `reasonable_buy_range`，也不能作为“左侧价值买点榜”的硬门。

## 全市场独立扫描
对全部具备新鲜历史数据的主板股票做机械结构扫描；扫描不依赖本期基本面是否研究该公司。历史价格只用于结构、关键位和转折时机判断。

输出文件：`data/research/full_market_price_structure.json`。

## 基础结构状态
`base_not_started`、`transition`、`breakout`、`pullback`、`trend_continuation`、`overheated`、`damaged`、`unavailable`。

这些是市场结构描述，不等同于最终买点类型。

## 必查信息
最近高低点/关键突破位、HH/HL或LH/LL、成交量、收盘位置、相对市场/行业强度、中短期均线/关键成本区、加速或乖离。

## 结构输出
对进入本期估值集合的公司必须额外输出：
- `structure_type`；
- `structure_entry_range`：仅由支撑、突破确认位、回踩承接区、量价和乖离推导，可为空；
- `structure_invalidation`；
- `key_level`；
- `relative_strength`；
- `volume_confirmation`；
- `chase_risk`；
- `timing_action`；
- `left_turn_confirmed`；
- `left_turn_basis`。

`structure_entry_range`不能参考合理价值、Safe Price Ceiling 或 `reasonable_buy_range` 来人为调整；它必须独立产生。

## 左侧拐点确认
“左侧拐点”不是普通右侧趋势延续。只有公司当前价格已经处于估值层给出的 `reasonable_buy_range` 内，才评估是否形成左侧拐点。

`left_turn_confirmed=true` 至少需要满足以下转折证据中的有效组合：
- 关键支撑/价值区内低点得到承接，停止连续创新低；
- 出现更高低点（HL）或等价的底部结构改善；
- 重新站回关键位/短期均线，并有收盘确认；
- 小级别突破或底部突破有成交量、收盘位置确认；
- 相对强度不再继续显著恶化。

同时：
- `chase_risk=high` 不能判为左侧拐点；
- `damaged / overheated / unavailable` 不能判为 `left_turn_confirmed=true`；
- 单纯处于既有 `trend_continuation`，但没有“从左侧价值区转折”的证据，不得冒充左侧拐点；
- 当前价格已经离开 `reasonable_buy_range`，即使右侧结构很强，也不能进入左侧拐点买点榜。

## 与两个榜单的关系
### 左侧价值买点榜
由估值层决定：

`left_value_buyable_now = current_price ∈ reasonable_buy_range`

价格结构**不参与硬否决**。即使当前仍是下降/过渡结构，只要基本面与估值仍有效，就可以进入左侧价值买点榜，并明确标注结构风险和失效条件。

### 左侧拐点买点榜
必须同时满足：

`left_turn_buyable_now = left_value_buyable_now AND left_turn_confirmed`

因此：

`左侧拐点买点榜 ⊂ 左侧价值买点榜`

价格结构只负责把“已经便宜”的股票进一步筛出“开始转折”的子集。

## 数据日期硬门
机械结构文件的 `reference_trade_date` 必须与 Data Gate 的 expected completed A-share trade date 一致。日期不一致视为 stale structure data，禁止正式发布新的左侧拐点判断。

## 持久化
只持久化全市场机械结构：`data/research/full_market_price_structure.json`。

本轮公司的结构判断、左侧价值买点、左侧拐点买点、Near-miss 都只存在于当前执行上下文，不写 `research_state.json`，不形成跨期候选池。
