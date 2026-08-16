# A-share Market Data Bridge

A lightweight GitHub Actions data bridge for the downstream ChatGPT A-share stock-screening task.

## What it does

- Pulls Shanghai/Shenzhen main-board current quotes with **exchange-aware symbol filtering**.
- Uses Sina/easyquotation as the primary real-time source and Tencent/AKShare as verification/fallback sources.
- Publishes per-stock current-price confidence.
- Keeps a **bounded rolling history of at most 65 completed sessions per stock**.
- Uses Tencent forward-adjusted (`qfq`) daily K-lines as the periodic historical baseline.
- Detects likely corporate-action adjustment drift from `historical previous close` vs the current session's `prev_close` and repairs only affected stocks immediately.
- Precomputes compact **5d / 20d / 60d** context so ChatGPT does not need to load 60 raw candles.
- Publishes history-quality labels and warnings.
- Generates small quote shards for candidate-only reads.

## Main-board universe

Included:

- Shanghai: `600`, `601`, `603`, `605`
- Shenzhen: `000`, `001`, `002`, `003`

Excluded: ChiNext (`300/301`), STAR (`688/689`), BSE and index symbols. For Sina/Tencent, exchange prefix and stock-code prefix are checked together so symbols such as `sh000001` cannot collide with Shenzhen stock `000001`.

## Files consumed by ChatGPT

### `data/health.json`

Always read this first. Key fields:

- `generated_at`, `trade_date`, `market_status`
- source status/errors
- current-price `high / medium / invalid` coverage
- `shard_key_length`
- rolling-history window and 5d/20d/60d coverage
- history-confidence coverage
- latest `corporate_action_repair` status
- sample quotes and trend structures

### `data/shards/<dynamic-key>.json`

Read `health.shard_key_length = N`, take the first `N` digits of a candidate code, and read only that shard.

Each stock contains current quote fields plus a compact trend object. When history is sufficient, the trend includes:

- `history_confidence`, `history_warnings`
- `history_basis`, `last_full_refresh`
- recent 5-session closes and 5d change
- 20d high/low and 20d change
- `structure_60d`:
  - 60d high/low and change
  - `ma20`, `ma60`
  - current 60d range position
  - swing `support_zones`
  - swing `resistance_zones`
  - `structure_evolution` with confirmed pivot sequence and HH/HL/LH/LL structure state
  - repeated-close `dense_price_zones`
  - approximate volume-at-price `volume_profile_zones`

`structure_evolution` uses the same completed-session 60d OHLC history, but preserves the time ordering of confirmed swing pivots instead of clustering them only into price zones. Its main fields are:

- `trend_state`: `bullish`, `bearish`, `transition`, or `insufficient`
- `break_state`: whether the current structure is intact, under threat, or has a confirmed structural break
- `latest_high`, `latest_low`: latest confirmed swing pivots and their HH/LH or HL/LL labels
- `invalidation`: the latest confirmed structural level whose breach threatens the active trend
- `pivots`: the latest confirmed alternating high/low sequence
- `confirmation_lag_sessions`: currently `2`; a pivot needs two completed sessions on each side before it becomes confirmed

The most recent unconfirmed bars may therefore threaten an existing structure without being promoted immediately to a confirmed reversal. Daily candles that are simultaneously a local high and low are omitted from pivot sequencing because daily OHLC does not reveal their intraday ordering.

`volume_profile_zones` is derived from daily typical price and daily volume (`daily_typical_price_approx`). Tencent historical K-line volume is normalized from board lots to **shares**, matching live quote volume, before volume shares are compared. It is deliberately approximate rather than tick-level volume profile, so downstream logic should use it as corroborating structural evidence, not as a precise cost-distribution claim.

The 60d fields are a structural summary, not an instruction to mechanically buy at the nearest support.

### `data/history_shards/<first-four-digits>.json`

Internal bounded history store. Each stock keeps at most 65 completed daily OHLCV rows.

Morning/intraday snapshots never enter this daily history. Post-close snapshots are merged by trading date, duplicates overwrite instead of append, and only the newest 65 sessions are retained.

The store therefore has a fixed upper bound and does not grow with repository age.

### `data/repair_status.json`

Records the latest targeted corporate-action check and repair result: detected mismatches, repaired stocks, failures and sample mismatch details.

## History quality

History is labelled:

- `high`: at least 60 valid points, OHLC is structurally consistent, no material date/freshness warning, and the qfq baseline is recent.
- `medium`: still usable but has fewer than 60 points or a freshness/gap warning.
- `invalid`: too little usable history or structural/date errors.

During intraday runs, completed history is expected to end **before** the current trading date. This prevents the current morning/afternoon partial candle from being mistaken for a completed daily bar while still allowing the 12:00 screener to retain high history confidence when the previous completed session is fresh.

## Corporate-action repair

After each fresh quote pull, `repair_corporate_actions.py` compares the stored previous completed qfq close with the current session's exchange reference `prev_close`.

A material mismatch (with both percentage and absolute thresholds to ignore normal rounding noise) is treated as a likely dividend/split/rights/adjustment event. Only affected stocks are re-fetched from Tencent qfq history.

During intraday repair the current trading date is explicitly excluded, so an unfinished current-day K-line can never enter completed history. After the close, the normal history append writes the final daily bar.

The weekly full qfq refresh remains as a second safety net even when no targeted repair fires.

## Why 5d / 20d / 60d have different jobs

- **5d**: short-term emotion and acceleration — chase/not chase, pullback or momentum.
- **20d**: recent position — roughly high/mid/low in the last month and whether a pullback has occurred.
- **60d**: medium-term structure — MA20/MA60, repeated price zones, approximate high-volume price zones, swing support/resistance, confirmed HH/HL/LH/LL evolution and broader platform context.

Core buy zones should combine 60d structure with earnings, valuation and industry conditions. A rising current price alone must not move the core buy zone upward.

## GitHub Actions

### Normal market update

Weekdays, Beijing time:

- 11:37
- 11:52
- 15:12
- 15:27

Each run pulls/validates current quotes, runs the targeted corporate-action repair check, rebuilds trend/structure summaries and republishes compact bridge files.

Morning runs do not append the current intraday candle. Post-close runs merge the completed session into the 65-session history.

### Full qfq history refresh

`Backfill A-share rolling history` can be run manually and also runs weekly on Saturday at 10:20 Beijing time.

It refreshes the latest 65 sessions from Tencent qfq K-lines, prunes records outside the current valid stock universe, rebuilds trend/structure summaries and republishes bridge shards.

## Downstream lookup flow

1. Read `data/health.json` and validate freshness/trade date/coverage/repair status.
2. Build the fundamental/industry candidate list first.
3. Read only each candidate's small quote shard.
4. Use `confidence=high/medium` current price directly; web price fallback only for invalid/missing records.
5. Use 5d/20d/60d fields only when the relevant points and `history_confidence` are adequate.
6. Use web research primarily for earnings, catalysts, valuation and market regime rather than repeated price scraping.
7. Define a **value anchor** independently from earnings/valuation, define a **structure anchor** independently from 60d structure, and only treat their overlap as the preferred core-buy region. If there is no credible overlap, wait rather than forcing a buy zone.

At 12:00, combine the latest morning price with completed-session history; never treat the morning snapshot as a completed daily candle.

## Reliability notes

The upstream quote/K-line endpoints are public and unofficial and can be throttled or changed. The bridge therefore uses multi-source current-price validation, explicit history-quality labels, targeted corporate-action repair, a bounded local history, weekly qfq refresh and downstream fallback rather than assuming any single provider is permanently reliable.
