from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LATEST_PATH = DATA_DIR / "latest.json"
TAXONOMY_OUTPUT_PATH = ROOT / "config" / "industry_scan_universe.json"
OUTPUT_PATH = DATA_DIR / "research" / "company_industry_index.json"
TZ = ZoneInfo("Asia/Shanghai")
MAIN_BOARD_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003")
EXPECTED_COUNTS = {1: 31, 2: 134, 3: 346}


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def is_main_board(code: str) -> bool:
    code = str(code).zfill(6)
    return code.startswith(MAIN_BOARD_PREFIXES)


def is_research_eligible_quote(item: dict | None, trade_date: str | None) -> bool:
    """Return whether a quote belongs to the current actionable research universe.

    Raw market snapshots may retain delisted, merged, stale, or otherwise non-tradable
    symbols. Those rows are useful for audit/history, but they must not create false
    Company Mapping Gate failures. Only quotes validated against the current trade
    date (high/medium confidence) are part of the company-research universe.
    """
    if not isinstance(item, dict):
        return False
    if str(item.get("confidence") or "").lower() not in {"high", "medium"}:
        return False
    if not trade_date:
        return True
    source_dates = item.get("source_dates")
    if not isinstance(source_dates, dict):
        return True
    verified_dates = {str(value) for value in source_dates.values() if value}
    return not verified_dates or trade_date in verified_dates


def iso_date(value) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text in {"NaT", "nan", "None"}:
        return None
    return text[:10]


def load_sw_taxonomy() -> dict[str, dict]:
    import akshare as ak

    df = ak.stock_industry_category_cninfo(symbol="申银万国行业分类标准")
    if df is None or df.empty:
        raise RuntimeError("empty_sw_taxonomy")

    nodes: dict[str, dict] = {}
    for _, row in df.iterrows():
        code = str(row.get("类目编码") or "").strip()
        if not code:
            continue
        try:
            level = int(row.get("分级"))
        except (TypeError, ValueError):
            continue
        nodes[code] = {
            "code": code,
            "name": str(row.get("类目名称") or "").strip(),
            "parent_code": str(row.get("父类编码") or "").strip() or None,
            "level": level,
        }
    return nodes


def build_taxonomy_snapshot(nodes: dict[str, dict], now_iso: str) -> dict:
    levels: dict[str, list[dict]] = {}
    counts: dict[str, int] = {}
    for level in (1, 2, 3):
        key = f"level{level}"
        rows = [
            {
                "code": node["code"],
                "name": node["name"],
                "parent_code": node["parent_code"],
            }
            for node in nodes.values()
            if node["level"] == level
        ]
        rows.sort(key=lambda item: item["code"])
        levels[key] = rows
        counts[key] = len(rows)

    expected = {f"level{k}": v for k, v in EXPECTED_COUNTS.items()}
    if counts != expected:
        raise RuntimeError(f"unexpected_sw_taxonomy_counts:{counts}:expected:{expected}")

    return {
        "schema_version": 3,
        "generated_at": now_iso,
        "taxonomy": "申万行业分类标准2021版",
        "role": "coverage_only_not_answer_pool",
        "expected_counts": expected,
        "accounting_rule": "18:00完整研究必须逐一accounted_for全部节点；弱/稳定节点可浅扫描，改善/恶化/显著分化节点进入深度盈利链研究。",
        "profit_chain_rule": "申万三级行业不是盈利链默认终点；若直接盈利Driver、领先变量或利润传导不同，必须继续拆分。",
        "levels": levels,
    }


def resolve_sw_levels(industry_code: str | None, taxonomy: dict[str, dict]) -> dict[str, str | None]:
    code = str(industry_code or "").strip()
    by_level: dict[int, dict] = {}
    visited: set[str] = set()
    while code and code not in visited:
        visited.add(code)
        node = taxonomy.get(code)
        if not node:
            break
        level = int(node.get("level") or 0)
        if level in (1, 2, 3):
            by_level[level] = node
        code = str(node.get("parent_code") or "")

    result: dict[str, str | None] = {}
    for level in (1, 2, 3):
        node = by_level.get(level)
        result[f"sw_level{level}_code"] = node.get("code") if node else None
        result[f"sw_level{level}_name"] = node.get("name") if node else None
    return result


def normalize_entry(item: dict, taxonomy: dict[str, dict]) -> dict:
    levels = resolve_sw_levels(item.get("industry_code"), taxonomy)
    normalized = {
        "name": item.get("name"),
        "source": item.get("source") or "cninfo_sw_industry_via_akshare",
        "classification_standard": item.get("classification_standard") or "申银万国行业分类标准",
        "industry_code": item.get("industry_code"),
        **levels,
        "classification_change_date": item.get("classification_change_date"),
        "last_verified_at": item.get("last_verified_at"),
    }
    normalized["mapping_status"] = (
        "mapped"
        if all(normalized.get(f"sw_level{level}_code") for level in (1, 2, 3))
        else "unmapped"
    )
    return normalized


