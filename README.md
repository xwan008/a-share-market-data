# A-share Market Data Bridge

A lightweight, serverless A-share market-data bridge for the downstream ChatGPT stock-screening task.

## What it does

- Pulls A-share main-board current quotes with Sina/easyquotation as a primary source.
- Uses Tencent and AKShare/Eastmoney as verification/fallback sources when available.
- Publishes a confidence level for every current-price anchor.
- Keeps a **bounded rolling history of at most 25 completed sessions per stock**.
- Precomputes 5-session and 20-session trend context from completed daily bars only.
- Generates small quote shards so ChatGPT does not need to load the full-market JSON for a candidate.

## Main-board universe

Included:

- Shanghai: `600`, `601`, `603`, `605`
- Shenzhen: `000`, `001`, `002`, `003`

Excluded: ChiNext (`300/301`), STAR (`688/689`) and BSE.

## Current-price confidence

- `high`: current price has strong multi-source agreement/verification.
- `medium`: one valid fresh source is available; price is usable but should be labelled single-source/medium confidence downstream.
- `invalid`: price is missing/non-positive, stale, or available sources materially conflict.

The downstream task accepts `high` and `medium`. Only `invalid` or missing records fall back to public-web quote validation.

## Files consumed by ChatGPT

### 1. `data/health.json`

Always read this first. It provides:

- `generated_at`
- `trade_date`
- `market_status`
- source status/errors
- high/medium/invalid price coverage
- `shard_key_length`
- rolling-history configuration and 5d/20d coverage
- sample quotes used as pipeline smoke tests

The quote shard length is deliberately discoverable rather than hard-coded. Read `shard_key_length = N`, then use the first `N` digits of a stock code.

At the time of writing the bridge uses five-digit quote shards, for example:

- `002475` → `data/shards/00247.json`
- `601138` → `data/shards/60113.json`
- `601899` → `data/shards/60189.json`

If the shard layout changes later, downstream code should continue to work by following `health.json`.

### 2. `data/shards/<dynamic-key>.json`

Each stock record contains its current quote anchor plus a trend summary:

```json
{
  "price": 57.35,
  "prev_close": 55.63,
  "open": 55.68,
  "high": 57.58,
  "low": 55.30,
  "price_time": "2026-08-12T15:35:15+08:00",
  "confidence": "high",
  "source_prices": {
    "sina": 57.35,
    "tencent": 57.35,
    "akshare": null
  },
  "trend": {
    "points": 20,
    "last_date": "2026-08-12",
    "last_close": 57.35,
    "high_20d": 64.201,
    "low_20d": 52.65,
    "close_change_5d_pct": 2.59,
    "close_change_20d_pct": -6.66,
    "last5": [
      {"date": "2026-08-06", "close": 55.90},
      {"date": "2026-08-07", "close": 56.99},
      {"date": "2026-08-10", "close": 55.79},
      {"date": "2026-08-11", "close": 55.63},
      {"date": "2026-08-12", "close": 57.35}
    ]
  }
}
```

Use 5-session fields only when `trend.points >= 5`, and 20-session fields only when `trend.points >= 20`.

### 3. `data/history_shards/<first-four-digits>.json`

This is the bounded internal history store. It uses four-digit shards independently of the quote-shard layout.

Each stock contains a `history` array with at most 25 dated OHLCV rows. Only snapshots with `market_status = closed` are allowed into this store. On every closed-session update:

1. the final daily session is merged by trading date;
2. a duplicate trading date overwrites the previous row rather than being appended twice;
3. rows are sorted by date;
4. only the newest 25 are retained.

Therefore the working history does **not** grow with repository age. Running the project for five years still leaves at most 25 stored completed sessions per stock.

Morning/intraday snapshots never enter rolling daily history. They update current quote files only.

### 4. `data/latest.json`

Full-market current snapshot retained for processing/debugging. It is intentionally not the preferred ChatGPT read path because it is large.

### 5. `data/trend_summary.json`

Full-market derived trend output. The relevant per-stock trend is embedded in the small quote shard, so normal downstream reads do not need this large file.

### 6. `data/backfill_status.json`

Records the latest manual historical backfill result and source coverage.

## Historical bootstrap

The repository does not need to wait 20 future trading days before 5d/20d analysis becomes useful.

`Backfill A-share rolling history` is a manual GitHub Actions workflow that requests recent Tencent forward-adjusted daily K-lines and fills the rolling 25-session history store. Individual suspended/new stocks may fail without invalidating the batch; a broad source failure causes the workflow to fail.

After the initial bootstrap, normal post-close updates maintain the rolling window automatically. The old one-file-per-day `data/history/YYYY-MM-DD.json` model is no longer used.

## GitHub Actions

### Normal update

Runs on weekdays at Beijing time:

- 11:37
- 11:52
- 15:12
- 15:27

Every run refreshes and validates current quotes and rebuilds compact ChatGPT quote shards.

The two morning runs are **current-price snapshots only**: rolling daily history is not changed.

The two post-close runs additionally:

1. merge the completed daily bar into bounded history;
2. rebuild 5d/20d trend summaries;
3. publish updated history coverage in `health.json`.

Duplicate post-close runs are safe because same-day history is deduplicated by trading date. The workflow runs tests before market-data processing.

### Historical backfill

The backfill workflow is manual (`workflow_dispatch`) and should normally only be needed for initial bootstrap or history repair.

## Downstream lookup flow

1. Read `data/health.json` and validate freshness/trade date.
2. Read `health.shard_key_length = N`.
3. Take the first `N` digits of the candidate stock code and read only that quote shard.
4. Use `high` or `medium` current price according to its confidence label.
5. Use embedded 5d/20d trend when `points` is sufficient.
6. For missing/invalid current price or insufficient history, use dated public-web fallback only for the missing field.

At 12:00, combine the latest morning price snapshot with trend data calculated from completed sessions. Intraday prices are never mistaken for a completed daily K-line.

## Reliability notes

The upstream market-data endpoints are public and unofficial, so they may be throttled or changed. The bridge therefore uses multiple current-price sources, bounded local history, explicit confidence/coverage fields, and a downstream web fallback rather than assuming any one provider is permanently reliable.
