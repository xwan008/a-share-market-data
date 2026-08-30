from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LATEST_PATH = DATA_DIR / "latest.json"
PART_STATUS_DIR = DATA_DIR / "backfill_parts"
HISTORY_DIR = DATA_DIR / "history_shards"
OUT = DATA_DIR / "backfill_status.json"
TZ = ZoneInfo("Asia/Shanghai")
MIN_OVERALL_FETCH_RATIO = 0.90
MIN_LOCAL_READY_RATIO = 0.90


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and aggregate sharded full-market history backfill")
    parser.add_argument("--partition-count", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    latest = load(LATEST_PATH, {})
    stocks = latest.get("stocks", {})
    expected_codes = {str(code).zfill(6) for code in stocks}
    trade_date = str(latest.get("trade_date") or "")
    errors: list[str] = []

    statuses: dict[int, dict] = {}
    for path in sorted(PART_STATUS_DIR.glob("part-*.json")):
        payload = load(path, {})
        idx = payload.get("partition_index")
        if not isinstance(idx, int):
            errors.append(f"invalid_partition_index:{path.name}")
            continue
        if idx in statuses:
            errors.append(f"duplicate_partition_status:{idx}")
            continue
        statuses[idx] = payload

    expected_indices = set(range(args.partition_count))
    actual_indices = set(statuses)
    if actual_indices != expected_indices:
        errors.append(f"partition_status_mismatch:missing={sorted(expected_indices-actual_indices)}:extra={sorted(actual_indices-expected_indices)}")

    seen_codes: set[str] = set()
    duplicate_codes: set[str] = set()
    successful_codes: set[str] = set()
    failed_by_code: dict[str, str] = {}
    part_summaries = []

    for idx in sorted(statuses):
        status = statuses[idx]
        if status.get("schema_version") != 6:
            errors.append(f"part_{idx}:schema_not_6")
        if status.get("partition_count") != args.partition_count:
            errors.append(f"part_{idx}:partition_count_mismatch")
        requested = {str(c).zfill(6) for c in status.get("requested_codes", [])}
        overlap = seen_codes & requested
        duplicate_codes.update(overlap)
        seen_codes.update(requested)
        failures = {str(c).zfill(6): str(reason) for c, reason in (status.get("failures") or {}).items()}
        failed_by_code.update(failures)
        successful_codes.update(requested - set(failures))
        part_summaries.append(
            {
                "partition_index": idx,
                "requested": len(requested),
                "successful": int(status.get("successful_stocks") or 0),
                "failed": int(status.get("failed_stocks") or 0),
                "success_ratio": status.get("success_ratio"),
                "owned_shard_keys": status.get("owned_shard_keys", []),
            }
        )

    if duplicate_codes:
        errors.append(f"duplicate_partition_codes:{sorted(duplicate_codes)[:20]}")
    if seen_codes != expected_codes:
        errors.append(f"partition_code_coverage_mismatch:missing={len(expected_codes-seen_codes)}:extra={len(seen_codes-expected_codes)}")

    shard_cache: dict[str, dict] = {}
    ge120 = 0
    ge180 = 0
    summary_present = 0
    latest_date = 0
    right_ready = 0
    incomplete_codes: list[str] = []

    for code in sorted(expected_codes):
        key = code[:4]
        if key not in shard_cache:
            shard_cache[key] = load(HISTORY_DIR / f"{key}.json", {"stocks": {}})
        item = (shard_cache[key].get("stocks") or {}).get(code) or {}
        rows = item.get("history") or []
        summary = item.get("long_term_summary") or {}
        points = len(rows)
        last_date = str(rows[-1].get("date") or "") if rows else ""
        has_summary = bool(summary and summary.get("summary_data_date"))
        if points >= 120:
            ge120 += 1
        if points >= 180:
            ge180 += 1
        if has_summary:
            summary_present += 1
        if last_date == trade_date:
            latest_date += 1
        if points >= 120 and has_summary and last_date == trade_date:
            right_ready += 1
        else:
            incomplete_codes.append(code)

    requested = len(expected_codes)
    fetch_success_ratio = len(successful_codes) / requested if requested else 0.0
    ready_ratio = right_ready / requested if requested else 0.0
    if fetch_success_ratio < MIN_OVERALL_FETCH_RATIO:
        errors.append(f"overall_fetch_ratio_below_{MIN_OVERALL_FETCH_RATIO}:{fetch_success_ratio:.4f}")
    if ready_ratio < MIN_LOCAL_READY_RATIO:
        errors.append(f"local_ready_ratio_below_{MIN_LOCAL_READY_RATIO}:{ready_ratio:.4f}")

    payload = {
        "schema_version": 7,
        "mode": "sharded_full_market",
        "generated_at": datetime.now(TZ).isoformat(),
        "partition_count": args.partition_count,
        "completed_partitions": sorted(actual_indices),
        "requested_stocks": requested,
        "successful_fetch_stocks": len(successful_codes),
        "failed_fetch_stocks": len(failed_by_code),
        "fetch_success_ratio": fetch_success_ratio,
        "rolling_days": 180,
        "long_term_summary_window": 252,
        "latest_trade_date": trade_date,
        "local_history_ge_120": ge120,
        "local_history_ge_180": ge180,
        "long_term_summary_present": summary_present,
        "latest_history_date_count": latest_date,
        "right_structure_ready_count": right_ready,
        "right_structure_ready_ratio": ready_ratio,
        "incomplete_count": len(incomplete_codes),
        "incomplete_codes": incomplete_codes,
        "failed_fetches": failed_by_code,
        "partitions": part_summaries,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k not in {"incomplete_codes", "failed_fetches", "partitions"}}, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
