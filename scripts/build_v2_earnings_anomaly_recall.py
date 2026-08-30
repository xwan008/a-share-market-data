from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data/research/company_industry_index.json"
LATEST = ROOT / "data/latest.json"
OUT = ROOT / "data/research/v2/earnings_anomaly_recall.json"
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


def code_of(row):
    raw = col(row, ["股票代码", "代码", "证券代码"])
    return str(raw).split(".")[0].zfill(6) if raw not in (None, "") else None


def main() -> int:
    import akshare as ak

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    codes = sorted({str(c).zfill(6) for c in index.get("companies", {})} | {str(c).zfill(6) for c in index.get("missing_codes", [])})
    codes = [c for c in codes if c.startswith(MAIN_PREFIXES)]
    quotes = latest.get("stocks", {})

    # 2026-08 shadow baseline: H1 report/flash plus Q3 forecast. These dates should roll with the reporting calendar before production.
    source_errors = {}
    try:
        report_rows = frame_rows(ak.stock_yjbb_em(date="20260630"))
    except Exception as exc:
        report_rows = []; source_errors["h1_report"] = f"{type(exc).__name__}:{exc}"
    try:
        bulletin_rows = frame_rows(ak.stock_yjkb_em(date="20260630"))
    except Exception as exc:
        bulletin_rows = []; source_errors["h1_bulletin"] = f"{type(exc).__name__}:{exc}"
    try:
        forecast_rows = frame_rows(ak.stock_yjyg_em(date="20260930"))
    except Exception as exc:
        forecast_rows = []; source_errors["q3_forecast"] = f"{type(exc).__name__}:{exc}"

    reports = {}
    for row in report_rows + bulletin_rows:
        code = code_of(row)
        if code and code in codes:
            reports.setdefault(code, {}).update({k: v for k, v in row.items() if v not in (None, "")})
    forecasts = {}
    for row in forecast_rows:
        code = code_of(row)
        if code and code in codes:
            forecasts.setdefault(code, []).append(row)

    results = {}
    candidates = []
    for code in codes:
        row = reports.get(code) or {}
        frows = forecasts.get(code, [])
        name = (quotes.get(code) or {}).get("name") or (index.get("companies", {}).get(code) or {}).get("name") or code
        rev_yoy = num(col(row, ["营业总收入-同比增长", "营业收入-同比增长", "营业总收入同比", "营业收入同比", "营业收入同比增长", "营业总收入同比增长率"]))
        profit_yoy = num(col(row, ["净利润-同比增长", "归母净利润-同比增长", "净利润同比", "归母净利润同比", "净利润同比增长", "归母净利润同比增长率"]))
        profit_qoq = num(col(row, ["净利润-季度环比增长", "归母净利润-季度环比增长", "净利润季度环比", "归母净利润季度环比", "净利润环比"]))
        profit = num(col(row, ["净利润-净利润", "归母净利润-净利润", "净利润", "归母净利润"]))
        text = " ".join(str(v) for r in frows for v in r.values() if v not in (None, ""))
        positive_forecast = any(k in text for k in ("预增", "扭亏", "略增", "续盈", "增长")) and not any(k in text for k in ("预减", "首亏", "续亏"))

        status = "reject"; score = 0.0; reasons = []
        if positive_forecast:
            status = "pass"; score += 80; reasons.append("Q3存在正向业绩预告/预期文本")
        if profit is not None and profit <= 0:
            reasons.append("当前归母净利润非正，需公司研究阶段确认是否为真实拐点")
        if profit_yoy is not None and rev_yoy is not None and profit_yoy >= 40 and rev_yoy >= 8:
            status = "pass"; score += min(profit_yoy, 200)*0.35 + min(rev_yoy, 100)*0.30
            reasons.append(f"H1收入同比{rev_yoy:.1f}%且净利同比{profit_yoy:.1f}%")
        elif profit_yoy is not None and rev_yoy is not None and profit_yoy >= 20 and rev_yoy >= 5:
            status = "uncertain" if status == "reject" else status
            score += min(profit_yoy, 150)*0.25 + min(rev_yoy, 80)*0.20
            reasons.append(f"H1收入/利润同步改善{rev_yoy:.1f}%/{profit_yoy:.1f}%")
        elif profit_yoy is not None and profit_yoy >= 60 and (rev_yoy is None or rev_yoy >= 0):
            status = "uncertain" if status == "reject" else status
            score += min(profit_yoy, 200)*0.25
            reasons.append(f"H1净利高增{profit_yoy:.1f}%，需排除低基数/一次性因素")
        if profit_qoq is not None and profit_qoq >= 30 and profit is not None and profit > 0:
            status = "uncertain" if status == "reject" else status
            score += min(profit_qoq, 200)*0.15
            reasons.append(f"最新季度净利环比改善{profit_qoq:.1f}%")
        if not reasons:
            reasons.append("未达到本轮全市场盈利异常宽召回阈值")

        item = {
            "code": code, "name": name, "status": status, "triage_score": round(score, 3),
            "reason": "；".join(reasons),
            "metrics": {"revenue_yoy_pct": rev_yoy, "net_profit_yoy_pct": profit_yoy, "net_profit_qoq_pct": profit_qoq, "net_profit": profit, "q3_positive_forecast": positive_forecast}
        }
        results[code] = item
        if status in {"pass", "uncertain"}:
            candidates.append(item)

    candidates.sort(key=lambda x: (-x["triage_score"], x["code"]))
    payload = {
        "schema_version": 1,
        "mode": "shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "reference_trade_date": latest.get("trade_date"),
        "universe_source": "full_mainboard_company_index",
        "universe_count": len(codes),
        "screened_count": len(results),
        "source_errors": source_errors,
        "status_counts": {k: sum(1 for x in results.values() if x["status"] == k) for k in ("pass", "uncertain", "reject")},
        "candidate_codes": [x["code"] for x in candidates],
        "candidates": candidates,
        "screen_results": results,
        "method_note": "This is recall only. It deliberately does not use price, valuation, technical structure, T1/T2, or industry status. Company-research must validate recurring profit, cash flow, one-off risk and the 1-2Q forward bridge before admission."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": "ok", "universe": len(codes), "counts": payload["status_counts"], "source_errors": source_errors}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
