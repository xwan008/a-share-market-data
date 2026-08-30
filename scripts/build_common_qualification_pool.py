from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
T2 = ROOT / "data/research/pipeline/t2_company_recall.json"
WEEKLY = ROOT / "data/research/weekly_fundamental_opportunity_pool.json"
LIGHT = ROOT / "data/research/pipeline/weekly_light_recall.json"
LATEST = ROOT / "data/latest.json"
OUT = ROOT / "data/research/pipeline/common_qualification_pool.json"
TZ = ZoneInfo("Asia/Shanghai")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    t2 = load(T2)
    weekly = load(WEEKLY)
    light = load(LIGHT)
    latest = load(LATEST)
    now = datetime.now(TZ).isoformat()

    t2_tags: dict[str, list[str]] = {}
    t2_exposure: dict[str, list[str]] = {}
    for chain in t2.get("t2_subchains", []):
        tag = f"{chain.get('broad_industry_id')}::{chain.get('subchain')}"
        for code, item in (chain.get("classifications") or {}).items():
            code = str(code).zfill(6)
            if isinstance(item, dict) and item.get("status") == "exposed":
                t2_tags.setdefault(code, []).append(tag)
                if item.get("reason"):
                    t2_exposure.setdefault(code, []).append(str(item.get("reason")))
        for row in chain.get("cross_industry_discoveries", []) or []:
            code = str(row.get("code") or "").zfill(6)
            if code:
                t2_tags.setdefault(code, []).append(tag)
                t2_exposure.setdefault(code, []).append(str(row.get("exposure_summary") or "cross-industry verified exposure"))

    t2_codes = set(t2_tags)
    weekly_rows = {
        str(row.get("code")).zfill(6): row
        for row in weekly.get("candidates", [])
        if row.get("status") != "移除"
    }
    weekly_codes = set(weekly_rows)
    overlap = t2_codes & weekly_codes
    merged = t2_codes | weekly_codes
    screen = light.get("screen_results", {})
    stocks = latest.get("stocks", {})

    gate = {}
    passed = []
    for code in sorted(merged):
        source = "both" if code in overlap else ("T2-subchain" if code in t2_codes else "weekly")
        name = (stocks.get(code) or {}).get("name") or (weekly_rows.get(code) or {}).get("name") or code
        metrics = (screen.get(code) or {}).get("metrics") or {}
        weekly_row = weekly_rows.get(code)
        tags = sorted(set(t2_tags.get(code, [])))

        if weekly_row:
            status = "pass"
            reason = "周度全市场深验已验证未来1-2季度盈利桥。"
            bridge = weekly_row.get("forward_bridge")
            invalidation = weekly_row.get("invalidation_condition")
        else:
            revenue_yoy = metrics.get("revenue_yoy_pct")
            profit_yoy = metrics.get("net_profit_yoy_pct")
            profit_qoq = metrics.get("net_profit_qoq_pct")
            profit = metrics.get("net_profit")
            is_st = "ST" in str(name).upper()
            sufficient = (
                isinstance(profit, (int, float)) and profit > 0 and not is_st and (
                    (isinstance(profit_yoy, (int, float)) and isinstance(revenue_yoy, (int, float)) and profit_yoy >= 15 and revenue_yoy >= 5)
                    or
                    (isinstance(profit_qoq, (int, float)) and profit_qoq >= 20 and (revenue_yoy is None or revenue_yoy >= 0))
                )
            )
            if sufficient:
                status = "pass"
                reason = "冻结T2直接盈利链仍有效，且公司H1/Q2主营盈利传导已出现；满足公司级未来盈利门槛的最低验证要求。"
                driver = " / ".join(tags)
                bridge = f"冻结T2领先变量({driver}) → 公司已验证的直接业务暴露 → 当前收入/利润传导为正 → 若T2链不降级，未来1-2季度盈利方向保持向上。"
                invalidation = "对应T2细分链降级/失效，或公司后续收入、利润率、订单/产销出现与产业链方向相反的明显恶化。"
            else:
                status = "reject"
                reason = "虽然属于冻结T2直接链召回，但本轮公司级H1/Q2盈利传导不足、亏损、ST或缺少可验证财务桥；不能仅靠行业T2自动通过。"
                bridge = None
                invalidation = None

        gate[code] = {
            "code": code,
            "name": name,
            "source": source,
            "t2_tags": tags,
            "t2_exposure": t2_exposure.get(code, []),
            "metrics": metrics,
            "gate_status": status,
            "reason": reason,
            "forward_bridge": bridge,
            "invalidation_condition": invalidation,
        }
        if status == "pass":
            passed.append(code)

    arithmetic = {
        "t2_recall_unique_count": len(t2_codes),
        "weekly_pool_effective_count": len(weekly_codes),
        "overlap_count": len(overlap),
        "merged_pre_gate_count": len(merged),
        "future_earnings_gate_removals": len(merged) - len(passed),
        "common_qualification_pool_count": len(passed),
    }
    if arithmetic["t2_recall_unique_count"] + arithmetic["weekly_pool_effective_count"] - arithmetic["overlap_count"] != arithmetic["merged_pre_gate_count"]:
        raise RuntimeError("merge reconciliation failed")
    if arithmetic["merged_pre_gate_count"] - arithmetic["future_earnings_gate_removals"] != arithmetic["common_qualification_pool_count"]:
        raise RuntimeError("gate reconciliation failed")

    payload = {
        "schema_version": 1,
        "generated_at": now,
        "t2_recall_frozen_at": t2.get("t2_recall_frozen_at"),
        "weekly_pool_generated_at": weekly.get("generated_at"),
        "arithmetic": arithmetic,
        "overlap_codes": sorted(overlap),
        "merged_pre_gate_codes": sorted(merged),
        "future_earnings_gate": gate,
        "common_pool_codes": sorted(passed),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"ok", **arithmetic}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
