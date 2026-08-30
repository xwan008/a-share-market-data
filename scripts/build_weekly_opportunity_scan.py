from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LIGHT = ROOT / "data" / "research" / "pipeline" / "weekly_light_recall.json"
T2 = ROOT / "data" / "research" / "pipeline" / "t2_company_recall.json"
OLD_POOL = ROOT / "data" / "research" / "weekly_fundamental_opportunity_pool.json"
OVERRIDES = ROOT / "config" / "current_weekly_deep_overrides.json"
OUTPUT = ROOT / "data" / "research" / "pipeline" / "weekly_opportunity_scan.json"
POOL = ROOT / "data" / "research" / "weekly_fundamental_opportunity_pool.json"
TZ = ZoneInfo("Asia/Shanghai")


def active_t2_codes(t2: dict) -> set[str]:
    out = set()
    for chain in t2.get("t2_subchains", []):
        for link in chain.get("value_chain_links", []):
            for row in link.get("companies", []):
                out.add(str(row.get("code") or "").zfill(6))
    return out


def main() -> int:
    light = json.loads(LIGHT.read_text(encoding="utf-8"))
    t2 = json.loads(T2.read_text(encoding="utf-8"))
    old = json.loads(OLD_POOL.read_text(encoding="utf-8")) if OLD_POOL.exists() else {"candidates": []}
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {"companies": {}}
    override_map = {str(code).zfill(6): row for code, row in overrides.get("companies", {}).items()}
    t2_codes = active_t2_codes(t2)
    old_map = {str(x.get("code") or "").zfill(6): x for x in old.get("candidates", []) if x.get("code")}
    screen = light.get("screen_results", {})
    recalled = {str(code).zfill(6) for code, item in screen.items() if item.get("status") in {"pass", "uncertain"}}
    now = datetime.now(TZ).isoformat()

    deep_results = {}
    active = []
    removed = []
    for code in sorted(recalled):
        item = screen[code]
        metrics = item.get("metrics", {})
        override = override_map.get(code)
        q3 = bool(metrics.get("q3_positive_forecast"))
        if override:
            direction = override.get("direction", "uncertain")
            confidence = override.get("confidence", "medium")
            evidence = override.get("evidence", [])
            driver = override.get("forward_driver")
            transmission = override.get("transmission_chain")
            invalidation = override.get("invalidation_condition")
            is_active = direction in {"up", "inflection_up"} and bool(driver and transmission and invalidation and evidence)
            reason = "manual/independent forward-evidence override"
        elif q3:
            direction = "up"
            confidence = "medium"
            evidence = [item.get("reason")]
            driver = "公司已披露2026年前三季度正向盈利预期/预告"
            transmission = "公司经营推进与业务增长 → 2026前三季度利润同比增长 → 下一季度盈利方向保持向上"
            invalidation = "后续正式业绩明显低于预告区间或公司撤回/下修盈利预期"
            is_active = True
            reason = "explicit positive Q3 forecast"
        else:
            direction = "uncertain"
            confidence = "low"
            evidence = [item.get("reason")]
            driver = None
            transmission = None
            invalidation = None
            is_active = False
            reason = "H1/环比数据只触发宽召回，但缺少独立未来1-2季度领先变量证据"

        deep_results[code] = {
            "name": item.get("name"),
            "light_status": item.get("status"),
            "direction": direction,
            "confidence": confidence,
            "forward_driver": driver,
            "transmission_chain": transmission,
            "evidence": evidence,
            "invalidation_condition": invalidation,
            "covered_by_t2": code in t2_codes,
            "active_in_weekly_pool": is_active,
            "reason": reason,
        }
        if is_active:
            old_row = old_map.get(code)
            active.append({
                "code": code,
                "name": item.get("name"),
                "first_added_date": (old_row or {}).get("first_added_date") or "2026-08-30",
                "last_review_date": "2026-08-30",
                "status": "继续保留" if old_row else "新发现",
                "earnings_direction": "向上" if direction == "up" else "拐点向上",
                "earnings_driver": driver,
                "evidence": evidence,
                "key_validation_metric": override.get("key_validation_metric") if override else "正式Q3业绩相对预告区间的兑现度",
                "invalidation_condition": invalidation,
                "industry_t2_tag": "T2重合" if code in t2_codes else "非T2周度补漏",
                "source_summary": reason,
            })

    active_codes = {x["code"] for x in active}
    for code, row in old_map.items():
        if code not in active_codes:
            removed.append({
                "code": code,
                "name": row.get("name"),
                "removal_reason": "迁移到新Skill基线后，当前全市场宽召回/未来盈利深验未同时满足正式active条件；旧池仅保留为历史证据，不自动继承。",
            })

    payload = {
        "schema_version": 1,
        "t2_recall_frozen_at": t2.get("t2_recall_frozen_at"),
        "weekly_pool_read_at": now,
        "universe_count": light.get("universe_count"),
        "screened_count": light.get("screened_count"),
        "screen_results": screen,
        "deep_verified_codes": sorted(recalled),
        "deep_results": deep_results,
        "pool_active_codes": sorted(active_codes),
        "removed_codes": removed,
        "industry_state_modified": False,
        "source_status": light.get("source_status", {}),
    }
    pool = {
        "schema_version": 2,
        "pool_name": "A股周度全市场盈利机会池",
        "purpose": "新Skill基线：主板全集机械宽召回后，仅保留未来1-2季度盈利方向有独立可验证前瞻证据的公司。周度池只补公司，不反向影响产业景气状态。",
        "generated_at": now,
        "scan_as_of": "2026-08-30",
        "market_trade_date": "2026-08-28",
        "scan_mode": "skill_v3_clean_baseline",
        "universe_count": light.get("universe_count"),
        "light_recall_count": len(recalled),
        "active_count": len(active),
        "candidates": active,
        "removed_legacy_candidates": removed,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    POOL.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"ok","universe":light.get("universe_count"),"recalled":len(recalled),"active":len(active),"removed_legacy":len(removed)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
