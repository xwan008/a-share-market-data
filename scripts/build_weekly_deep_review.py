from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data/research/pipeline/weekly_manual_review_queue.json"
LIGHT = ROOT / "data/research/pipeline/weekly_light_recall.json"
OLD_POOL = ROOT / "data/research/weekly_fundamental_opportunity_pool.json"
OVERRIDES = ROOT / "config/weekly_deep_review_overrides_20260830.json"
T2_RECALL = ROOT / "data/research/pipeline/t2_company_recall.json"
OUT_REVIEW = ROOT / "data/research/pipeline/weekly_deep_review.json"
OUT_SCAN = ROOT / "data/research/pipeline/weekly_opportunity_scan.json"
OUT_POOL = OLD_POOL
TZ = ZoneInfo("Asia/Shanghai")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    queue = load(QUEUE)
    light = load(LIGHT)
    old_pool = load(OLD_POOL)
    overrides = load(OVERRIDES)
    t2 = load(T2_RECALL)
    now = datetime.now(TZ).isoformat()

    old_by_code = {str(x.get("code")).zfill(6): x for x in old_pool.get("candidates", [])}
    active_cfg = overrides.get("active", {})
    explicit_remove = overrides.get("explicit_remove", {})

    t2_tags: dict[str, list[str]] = {}
    for chain in t2.get("t2_subchains", []):
        tag = f"{chain.get('broad_industry_id')}::{chain.get('subchain')}"
        for code, item in (chain.get("classifications") or {}).items():
            if isinstance(item, dict) and item.get("status") == "exposed":
                t2_tags.setdefault(str(code).zfill(6), []).append(tag)
        for row in chain.get("cross_industry_discoveries", []) or []:
            code = str(row.get("code") or "").zfill(6)
            if code:
                t2_tags.setdefault(code, []).append(tag)

    reviews = {}
    active_codes = []
    for item in queue.get("queue", []):
        code = str(item.get("code")).zfill(6)
        name = item.get("name") or code
        metrics = item.get("metrics") or {}
        if code in active_cfg:
            cfg = active_cfg[code]
            reviews[code] = {
                "code": code,
                "name": name,
                "deep_status": "pass",
                "earnings_direction": cfg["earnings_direction"],
                "earnings_driver": cfg["earnings_driver"],
                "forward_bridge": cfg["forward_bridge"],
                "supporting_evidence": cfg.get("evidence", []),
                "counter_evidence": cfg.get("counter_evidence", []),
                "one_off_profit_impact": cfg["one_off_profit_impact"],
                "key_validation_metric": cfg["key_validation_metric"],
                "invalidation_condition": cfg["invalidation_condition"],
                "sources": cfg.get("sources", []),
                "light_metrics": metrics,
                "t2_tags": sorted(set(t2_tags.get(code, []))),
            }
            active_codes.append(code)
        else:
            reason = explicit_remove.get(code) or (
                "本轮仅验证到H1历史高增长/环比改善，未验证到足以支撑未来1-2季度利润继续向上或明确拐点的独立订单、价格、产销、指引或利用率证据；按规则不进入正式周度池。"
            )
            reviews[code] = {
                "code": code,
                "name": name,
                "deep_status": "reject",
                "earnings_direction": "unverified",
                "earnings_driver": None,
                "forward_bridge": None,
                "supporting_evidence": [item.get("light_reason")],
                "counter_evidence": [reason],
                "one_off_profit_impact": "未完成可验证的前瞻盈利桥，H1高增可能包含低基数、重组、公允价值、投资收益或周期价格等因素，不能直接外推。",
                "key_validation_metric": "待后续出现明确Q3/Q4订单、价格、产销、指引或其他前瞻变量后重新进入深验。",
                "invalidation_condition": "不适用；当前结论为不纳入。",
                "sources": [],
                "light_metrics": metrics,
                "t2_tags": sorted(set(t2_tags.get(code, []))),
            }

    active_codes = sorted(set(active_codes))
    deep_codes = sorted(reviews)

    pool_candidates = []
    for code in active_codes:
        review = reviews[code]
        old = old_by_code.get(code)
        status = "继续保留" if old and old.get("status") != "移除" else "新发现"
        first_added = old.get("first_added_date") if old else "2026-08-30"
        pool_candidates.append({
            "code": code,
            "name": review["name"],
            "first_added_date": first_added,
            "last_review_date": "2026-08-30",
            "status": status,
            "earnings_direction": review["earnings_direction"],
            "earnings_driver": review["earnings_driver"],
            "evidence": review["supporting_evidence"],
            "key_validation_metric": review["key_validation_metric"],
            "invalidation_condition": review["invalidation_condition"],
            "industry_t2_tag": review["t2_tags"] if review["t2_tags"] else ["weekly_only"],
            "source_summary": "2026-08-30 full-market weekly deep review after independent T2 freeze",
            "forward_bridge": review["forward_bridge"],
            "one_off_profit_impact": review["one_off_profit_impact"],
            "sources": review["sources"],
        })

    removed_codes = []
    for code, old in old_by_code.items():
        if old.get("status") == "移除" or code in active_codes:
            continue
        if code not in reviews:
            continue
        removed_codes.append(code)
        row = dict(old)
        row["last_review_date"] = "2026-08-30"
        row["status"] = "移除"
        row["removal_reason"] = explicit_remove.get(code) or reviews[code]["counter_evidence"][0]
        row["industry_t2_tag"] = reviews[code]["t2_tags"] if reviews[code]["t2_tags"] else row.get("industry_t2_tag")
        pool_candidates.append(row)

    pool_candidates.sort(key=lambda x: (x.get("status") == "移除", x["code"]))

    review_payload = {
        "schema_version": 1,
        "generated_at": now,
        "queue_count": len(deep_codes),
        "deep_verified_count": len(deep_codes),
        "active_count": len(active_codes),
        "rejected_count": len(deep_codes) - len(active_codes),
        "active_codes": active_codes,
        "reviews": reviews,
        "industry_state_modified": False,
    }

    scan_payload = {
        "schema_version": 1,
        "generated_at": now,
        "t2_recall_frozen_at": t2.get("t2_recall_frozen_at"),
        "weekly_pool_read_at": now,
        "universe_count": light.get("universe_count"),
        "screened_count": light.get("screened_count"),
        "screen_results": light.get("screen_results", {}),
        "deep_verified_codes": deep_codes,
        "pool_active_codes": active_codes,
        "removed_codes": sorted(removed_codes),
        "industry_state_modified": False,
        "deep_review_file": str(OUT_REVIEW.relative_to(ROOT)),
    }

    new_pool = {
        "schema_version": 2,
        "pool_name": "A股周度全市场盈利机会池",
        "purpose": "独立于产业T2的公司级补漏召回层；只保留未来1-2季度盈利向上或明确拐点且有可验证前瞻桥的公司。",
        "universe": old_pool.get("universe", {}),
        "market_data_source": old_pool.get("market_data_source", {}),
        "selection_principle": "全主板机械宽召回后深验；历史高增本身不构成准入。周期资源公司必须让当前商品锚支持未来盈利方向。",
        "required_fields_per_candidate": old_pool.get("required_fields_per_candidate", []),
        "allowed_status": old_pool.get("allowed_status", ["新发现", "继续保留", "盈利强化", "盈利转弱", "移除"]),
        "generated_at": now,
        "scan_as_of": "2026-08-30",
        "market_trade_date": "2026-08-28",
        "scan_mode": "full_market_mechanical_recall_plus_deep_review",
        "audit": {
            "universe_count": light.get("universe_count"),
            "light_recall_count": sum(1 for x in light.get("screen_results", {}).values() if x.get("status") in {"pass", "uncertain"}),
            "deep_review_count": len(deep_codes),
            "active_count": len(active_codes),
            "removed_legacy_count": len(removed_codes),
            "industry_state_modified": False,
            "t2_recall_frozen_at": t2.get("t2_recall_frozen_at"),
        },
        "candidates": pool_candidates,
    }

    OUT_REVIEW.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SCAN.write_text(json.dumps(scan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_POOL.write_text(json.dumps(new_pool, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "queue": len(deep_codes),
        "active": len(active_codes),
        "removed_legacy": sorted(removed_codes),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
