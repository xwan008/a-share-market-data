from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data" / "research" / "company_industry_index.json"
LATEST = ROOT / "data" / "latest.json"
RECALL = ROOT / "data" / "research" / "pipeline" / "t2_company_recall.json"
OUT = ROOT / "data" / "research" / "pipeline" / "weekly_light_recall.json"
SUMMARY = ROOT / "data" / "research" / "pipeline" / "weekly_light_candidates.json"
TZ = ZoneInfo("Asia/Shanghai")
MAIN_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003")


def num(v):
    if v is None:
        return None
    try:
        x = float(str(v).replace("%", "").replace(",", "").strip())
        return None if math.isnan(x) else x
    except Exception:
        return None


def col(row, names):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def frame_rows(df):
    if df is None or getattr(df, "empty", True):
        return []
    return [dict(row) for _, row in df.iterrows()]


def main() -> int:
    import akshare as ak

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    recall = json.loads(RECALL.read_text(encoding="utf-8"))
    codes = sorted({str(c).zfill(6) for c in index.get("companies", {})} | {str(c).zfill(6) for c in index.get("missing_codes", [])})
    codes = [c for c in codes if c.startswith(MAIN_PREFIXES)]
    quotes = latest.get("stocks", {})

    report_rows = []
    report_error = None
    try:
        report_rows = frame_rows(ak.stock_yjbb_em(date="20260630"))
    except Exception as exc:
        report_error = f"{type(exc).__name__}:{exc}"

    bulletin_rows = []
    bulletin_error = None
    try:
        bulletin_rows = frame_rows(ak.stock_yjkb_em(date="20260630"))
    except Exception as exc:
        bulletin_error = f"{type(exc).__name__}:{exc}"

    forecast_rows = []
    forecast_error = None
    try:
        forecast_rows = frame_rows(ak.stock_yjyg_em(date="20260930"))
    except Exception as exc:
        forecast_error = f"{type(exc).__name__}:{exc}"

    def code_of(row):
        raw = col(row, ["股票代码", "代码", "证券代码"])
        return str(raw).split(".")[0].zfill(6) if raw not in (None, "") else None

    reports = {}
    for row in report_rows + bulletin_rows:
        code = code_of(row)
        if code and code in codes:
            current = reports.get(code, {})
            current.update({k: v for k, v in row.items() if v not in (None, "")})
            reports[code] = current

    forecasts = {}
    for row in forecast_rows:
        code = code_of(row)
        if code and code in codes:
            forecasts.setdefault(code, []).append(row)

    screen = {}
    candidates = []
    for code in codes:
        q = quotes.get(code, {})
        name = q.get("name") or index.get("companies", {}).get(code, {}).get("name") or code
        row = reports.get(code)
        frows = forecasts.get(code, [])
        rev_yoy = num(col(row or {}, [
            "营业总收入-同比增长", "营业收入-同比增长",
            "营业总收入同比", "营业收入同比", "营业收入同比增长", "营业总收入同比增长率"
        ]))
        profit_yoy = num(col(row or {}, [
            "净利润-同比增长", "归母净利润-同比增长",
            "净利润同比", "归母净利润同比", "净利润同比增长", "归母净利润同比增长率"
        ]))
        profit_qoq = num(col(row or {}, [
            "净利润-季度环比增长", "归母净利润-季度环比增长",
            "净利润季度环比", "归母净利润季度环比", "净利润环比"
        ]))
        revenue = num(col(row or {}, [
            "营业总收入-营业总收入", "营业收入-营业收入", "营业总收入", "营业收入"
        ]))
        profit = num(col(row or {}, [
            "净利润-净利润", "归母净利润-净利润", "净利润", "归母净利润"
        ]))
        ftext = " ".join(str(v) for r in frows for v in r.values() if v not in (None, ""))
        positive_forecast = any(k in ftext for k in ("预增", "扭亏", "略增", "续盈", "增长")) and not any(k in ftext for k in ("预减", "首亏", "续亏"))

        status = "reject"
        reasons = []
        score = 0.0
        if positive_forecast:
            status = "pass"
            score += 80
            reasons.append("存在2026Q3正向业绩预告/预期文本")
        if row:
            if profit_yoy is not None and rev_yoy is not None and profit_yoy >= 40 and rev_yoy >= 8:
                status = "pass"
                score += min(profit_yoy, 200) * 0.35 + min(rev_yoy, 100) * 0.3
                reasons.append(f"H1收入同比{rev_yoy:.1f}%且净利同比{profit_yoy:.1f}%")
            elif profit_yoy is not None and rev_yoy is not None and profit_yoy >= 20 and rev_yoy >= 5:
                if status != "pass":
                    status = "uncertain"
                score += min(profit_yoy, 150) * 0.25 + min(rev_yoy, 80) * 0.2
                reasons.append(f"H1收入/利润同时改善: {rev_yoy:.1f}%/{profit_yoy:.1f}%")
            elif profit_yoy is not None and profit_yoy >= 60 and (rev_yoy is None or rev_yoy >= 0):
                if status != "pass":
                    status = "uncertain"
                score += min(profit_yoy, 200) * 0.25
                reasons.append(f"H1净利高增{profit_yoy:.1f}%，需排除低基数/一次性因素")
            if profit_qoq is not None and profit_qoq >= 30 and profit is not None and profit > 0:
                if status == "reject":
                    status = "uncertain"
                score += min(profit_qoq, 200) * 0.15
                reasons.append(f"最新季度净利环比改善{profit_qoq:.1f}%")
        if not reasons:
            if not row and not frows:
                reasons.append("未取得足以触发本周宽召回的最新财报/预告证据")
            else:
                reasons.append("最新公开财务数据未达到宽召回阈值")

        item = {
            "status": status,
            "reason": "；".join(reasons),
            "name": name,
            "metrics": {
                "revenue_yoy_pct": rev_yoy,
                "net_profit_yoy_pct": profit_yoy,
                "net_profit_qoq_pct": profit_qoq,
                "revenue": revenue,
                "net_profit": profit,
                "q3_positive_forecast": positive_forecast,
            },
            "triage_score": round(score, 3),
        }
        screen[code] = item
        if status in {"pass", "uncertain"}:
            candidates.append({"code": code, **item})

    candidates.sort(key=lambda x: (-x["triage_score"], x["code"]))
    now = datetime.now(TZ).isoformat()
    payload = {
        "schema_version": 1,
        "generated_at": now,
        "t2_recall_frozen_at": recall.get("t2_recall_frozen_at"),
        "weekly_stage_started_at": now,
        "universe_count": len(codes),
        "screened_count": len(screen),
        "source_status": {
            "h1_report_rows": len(report_rows), "h1_report_error": report_error,
            "h1_bulletin_rows": len(bulletin_rows), "h1_bulletin_error": bulletin_error,
            "q3_forecast_rows": len(forecast_rows), "q3_forecast_error": forecast_error,
        },
        "status_counts": {
            "pass": sum(1 for x in screen.values() if x["status"] == "pass"),
            "uncertain": sum(1 for x in screen.values() if x["status"] == "uncertain"),
            "reject": sum(1 for x in screen.values() if x["status"] == "reject"),
        },
        "screen_results": screen,
    }
    summary = {
        "schema_version": 1,
        "generated_at": now,
        "universe_count": len(codes),
        "candidate_count": len(candidates),
        "source_status": payload["source_status"],
        "candidates": candidates,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status":"ok","universe":len(codes),"status_counts":payload["status_counts"],"source_status":payload["source_status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
