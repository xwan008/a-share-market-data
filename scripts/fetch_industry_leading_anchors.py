#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "industry_leading_anchor_sources.json"
HEALTH_PATH = ROOT / "data" / "health.json"
OUTPUT_PATH = ROOT / "data" / "research" / "industry_leading_anchors.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def current_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def fnum(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    text = str(value).strip().replace(",", "").replace("，", "").replace("%", "")
    if not text or text.lower() in {"nan", "none", "null", "--", "-", "—"}:
        return None
    try:
        result = float(text)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def parse_period(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(20\d{2}|19\d{2})[-/年.](\d{1,2})(?:[-/月.](\d{1,2}))?", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3) or 1))
        except ValueError:
            return None
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            pass
    if len(digits) >= 6:
        try:
            return date(int(digits[:4]), int(digits[4:6]), 1)
        except ValueError:
            pass
    return None


def freshness(ref_day: date | None, target_day: date, frequency: str, config: dict) -> dict:
    max_age = int((config.get("freshness_days") or {}).get(frequency, 55))
    if not ref_day:
        return {"status": "unknown", "age_calendar_days": None, "max_age_calendar_days": max_age}
    age = (target_day - ref_day).days
    return {"status": "fresh" if 0 <= age <= max_age else "stale", "age_calendar_days": age, "max_age_calendar_days": max_age}


def pick_date_column(frame, candidates: list[str]):
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    for column in frame.columns:
        if any(token in str(column) for token in ("日期", "时间", "月份", "date", "Date")):
            return column
    raise RuntimeError(f"date_column_missing:{list(frame.columns)}")


def collect_akshare_table(ak, candidate: dict, target_day: date, config: dict) -> dict:
    function_name = candidate["function"]
    frame = getattr(ak, function_name)(**(candidate.get("kwargs") or {}))
    if frame is None or frame.empty:
        raise RuntimeError("empty_dataframe")
    row_filter = candidate.get("row_filter") or {}
    for column, allowed in row_filter.items():
        if column in frame.columns:
            tokens = [str(item) for item in allowed]
            frame = frame.loc[frame[column].astype(str).apply(lambda value: any(token in value for token in tokens))]
    if frame.empty:
        raise RuntimeError("row_filter_empty")
    date_col = pick_date_column(frame, candidate.get("date_columns") or [])
    metric_cols = [column for column in (candidate.get("metric_columns") or []) if column in frame.columns]
    if not metric_cols:
        raise RuntimeError(f"metric_columns_missing:{list(frame.columns)}")
    dated = []
    for _, row in frame.iterrows():
        row_day = parse_period(row.get(date_col))
        if row_day and row_day <= target_day:
            dated.append((row_day, row))
    if not dated:
        raise RuntimeError("no_parseable_rows")
    latest_day = max(day for day, _ in dated)
    metrics = {}
    scope_columns = [column for column in row_filter if column in frame.columns]
    for day, row in dated:
        if day != latest_day:
            continue
        prefix = "|".join(f"{column}={row.get(column)}" for column in scope_columns)
        for column in metric_cols:
            raw = row.get(column)
            value = fnum(raw)
            if value is None:
                text = str(raw).strip() if raw is not None else ""
                if not text or text.lower() == "nan":
                    continue
                output = text
            else:
                output = round(value, 6)
            metrics[f"{prefix}::{column}" if prefix else str(column)] = output
    if not metrics:
        raise RuntimeError("latest_row_has_no_metrics")
    frequency = candidate.get("frequency", "monthly")
    return {"anchor_id": candidate["id"], "source_type": "akshare_table", "source": f"akshare.{function_name}", "proxy_strength": candidate.get("proxy_strength", "primary"), "reference_date": latest_day.isoformat(), "frequency": frequency, "freshness": freshness(latest_day, target_day, frequency, config), "metrics": metrics}


def collect_futures_basket(ak, candidate: dict, target_day: date, config: dict) -> dict:
    frequency = candidate.get("frequency", "daily")
    max_age = int((config.get("freshness_days") or {}).get(frequency, 7))
    summaries, errors, reference_days = {}, {}, []
    for symbol in candidate.get("symbols") or []:
        try:
            frame = ak.futures_zh_daily_sina(symbol=symbol)
            date_col = next((column for column in frame.columns if str(column).lower() == "date"), None)
            close_col = next((column for column in frame.columns if str(column).lower() == "close"), None)
            if date_col is None or close_col is None:
                raise RuntimeError(f"columns_missing:{list(frame.columns)}")
            rows = []
            for _, row in frame.iterrows():
                row_day, close = parse_period(row.get(date_col)), fnum(row.get(close_col))
                if row_day and row_day <= target_day and close is not None and close > 0:
                    rows.append((row_day, close))
            rows.sort(key=lambda item: item[0])
            if len(rows) < 20:
                raise RuntimeError(f"insufficient_history:{len(rows)}")
            last_day = rows[-1][0]
            if (target_day - last_day).days > max_age:
                raise RuntimeError(f"stale:{last_day.isoformat()}")
            closes = [item[1] for item in rows]
            current = closes[-1]
            ma20 = sum(closes[-20:]) / 20
            ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else None
            summaries[symbol] = {"last_date": last_day.isoformat(), "current": round(current, 6), "ma20": round(ma20, 6), "ma60": round(ma60, 6) if ma60 else None, "change_20_sessions_pct": round((current / closes[-20] - 1) * 100, 4), "trend_20_vs_60_pct": round((ma20 / ma60 - 1) * 100, 4) if ma60 else None}
            reference_days.append(last_day)
        except Exception as exc:
            errors[symbol] = f"{type(exc).__name__}:{exc}"
    min_success = int(candidate.get("min_success") or 1)
    if len(summaries) < min_success:
        raise RuntimeError(f"futures_success_below_min:{len(summaries)}/{min_success}:{errors}")
    latest_day = max(reference_days)
    return {"anchor_id": candidate["id"], "source_type": "futures_basket", "source": "akshare.futures_zh_daily_sina", "proxy_strength": candidate.get("proxy_strength", "primary"), "reference_date": latest_day.isoformat(), "frequency": frequency, "freshness": freshness(latest_day, target_day, frequency, config), "metrics": {"symbols": summaries, "errors": errors}}


def collect_health_commodity(candidate: dict, target_day: date, config: dict, health: dict) -> dict:
    commodity = health.get("commodity_anchors") or {}
    rows = commodity.get("anchors") or {}
    selected, reference_days = {}, []
    for symbol in candidate.get("symbols") or []:
        row = rows.get(symbol)
        row_day = parse_period((row or {}).get("last_date"))
        if not row or not row_day:
            continue
        selected[symbol] = {key: row.get(key) for key in ("name", "role", "last_date", "current", "ma20", "ma60", "current_to_neutral", "trend_20_vs_60_pct")}
        reference_days.append(row_day)
    min_success = int(candidate.get("min_success") or 1)
    if len(selected) < min_success:
        raise RuntimeError(f"health_commodity_success_below_min:{len(selected)}/{min_success}")
    latest_day = max(reference_days)
    frequency = candidate.get("frequency", "daily")
    return {"anchor_id": candidate["id"], "source_type": "health_commodity", "source": "data/health.json#commodity_anchors", "proxy_strength": candidate.get("proxy_strength", "primary"), "reference_date": latest_day.isoformat(), "frequency": frequency, "freshness": freshness(latest_day, target_day, frequency, config), "metrics": {"symbols": selected, "source_status": commodity.get("status")}}


def collect_cpca_monthly(ak, candidate: dict, target_day: date, config: dict) -> dict:
    frame = getattr(ak, candidate["function"])(**(candidate.get("kwargs") or {}))
    if frame is None or frame.empty:
        raise RuntimeError("empty_dataframe")
    month_col = next((column for column in frame.columns if "月份" in str(column)), None)
    if month_col is None:
        raise RuntimeError(f"month_column_missing:{list(frame.columns)}")
    year_columns = []
    for column in frame.columns:
        match = re.search(r"(20\d{2})年", str(column))
        if match:
            year_columns.append((column, int(match.group(1))))
    points = []
    for _, row in frame.iterrows():
        month_match = re.search(r"(\d{1,2})", str(row.get(month_col) or ""))
        if not month_match:
            continue
        month = int(month_match.group(1))
        for column, year in year_columns:
            value = fnum(row.get(column))
            if value is None:
                continue
            try:
                point_day = date(year, month, 1)
            except ValueError:
                continue
            if point_day <= target_day:
                points.append((point_day, value))
    if not points:
        raise RuntimeError("no_monthly_points")
    points.sort(key=lambda item: item[0])
    latest_day, latest_value = points[-1]
    previous_year = next((value for day, value in reversed(points) if day.year == latest_day.year - 1 and day.month == latest_day.month), None)
    metrics = {"value": round(latest_value, 6), "unit": "万辆"}
    if previous_year not in (None, 0):
        metrics["yoy_pct"] = round((latest_value / previous_year - 1) * 100, 4)
    frequency = candidate.get("frequency", "monthly")
    return {"anchor_id": candidate["id"], "source_type": "cpca_monthly", "source": f"akshare.{candidate['function']}", "source_args": candidate.get("kwargs") or {}, "proxy_strength": candidate.get("proxy_strength", "primary"), "reference_date": latest_day.isoformat(), "frequency": frequency, "freshness": freshness(latest_day, target_day, frequency, config), "metrics": metrics}


def collect_movie_monthly(ak, candidate: dict, target_day: date, config: dict) -> dict:
    completed_month_end = target_day.replace(day=1) - timedelta(days=1)
    frame = getattr(ak, candidate["function"])(date=completed_month_end.strftime("%Y%m%d"))
    if frame is None or frame.empty or "单月票房" not in frame.columns:
        raise RuntimeError("movie_monthly_empty_or_columns_missing")
    values = [fnum(value) for value in frame["单月票房"].tolist()]
    values = [value for value in values if value is not None]
    if not values:
        raise RuntimeError("movie_boxoffice_no_numeric_values")
    metrics = {"boxoffice_total_100m_cny": round(sum(values), 6), "movie_count": len(values)}
    frequency = candidate.get("frequency", "monthly")
    return {"anchor_id": candidate["id"], "source_type": "movie_monthly", "source": f"akshare.{candidate['function']}", "proxy_strength": candidate.get("proxy_strength", "primary"), "reference_date": completed_month_end.isoformat(), "frequency": frequency, "freshness": freshness(completed_month_end, target_day, frequency, config), "metrics": metrics}


def collect_nbs_path(ak, candidate: dict, target_day: date, config: dict) -> dict:
    errors = {}
    frequency = candidate.get("frequency", "monthly")
    min_matches = int(candidate.get("min_keyword_matches") or 1)
    for path in candidate.get("paths") or []:
        try:
            frame = ak.macro_china_nbs_nation(kind=candidate.get("kind", "月度数据"), path=path, period=candidate.get("period", "LAST24"))
            if frame is None or frame.empty:
                raise RuntimeError("empty_dataframe")
            matched, reference_days = {}, []
            for raw_index, row in frame.iterrows():
                label = str(raw_index)
                if not any(keyword in label for keyword in candidate.get("keywords") or []):
                    continue
                best = None
                for column in frame.columns:
                    point_day, value = parse_period(column), fnum(row.get(column))
                    if point_day and point_day <= target_day and value is not None and (best is None or point_day > best[0]):
                        best = (point_day, value, str(column))
                if best:
                    point_day, value, column = best
                    matched[label] = {"value": round(value, 6), "period": column, "reference_date": point_day.isoformat()}
                    reference_days.append(point_day)
            if len(matched) < min_matches:
                raise RuntimeError(f"keyword_matches_below_min:{len(matched)}/{min_matches}")
            latest_day = max(reference_days)
            return {"anchor_id": candidate["id"], "source_type": "nbs_path", "source": "akshare.macro_china_nbs_nation", "source_path": path, "proxy_strength": candidate.get("proxy_strength", "primary"), "reference_date": latest_day.isoformat(), "frequency": frequency, "freshness": freshness(latest_day, target_day, frequency, config), "metrics": matched}
        except Exception as exc:
            errors[path] = f"{type(exc).__name__}:{exc}"
    raise RuntimeError(f"all_nbs_paths_failed:{errors}")


COLLECTORS = {"akshare_table": collect_akshare_table, "futures_basket": collect_futures_basket, "cpca_monthly": collect_cpca_monthly, "movie_monthly": collect_movie_monthly, "nbs_path": collect_nbs_path}


def collect_candidate(ak, candidate: dict, target_day: date, config: dict, health: dict) -> dict:
    if candidate.get("type") == "health_commodity":
        return collect_health_commodity(candidate, target_day, config, health)
    collector = COLLECTORS.get(candidate.get("type"))
    if not collector:
        raise RuntimeError(f"unsupported_candidate_type:{candidate.get('type')}")
    return collector(ak, candidate, target_day, config)


def semantic_payload(payload: dict) -> dict:
    clone = json.loads(json.dumps(payload, ensure_ascii=False))
    clone.pop("generated_at", None)
    clone.pop("source_repo_commit_sha", None)
    return clone


def main() -> int:
    import akshare as ak
    config, health = read_json(CONFIG_PATH), read_json(HEALTH_PATH)
    trade_date = str(health.get("trade_date") or "")[:10]
    target_day = parse_period(trade_date)
    if not target_day:
        raise RuntimeError("health_trade_date_missing")
    if health.get("market_status") != "closed":
        raise RuntimeError(f"market_not_closed:{health.get('market_status')}")
    industries = config.get("industries") or {}
    expected = int(config.get("required_level1_count") or 0)
    if len(industries) != expected:
        raise RuntimeError(f"industry_source_matrix_incomplete:{len(industries)}/{expected}")

    level1, complete, partial, total_attempts, failed_attempts = {}, 0, 0, 0, 0
    for code, industry in industries.items():
        anchors, attempts = [], []
        for candidate in industry.get("candidates") or []:
            total_attempts += 1
            try:
                anchor = collect_candidate(ak, candidate, target_day, config, health)
                fresh = (anchor.get("freshness") or {}).get("status") == "fresh"
                attempts.append({"anchor_id": candidate.get("id"), "type": candidate.get("type"), "status": "fresh" if fresh else "stale", "reference_date": anchor.get("reference_date")})
                anchors.append(anchor)
            except Exception as exc:
                failed_attempts += 1
                attempts.append({"anchor_id": candidate.get("id"), "type": candidate.get("type"), "status": "error", "error": f"{type(exc).__name__}:{exc}"})
        fresh_anchors = [anchor for anchor in anchors if (anchor.get("freshness") or {}).get("status") == "fresh"]
        strong_fresh = [anchor for anchor in fresh_anchors if anchor.get("proxy_strength", "primary") != "secondary"]
        primary = (strong_fresh or fresh_anchors or [None])[0]
        status = "complete" if primary else "partial"
        complete += int(status == "complete")
        partial += int(status == "partial")
        level1[code] = {"code": code, "name": industry.get("name"), "status": status, "primary_anchor_id": primary.get("anchor_id") if primary else None, "anchors": anchors, "attempts": attempts}

    payload = {"contract_id": "a-share-industry-leading-anchors", "schema_version": 1, "rollout_mode": config.get("rollout_mode", "shadow"), "generated_at": datetime.now(timezone.utc).isoformat(), "reference_trade_date": trade_date, "source_repo_commit_sha": current_git_sha(), "collection": {"level1_expected": expected, "level1_accounted": len(level1), "complete": complete, "partial": partial, "total_attempts": total_attempts, "failed_attempts": failed_attempts}, "level1": level1, "semantics": {"primary_anchor_rule": "first fresh non-secondary candidate, otherwise first fresh secondary candidate", "no_market_price_proxy": True, "financial_breadth_not_used_as_leading_anchor": True}}
    if OUTPUT_PATH.exists() and semantic_payload(read_json(OUTPUT_PATH)) == semantic_payload(payload):
        print(json.dumps({"changed": False, "reference_trade_date": trade_date, "complete": complete, "partial": partial, "failed_attempts": failed_attempts}, ensure_ascii=False))
        return 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"changed": True, "reference_trade_date": trade_date, "complete": complete, "partial": partial, "failed_attempts": failed_attempts, "output": str(OUTPUT_PATH.relative_to(ROOT))}, ensure_ascii=False))
    return 0


def self_test() -> int:
    assert parse_period("2026-09-07") == date(2026, 9, 7)
    assert parse_period("2026年08月份") == date(2026, 8, 1)
    assert parse_period("202608") == date(2026, 8, 1)
    assert fnum("12.3%") == 12.3
    assert fnum("--") is None
    config = read_json(CONFIG_PATH)
    assert len(config.get("industries") or {}) == int(config["required_level1_count"]) == 31
    supported = set(COLLECTORS) | {"health_commodity"}
    for code, industry in (config.get("industries") or {}).items():
        assert industry.get("candidates"), code
        for candidate in industry["candidates"]:
            assert candidate.get("type") in supported, (code, candidate)
            assert candidate.get("id"), (code, candidate)
            assert candidate.get("frequency") in (config.get("freshness_days") or {}), (code, candidate)
    print(json.dumps({"self_test": "pass", "industries": 31}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    raise SystemExit(self_test() if args.self_test else main())