def fetch_company_classification(
    code: str,
    name: str,
    taxonomy: dict[str, dict],
    now_iso: str,
) -> tuple[str, dict | None, str | None]:
    import akshare as ak

    try:
        df = ak.stock_industry_change_cninfo(
            symbol=code,
            start_date="19900101",
            end_date=now_iso[:10].replace("-", ""),
        )
        if df is None or df.empty:
            return code, None, "empty_industry_history"

        if "分类标准" not in df.columns and "分类标准编码" not in df.columns:
            return code, None, "missing_classification_standard_columns"

        standard = df["分类标准"].astype(str) if "分类标准" in df.columns else ""
        standard_code = df["分类标准编码"].astype(str) if "分类标准编码" in df.columns else ""
        mask = standard.str.contains("申银万国", na=False) if hasattr(standard, "str") else False
        if hasattr(standard_code, "__eq__"):
            mask = mask | (standard_code == "008003")
        sw = df[mask].copy()
        if sw.empty:
            return code, None, "no_sw_classification"

        if "变更日期" in sw.columns:
            sw = sw.sort_values("变更日期")
        row = sw.iloc[-1]
        industry_code = str(row.get("行业编码") or "").strip() or None
        levels = resolve_sw_levels(industry_code, taxonomy)
        item = {
            "name": name or str(row.get("新证券简称") or "").strip(),
            "source": "cninfo_sw_industry_via_akshare",
            "classification_standard": str(row.get("分类标准") or "申银万国行业分类标准"),
            "industry_code": industry_code,
            **levels,
            "classification_change_date": iso_date(row.get("变更日期")),
            "last_verified_at": now_iso,
        }
        item["mapping_status"] = (
            "mapped"
            if all(item.get(f"sw_level{level}_code") for level in (1, 2, 3))
            else "unmapped"
        )
        return code, item, None
    except Exception as exc:
        return code, None, f"{type(exc).__name__}:{exc}"


def is_stale(item: dict | None, now: datetime, refresh_days: int) -> bool:
    if not item or item.get("mapping_status") != "mapped":
        return True
    value = item.get("last_verified_at")
    if not value:
        return True
    try:
        checked = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=TZ)
    return checked < now - timedelta(days=refresh_days)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build persistent active-main-board SW 2021 industry index")
    parser.add_argument("--refresh-days", type=int, default=60)
    parser.add_argument("--limit", type=int, default=0, help="0 means all missing/stale codes")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    now = datetime.now(TZ)
    now_iso = now.isoformat()
    latest = read_json(LATEST_PATH, {})
    trade_date = latest.get("trade_date")
    raw_stocks = {
        str(code).zfill(6): quote
        for code, quote in latest.get("stocks", {}).items()
        if is_main_board(str(code).zfill(6))
    }
    excluded_codes = sorted(
        code for code, quote in raw_stocks.items()
        if not is_research_eligible_quote(quote, trade_date)
    )
    stocks = {
        code: quote for code, quote in raw_stocks.items()
        if is_research_eligible_quote(quote, trade_date)
    }
    if not stocks:
        print(json.dumps({"status": "error", "reason": "no_active_main_board_stocks"}, ensure_ascii=False))
        return 2

    try:
        taxonomy = load_sw_taxonomy()
        taxonomy_snapshot = build_taxonomy_snapshot(taxonomy, now_iso)
    except Exception as exc:
        print(json.dumps({"status": "error", "reason": f"taxonomy_failed:{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 2

    TAXONOMY_OUTPUT_PATH.write_text(
        json.dumps(taxonomy_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    old = read_json(OUTPUT_PATH, {"companies": {}})
    old_companies = old.get("companies", {}) if isinstance(old.get("companies"), dict) else {}
    existing = {
        code: normalize_entry(item, taxonomy)
        for code, item in old_companies.items()
        if code in stocks and isinstance(item, dict)
    }

    refresh_codes = [
        code for code in sorted(stocks)
        if is_stale(existing.get(code), now, args.refresh_days)
    ]
    if args.limit > 0:
        refresh_codes = refresh_codes[: args.limit]

    updated = dict(existing)
    failures: dict[str, str] = {}
    successes = 0

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(
                fetch_company_classification,
                code,
                str(stocks[code].get("name") or ""),
                taxonomy,
                now_iso,
            ): code
            for code in refresh_codes
        }
        for future in as_completed(futures):
            code, item, error = future.result()
            if item is not None:
                updated[code] = item
                successes += 1
            else:
                failures[code] = error or "unknown"

    updated = {code: item for code, item in updated.items() if code in stocks}
    indexed_count = len(updated)
    mapped_count = sum(1 for item in updated.values() if item.get("mapping_status") == "mapped")
    missing_codes = sorted(set(stocks) - set(updated))
    unmapped_codes = sorted(
        code for code, item in updated.items()
        if item.get("mapping_status") != "mapped"
    )
    coverage_pct = indexed_count / len(stocks) * 100 if stocks else 0.0
    mapped_pct = mapped_count / indexed_count * 100 if indexed_count else 0.0

    payload = {
        "schema_version": 2,
        "generated_at": now_iso,
        "source": "cninfo_sw_industry_via_akshare",
        "taxonomy": "申万行业分类标准2021版",
        "trade_date_reference": trade_date,
        "refresh_days": args.refresh_days,
        "raw_main_board_snapshot_count": len(raw_stocks),
        "main_board_universe_count": len(stocks),
        "research_universe_rule": "main-board quote confidence must be high/medium and, when source dates exist, include trade_date_reference",
        "excluded_inactive_or_untradable_count": len(excluded_codes),
        "excluded_inactive_or_untradable_codes": excluded_codes,
        "attempted_refresh_count": len(refresh_codes),
        "successful_refresh_count": successes,
        "failed_refresh_count": len(failures),
        "indexed_count": indexed_count,
        "mapped_to_sw_level3_count": mapped_count,
        "coverage_pct": round(coverage_pct, 2),
        "mapped_pct": round(mapped_pct, 2),
        "status": "healthy" if not missing_codes and not unmapped_codes else ("degraded" if coverage_pct >= 80 else "building"),
        "missing_codes": missing_codes,
        "unmapped_codes": unmapped_codes,
        "failure_sample": dict(list(failures.items())[:50]),
        "companies": updated,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "companies"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
