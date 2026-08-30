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
REP_POLICY = ROOT / "config/t2_representative_policy.json"
OUT = ROOT / "data/research/pipeline/common_qualification_pool.json"
TZ = ZoneInfo("Asia/Shanghai")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def number(value, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def normalized_metric(value, bounds: list[float]) -> float:
    if not isinstance(value, (int, float)) or not isinstance(bounds, list) or len(bounds) != 2:
        return 0.0
    lo, hi = float(bounds[0]), float(bounds[1])
    if hi <= lo:
        return 0.0
    clipped = max(lo, min(hi, float(value)))
    return (clipped - lo) / (hi - lo)


def representative_score(metrics: dict, policy: dict) -> float:
    ranking = policy.get("ranking", {})
    weights = ranking.get("weights", {})
    caps = ranking.get("normalization_caps", {})
    score = 0.0
    for key in ("net_profit_yoy_pct", "revenue_yoy_pct", "net_profit_qoq_pct"):
        score += float(weights.get(key, 0.0)) * normalized_metric(metrics.get(key), caps.get(key, [0, 1]))
    score += float(weights.get("q3_positive_forecast", 0.0)) * (1.0 if metrics.get("q3_positive_forecast") else 0.0)
    return score


def representative_cap(pass_count: int, policy: dict) -> int:
    for rule in policy.get("cap_rules", []):
        maximum = int(rule.get("max_earnings_gate_passers", 0))
        cap = int(rule.get("max_companies_in_common_pool", 0))
        if pass_count <= maximum:
            return max(0, cap)
    raise RuntimeError(f"no representative cap rule for pass_count={pass_count}")


def rank_chain_candidates(codes: list[str], gate: dict, policy: dict) -> list[str]:
    def key(code: str):
        metrics = gate[code].get("metrics") or {}
        return (
            -representative_score(metrics, policy),
            -number(metrics.get("net_profit_yoy_pct"), -1e9),
            -number(metrics.get("revenue_yoy_pct"), -1e9),
            -number(metrics.get("net_profit"), -1e18),
            code,
        )

    return sorted(codes, key=key)


def main() -> int:
    t2 = load(T2)
    weekly = load(WEEKLY)
    light = load(LIGHT)
    latest = load(LATEST)
    rep_policy = load(REP_POLICY)
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

    gate: dict[str, dict] = {}
    earnings_passed: list[str] = []
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
            earnings_passed.append(code)

    # T2 recall remains intentionally broad. Only after the company earnings gate do we select
    # a small number of representatives per T2 subchain for the formal common pool.
    earnings_passed_set = set(earnings_passed)
    all_tags = sorted({tag for code in earnings_passed for tag in t2_tags.get(code, [])})
    chain_passers = {
        tag: sorted(code for code in earnings_passed if tag in t2_tags.get(code, []))
        for tag in all_tags
    }
    chain_caps = {tag: representative_cap(len(codes), rep_policy) for tag, codes in chain_passers.items()}

    # Weekly deep-review names are independently validated and remain eligible, but they consume
    # the same subchain capacity. If weekly review alone exceeds a cap, keep them and expose the
    # overflow in the audit instead of silently deleting a deep-reviewed company.
    selected: set[str] = {code for code in earnings_passed if code in weekly_codes}
    counts_toward_cap = bool(rep_policy.get("weekly_deep_review", {}).get("counts_toward_subchain_cap", True))

    def selected_count(tag: str) -> int:
        return sum(1 for code in selected if tag in t2_tags.get(code, []))

    # Process the broadest chains first so a large homogeneous chain (e.g. brokers) cannot be
    # repopulated indirectly by multi-tag companies selected later from smaller chains.
    processing_order = sorted(all_tags, key=lambda tag: (-len(chain_passers[tag]), tag))
    for tag in processing_order:
        cap = chain_caps[tag]
        current_used = selected_count(tag) if counts_toward_cap else 0
        open_slots = max(0, cap - current_used)
        if open_slots <= 0:
            continue
        ranked = rank_chain_candidates(
            [code for code in chain_passers[tag] if code not in selected and code not in weekly_codes],
            gate,
            rep_policy,
        )
        added = 0
        for code in ranked:
            if added >= open_slots:
                break
            # Global multi-tag guard: selecting this company must not overfill any T2 chain it
            # belongs to. Weekly overflows are the only allowed cap exception.
            violates_other_chain = False
            for other_tag in t2_tags.get(code, []):
                if other_tag not in chain_caps:
                    continue
                if selected_count(other_tag) >= chain_caps[other_tag]:
                    violates_other_chain = True
                    break
            if violates_other_chain:
                continue
            selected.add(code)
            added += 1

    passed = sorted(selected)
    chain_audit: dict[str, dict] = {}
    for tag in all_tags:
        ranked_all = rank_chain_candidates(
            [code for code in chain_passers[tag] if code not in weekly_codes], gate, rep_policy
        )
        selected_in_chain = sorted(code for code in passed if tag in t2_tags.get(code, []))
        weekly_in_chain = sorted(code for code in selected_in_chain if code in weekly_codes)
        selected_t2_only = [code for code in selected_in_chain if code not in weekly_codes]
        deferred = [code for code in ranked_all if code not in selected]
        overflow = max(0, len(selected_in_chain) - chain_caps[tag])
        chain_audit[tag] = {
            "earnings_gate_pass_count": len(chain_passers[tag]),
            "representative_cap": chain_caps[tag],
            "selected_count": len(selected_in_chain),
            "weekly_deep_review_codes": weekly_in_chain,
            "selected_t2_only_codes": selected_t2_only,
            "deferred_t2_only_codes": deferred,
            "weekly_only_cap_overflow": overflow,
            "ranked_t2_only_codes": ranked_all,
            "selection_scores": {
                code: round(representative_score(gate[code].get("metrics") or {}, rep_policy), 6)
                for code in ranked_all
            },
        }
        if overflow and not weekly_in_chain:
            raise RuntimeError(f"representative cap violated without weekly exception:{tag}:{len(selected_in_chain)}>{chain_caps[tag]}")

    for code, row in gate.items():
        if row.get("gate_status") != "pass":
            row["representative_selection_status"] = "not_eligible"
            row["final_pool_status"] = "reject"
            continue
        if code in selected:
            if code in weekly_codes:
                row["representative_selection_status"] = "weekly_deep_review_kept"
                selected_via = ["weekly_deep_review"] + t2_tags.get(code, [])
            else:
                row["representative_selection_status"] = "selected_t2_representative"
                selected_via = t2_tags.get(code, [])
            row["selected_via"] = sorted(set(selected_via))
            row["final_pool_status"] = "pass"
        else:
            row["representative_selection_status"] = rep_policy.get("output_policy", {}).get(
                "deferred_status", "deferred_by_subchain_diversification"
            )
            row["selected_via"] = []
            row["final_pool_status"] = "deferred"
            row["representative_selection_reason"] = (
                "公司已通过未来盈利门槛，但所在T2细分链已有更强代表公司占用正式候选名额；"
                "保留在宽召回审计中，不进入共同资格池。"
            )

    earnings_gate_removals = len(merged) - len(earnings_passed_set)
    representative_deferrals = len(earnings_passed_set) - len(passed)
    arithmetic = {
        "t2_recall_unique_count": len(t2_codes),
        "weekly_pool_effective_count": len(weekly_codes),
        "overlap_count": len(overlap),
        "merged_pre_gate_count": len(merged),
        "future_earnings_gate_removals": earnings_gate_removals,
        "future_earnings_gate_pass_count": len(earnings_passed_set),
        "representative_selection_deferrals": representative_deferrals,
        "common_qualification_pool_count": len(passed),
    }
    if arithmetic["t2_recall_unique_count"] + arithmetic["weekly_pool_effective_count"] - arithmetic["overlap_count"] != arithmetic["merged_pre_gate_count"]:
        raise RuntimeError("merge reconciliation failed")
    if arithmetic["merged_pre_gate_count"] - arithmetic["future_earnings_gate_removals"] != arithmetic["future_earnings_gate_pass_count"]:
        raise RuntimeError("earnings gate reconciliation failed")
    if arithmetic["future_earnings_gate_pass_count"] - arithmetic["representative_selection_deferrals"] != arithmetic["common_qualification_pool_count"]:
        raise RuntimeError("representative selection reconciliation failed")

    payload = {
        "schema_version": 2,
        "generated_at": now,
        "t2_recall_frozen_at": t2.get("t2_recall_frozen_at"),
        "weekly_pool_generated_at": weekly.get("generated_at"),
        "t2_representative_policy_reviewed_at": rep_policy.get("reviewed_at"),
        "arithmetic": arithmetic,
        "overlap_codes": sorted(overlap),
        "merged_pre_gate_codes": sorted(merged),
        "future_earnings_gate": gate,
        "t2_representative_selection": chain_audit,
        "common_pool_codes": passed,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"ok", **arithmetic}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
