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
UNIVERSE_PATH = ROOT / "config" / "industry_scan_universe.json"
OUTPUT_PATH = DATA_DIR / "research" / "company_industry_index.json"
TZ = ZoneInfo("Asia/Shanghai")
MAIN_BOARD_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003")


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def is_main_board(code: str) -> bool:
    code = str(code).zfill(6)
    return code.startswith(MAIN_BOARD_PREFIXES)


def iso_date(value) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text in {"NaT", "nan", "None"}:
        return None
    return text[:10]


def load_sw_taxonomy():
    import akshare as ak

    df = ak.stock_industry_category_cninfo(symbol="申银万国行业分类标准")
    if df is None or df.empty:
        raise RuntimeError("empty_sw_taxonomy")
    nodes: dict[str, dict] = {}
    for _, row in df.iterrows():
        code = str(row.get("类目编码") or "").strip()
        if not code:
            continue
        level_raw = row.get("分级")
        try:
            level = int(level_raw)
        except (TypeError, ValueError):
            level = -1
        nodes[code] = {
            "name": str(row.get("类目名称") or "").strip(),
            "parent": str(row.get("父类编码") or "").strip(),
            "level": level,
        }
    return nodes


def level1_from_code(industry_code: str | None, taxonomy: dict[str, dict]) -> tuple[str | None, str | None]:
    code = str(industry_code or "").strip()
    visited: set[str] = set()
    while code and code not in visited:
        visited.add(code)
        node = taxonomy.get(code)
        if not node:
            return None, None
        if node.get("level") == 1:
            return code, node.get("name") or None
        code = node.get("parent") or ""
    return None, None


def fetch_company_classification(code: str, name: str, taxonomy: dict[str, dict], broad_name_to_id: dict[str, str], now_iso: str) -> tuple[str, dict | None, str | None]:
    import akshare as ak

    try:
        df = ak.stock_industry_change_cninfo(symbol=code, start_date="19900101", end_date=now_iso[:10].replace("-", ""))
        if df is None or df.empty:
            return code, None, "empty_industry_history"

        sw = df[
            df.get("分类标准", "").astype(str).str.contains("申银万国", na=False)
            | (df.get("分类标准编码", "").astype(str) == "008003")
        ].copy()
        if sw.empty:
            return code, None, "no_sw_classification"

        if "变更日期" in sw.columns:
            sw = sw.sort_values("变更日期")
        row = sw.iloc[-1]
        industry_code = str(row.get("行业编码") or "").strip() or None
        level1_code, level1_name = level1_from_code(industry_code, taxonomy)
        broad_id = broad_name_to_id.get(level1_name or "")

        item = {
            "name": name or str(row.get("新证券简称") or "").strip(),
            "source": "cninfo_sw_industry_via_akshare",
            "classification_standard": str(row.get("分类标准") or "申银万国行业分类标准"),
            "industry_code": industry_code,
            "sw_level1_code": level1_code,
            "sw_level1_name": level1_name,
            "registry_broad_industry_id": broad_id,
            "hierarchy": {
                "门类": None if str(row.get("行业门类")) == "nan" else row.get("行业门类"),
                "次类": None if str(row.get("行业次类")) == "nan" else row.get("行业次类"),
                "大类": None if str(row.get("行业大类")) == "nan" else row.get("行业大类"),
                "中类": None if str(row.get("行业中类")) == "nan" else row.get("行业中类"),
            },
            "classification_change_date": iso_date(row.get("变更日期")),
            "last_verified_at": now_iso,
            "mapping_status": "mapped" if broad_id else "unmapped",
        }
        return code, item, None
    except Exception as exc:
        return code, None, f"{type(exc).__name__}:{exc}"


def is_stale(item: dict | None, now: datetime, refresh_days: int) -> bool:
    if not item:
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
    parser = argparse.ArgumentParser(description="Build persistent main-board SW industry index")
    parser.add_argument("--refresh-days", type=int, default=60)
    parser.add_argument("--limit", type=int, default=0, help="0 means all missing/stale codes")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    now = datetime.now(TZ)
    now_iso = now.isoformat()
    latest = read_json(LATEST_PATH, {})
    stocks = {
        str(code).zfill(6): quote
        for code, quote in latest.get("stocks", {}).items()
        if is_main_board(str(code).zfill(6))
    }
    if not stocks:
        print(json.dumps({"status": "error", "reason": "no_main_board_stocks"}, ensure_ascii=False))
        return 2

    universe = read_json(UNIVERSE_PATH, {})
    broad_name_to_id = {
        str(item.get("name")): str(item.get("id"))
        for item in universe.get("broad_industries", [])
        if item.get("name") and item.get("id")
    }

    old = read_json(OUTPUT_PATH, {"companies": {}})
    existing: dict[str, dict] = old.get("companies", {}) if isinstance(old.get("companies"), dict) else {}

    try:
        taxonomy = load_sw_taxonomy()
    except Exception as exc:
        print(json.dumps({"status": "error", "reason": f"taxonomy_failed:{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 2

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
                broad_name_to_id,
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

    # Never keep delisted/non-universe codes in the live index.
    updated = {code: item for code, item in updated.items() if code in stocks}

    indexed_count = len(updated)
    mapped_count = sum(1 for item in updated.values() if item.get("registry_broad_industry_id"))
    missing_codes = sorted(set(stocks) - set(updated))
    coverage_pct = indexed_count / len(stocks) * 100 if stocks else 0.0
    mapped_pct = mapped_count / indexed_count * 100 if indexed_count else 0.0

    payload = {
        "schema_version": 1,
        "generated_at": now_iso,
        "source": "cninfo_sw_industry_via_akshare",
        "trade_date_reference": latest.get("trade_date"),
        "refresh_days": args.refresh_days,
        "main_board_universe_count": len(stocks),
        "attempted_refresh_count": len(refresh_codes),
        "successful_refresh_count": successes,
        "failed_refresh_count": len(failures),
        "indexed_count": indexed_count,
        "mapped_to_registry_broad_count": mapped_count,
        "coverage_pct": round(coverage_pct, 2),
        "mapped_pct": round(mapped_pct, 2),
        "status": "healthy" if coverage_pct >= 98 else ("degraded" if coverage_pct >= 80 else "building"),
        "missing_codes_sample": missing_codes[:50],
        "failure_sample": dict(list(failures.items())[:50]),
        "companies": updated,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "companies"}, ensure_ascii=False))
    # Partial data is persisted deliberately; validator decides whether a T2 recall has sufficient coverage.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
