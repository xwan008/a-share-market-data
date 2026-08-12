# A-share Market Data Bridge

A lightweight, serverless A-share market-data bridge for the downstream ChatGPT stock-screening task.

## What it does

- Pulls the A-share main-board snapshot with Sina/easyquotation as a primary quote source.
- Uses additional public sources such as Tencent and AKShare/Eastmoney for verification/fallback when available.
- Publishes a confidence level for every current price.
- Saves post-close history and gradually builds 5-day/20-day trend context.
- Generates small four-digit-code shards so ChatGPT never needs to load the full-market JSON just to verify one candidate.

## Main-board universe

Included:

- Shanghai: `600`, `601`, `603`, `605`
- Shenzhen: `000`, `001`, `002`, `003`

Excluded: ChiNext (`300/301`), STAR (`688/689`) and BSE.

## Confidence rules

- `high`: current price has strong multi-source agreement/verification.
- `medium`: one valid fresh source is available; price is usable but should be labelled single-source/medium confidence downstream.
- `invalid`: price is missing/non-positive, stale, or available sources materially conflict.

The downstream task should accept `high` and `medium`. Only `invalid` or missing records should fall back to public-web quote validation.

## Files consumed by ChatGPT

### 1. `data/health.json`

Always read this first. It provides:

- `generated_at`
- `trade_date`
- `market_status`
- source status/errors
- high/medium/invalid coverage
- `shard_key_length`
- sample quotes used as a pipeline smoke test

If this file is stale or the trade date is wrong for the requested run, do not trust the bridge blindly; use the existing public-web fallback.

### 2. `data/shards/<first-four-digits>.json`

Current shard key length is **4**.

Examples:

- `002475` (立讯精密) → `data/shards/0024.json`
- `601138` (工业富联) → `data/shards/6011.json`
- `601899` (紫金矿业) → `data/shards/6018.json`

Each stock record contains the current quote anchor and, as history accumulates, its trend summary:

```json
{
  "price": 57.35,
  "prev_close": 55.63,
  "open": 55.68,
  "high": 57.58,
  "low": 55.30,
  "price_time": "2026-08-12T15:35:15+08:00",
  "confidence": "high",
  "primary_source": "sina",
  "source_prices": {
    "sina": 57.35,
    "tencent": 57.35,
    "akshare": null
  },
  "trend": {
    "points": 1,
    "last_date": "2026-08-12",
    "last_close": 57.35,
    "high_20d": 57.58,
    "low_20d": 55.30,
    "close_change_5d_pct": null,
    "close_change_20d_pct": null
  }
}
```

Do not interpret `high_20d`, `low_20d`, `close_change_5d_pct`, or `close_change_20d_pct` as genuine 5/20-session statistics until `trend.points` is large enough:

- `points >= 5`: use 5-session fields.
- `points >= 20`: use 20-session fields.
- below those thresholds: supplement technical trend with dated public historical pages/K-line sources.

### 3. `data/latest.json`

Full-market source snapshot retained for storage/debugging. It is intentionally **not** the preferred ChatGPT read path because it is large.

### 4. `data/trend_summary.json`

Full-market accumulated trend file retained for processing/debugging. Per-stock trend data is also embedded in the small shard files for downstream reads.

## GitHub Actions schedule

The workflow runs on weekdays at Beijing time:

- 11:37
- 11:52
- 15:12
- 15:27

Duplicate runs provide a retry path for temporary upstream/GitHub delays. The workflow can also be run manually.

## Downstream lookup flow

1. Read `data/health.json` and validate freshness/trade date.
2. Take the first four digits of the candidate stock code.
3. Read only that shard file.
4. Use `high` or `medium` current price directly according to its confidence label.
5. For missing/invalid records, use the existing Tencent → Eastmoney → dual dated-page fallback.
6. Use embedded trend only when enough sessions have accumulated; otherwise keep using dated historical pages for 5d/20d structure.

## Local checks

```bash
python -m py_compile scripts/*.py tests/*.py
python -m pytest -q
```

## Reliability notes

The upstream quote sources are public, unofficial market endpoints and can be throttled or changed. The bridge therefore uses multiple sources, publishes confidence instead of hiding failures, keeps local history, and retains a downstream web fallback.