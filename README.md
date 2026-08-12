# A-share Market Data Bridge

A lightweight, serverless A-share market-data bridge for a downstream ChatGPT stock-screening task.

## What it does

- Pulls a full A-share main-board snapshot with **Sina/easyquotation** as the primary source.
- Uses **AKShare/Eastmoney** as a secondary source when available.
- Cross-checks current price when both sources are available.
- Publishes `data/latest.json` with price, previous close, quote time, source status, and confidence.
- Saves a compact post-close snapshot into `data/history/YYYY-MM-DD.json`.
- Builds `data/trend_summary.json` from the latest 20 stored sessions so the downstream task can judge 5-day/20-day direction without scraping 20 historical web pages.

## Confidence rules

- `high`: primary + secondary source both available and current prices differ by no more than 0.2%.
- `medium`: one valid source is available; price is still usable, but downstream analysis should label it as single-source.
- `invalid`: price is missing/non-positive or two available sources conflict by more than 0.2%.

The downstream ChatGPT task should accept `high` and `medium`, and use its public-web fallback only for `invalid`/missing records.

## Main-board universe

Included prefixes:

- Shanghai: `600`, `601`, `603`, `605`
- Shenzhen: `000`, `001`, `002`, `003`

This intentionally excludes ChiNext (`300/301`), STAR (`688/689`) and BSE.

## GitHub Actions schedule

The workflow runs on weekdays at Beijing time:

- 11:37
- 11:52
- 15:12
- 15:27

The duplicate runs provide a simple retry path for temporary upstream/GitHub delays. The workflow can also be run manually with **Run workflow**.

## Files consumed by ChatGPT

### `data/latest.json`

Use this as the primary current-price anchor.

Important fields:

```json
{
  "generated_at": "2026-08-12T15:12:31+08:00",
  "trade_date": "2026-08-12",
  "market_status": "closed",
  "stocks": {
    "002475": {
      "name": "立讯精密",
      "price": 57.21,
      "prev_close": 55.63,
      "price_time": "2026-08-12T15:00:00+08:00",
      "confidence": "high",
      "source_prices": {
        "sina": 57.21,
        "akshare": 57.20
      }
    }
  }
}
```

### `data/trend_summary.json`

After enough post-close snapshots accumulate, this provides:

- last 5 closes
- approximate 5-day change
- 20-session high/low
- approximate 20-day direction

During the first 20 trading days, the ChatGPT task can continue using dated public historical pages for 5d/20d trend context.

## Setup

1. Create a GitHub repository (public is simplest if ChatGPT must read raw JSON without authentication).
2. Upload this project to the default branch.
3. Open **Actions → Update A-share market data → Run workflow** once manually.
4. Confirm `data/latest.json` contains current data.
5. Use the raw GitHub URLs for `data/latest.json` and `data/trend_summary.json` as the first data source in the ChatGPT scheduled task.

## Local checks

```bash
python -m py_compile scripts/*.py tests/*.py
python -m pytest -q
```

## Reliability notes

The upstream sources are unofficial public quote endpoints and can be throttled or changed. That is why the design uses two sources, stores confidence, keeps local history, and leaves the existing public-web fallback in place.
