from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RECALL = ROOT / "data/research/pipeline/t2_company_recall.json"
WEEKLY = ROOT / "data/research/weekly_fundamental_opportunity_pool.json"
LIGHT = ROOT / "data/research/pipeline/weekly_light_recall.json"
INDUSTRY = ROOT / "data/research/pipeline/industry_scan.json"
LATEST = ROOT / "data/latest.json"
REP_POLICY = ROOT / "config/t2_representative_policy.json"
EXPOSURE_RULES = ROOT / "config/t2_exposure_rules.json"
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


def normalized_log_metric(value, bounds: list[float]) -> float:
    if not isinstance(value, (int, float)) or value <= 0 or not isinstance(bounds, list) or len(bounds) != 2:
        return 0.0
    lo, hi = float(bounds[0]), float(bounds[1])
    if lo <= 0 or hi <= lo:
        return 0.0
    clipped = max(lo, min(hi, float(value)))
    return (math.log10(clipped) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))


def representative_score(metrics: dict, policy: dict) -> float:
    ranking = policy.get("ranking", {})
    weights = ranking.get("weights", {})
    caps = ranking.get("normalization_caps", {})
    score = 0.0
    score += float(weights.get("net_profit_scale", 0.0)) * normalized_log_metric(
        metrics.get("net_profit"), caps.get("net_profit_scale", [1e8, 3e10])
    )
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


def chain_cap(pass_count: int, mode: str, policy: dict) -> int:
    if mode == "conditional_t1":
        return max(0, int(policy.get("conditional_t1", {}).get("max_companies_in_common_pool_per_subchain", 1)))
    return representative_cap(pass_count, policy)


def rank_chain_candidates(codes: list[str], gate: dict, policy: dict, weekly_codes: set[str]) -> list[str]:
    weekly_priority = bool(policy.get("weekly_deep_review", {}).get("priority_within_recalled_subchain", True))

    def key(code: str):
        metrics = gate[code].get("metrics") or {}
        weekly_rank = 0 if (weekly_priority and code in weekly_codes) else 1
        return (
            weekly_rank,
            -representative_score(metrics, policy),
            -number(metrics.get("net_profit"), -1e18),
            -number(metrics.get("net_profit_yoy_pct"), -1e9),
            -number(metrics.get("revenue_yoy_pct"), -1e9),
            code,
        )

    return sorted(codes, key=key)


def earnings_gate_pass(metrics: dict, name: str, gate_policy: dict) -> bool:
    profit = metrics.get("net_profit")
    if gate_policy.get("profit_must_be_positive", True) and not (isinstance(profit, (int, float)) and profit > 0):
        return False
    if gate_policy.get("exclude_st", True) and "ST" in str(name).upper():
        return False

    revenue_yoy = metrics.get("revenue_yoy_pct")
    profit_yoy = metrics.get("net_profit_yoy_pct")
    profit_qoq = metrics.get("net_profit_qoq_pct")
    yoy = gate_policy.get("yoy_path", {})
    qoq = gate_policy.get("qoq_path", {})

    yoy_ok = (
        isinstance(profit_yoy, (int, float))
        and isinstance(revenue_yoy, (int, float))
        and profit_yoy >= float(yoy.get("net_profit_yoy_pct_min", 15))
        and revenue_yoy >= float(yoy.get("revenue_yoy_pct_min", 5))
    )
    qoq_ok = (
        isinstance(profit_qoq, (int, float))
        and isinstance(revenue_yoy, (int, float))
        and profit_qoq >= float(qoq.get("net_profit_qoq_pct_min", 20))
        and revenue_yoy >= float(qoq.get("revenue_yoy_pct_min", 0))
    )
    return yoy_ok or qoq_ok


def industry_status_map(scan: dict) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for industry in scan.get("broad_industries", []):
        broad = industry.get("id")
        for row in industry.get("subchains", []):
            if broad and row.get("name"):
                out[(broad, row.get("name"))] = row.get("status")
    return out


def build_reverse_trigger_audit(light: dict, scan: dict, exposure_rules: dict, policy: dict, stocks: dict) -> dict:
    statuses = industry_status_map(scan)
    screen = light.get("screen_results", {})
    gate_policy = policy.get("earnings_gate", {}).get("unconfirmed_reverse_trigger", {})
    allowed_screen_statuses = set(gate_policy.get("screen_statuses", ["pass"]))
    qoq_policy = gate_policy.get("qoq_path", {})
    qoq_min = float(qoq_policy.get("net_profit_qoq_pct_min", 50))
    revenue_min = float(qoq_policy.get("revenue_yoy_pct_min", 0))
    rows: dict[str, dict] = {}

    for rule in exposure_rules.get("unconfirmed_reverse_trigger_rules", []):
        key = (rule.get("broad_industry_id"), rule.get("subchain"))
        if statuses.get(key) != "unconfirmed":
            continue
        trigger_universe_policy = rule.get("trigger_universe_policy") or "configured_trigger_company_codes"
        if trigger_universe_policy == "all_currently_verified_explicit_exposed":
            raw_codes = rule.get("explicit_exposed", [])
        else:
            raw_codes = rule.get("trigger_company_codes", [])
        trigger_codes = sorted({str(code).zfill(6) for code in raw_codes if code})
        triggers = []
        for code in trigger_codes:
            screen_row = screen.get(code) or {}
            metrics = screen_row.get("metrics") or {}
            name = screen_row.get("name") or (stocks.get(code) or {}).get("name") or code
            profit = metrics.get("net_profit")
            qoq = metrics.get("net_profit_qoq_pct")
            revenue = metrics.get("revenue_yoy_pct")
            is_st = "ST" in str(name).upper()
            direct_screen_trigger = screen_row.get("status") in allowed_screen_statuses
            qoq_trigger = (
                isinstance(profit, (int, float)) and profit > 0
                and not is_st
                and isinstance(qoq, (int, float)) and qoq >= qoq_min
                and isinstance(revenue, (int, float)) and revenue >= revenue_min
            )
            triggered = direct_screen_trigger or qoq_trigger
            triggers.append({
                "code": code,
                "name": name,
                "screen_status": screen_row.get("status"),
                "screen_reason": screen_row.get("reason"),
                "metrics": metrics,
                "triggered": triggered,
                "trigger_reason": (
                    "full-market light screen already shows strong earnings transmission"
                    if direct_screen_trigger
                    else "latest-quarter profit acceleration is strong enough to require subchain re-review"
                    if qoq_trigger
                    else "company signal is not strong enough to reopen the unconfirmed subchain"
                ),
            })
        review_required = any(r["triggered"] for r in triggers)
        tag = f"{key[0]}::{key[1]}"
        rows[tag] = {
            "industry_status": "unconfirmed",
            "review_status": "review_required" if review_required else "no_trigger",
            "value_chain_link": rule.get("value_chain_link"),
            "review_variables": rule.get("review_variables", []),
            "trigger_universe_policy": trigger_universe_policy,
            "trigger_universe_count": len(trigger_codes),
            "trigger_companies": triggers,
            "rule": "All currently verified exposed companies for this configured unconfirmed chain are screened for strong earnings anomalies. A trigger only reopens industry evidence review; it does not auto-promote the subchain or auto-admit any company to the common pool.",
        }
    return rows


def main() -> int:
    recall = load(RECALL)
    weekly = load(WEEKLY)
    light = load(LIGHT)
    industry = load(INDUSTRY)
    latest = load(LATEST)
    rep_policy = load(REP_POLICY)
    exposure_rules = load(EXPOSURE_RULES)
    now = datetime.now(TZ).isoformat()

    all_tags_by_code: dict[str, list[str]] = {}
    t2_tags: dict[str, list[str]] = {}
    t1_tags: dict[str, list[str]] = {}
    exposure: dict[str, list[str]] = {}
    tag_modes: dict[str, str] = {}

    for chain in recall.get("t2_subchains", []):
        tag = f"{chain.get('broad_industry_id')}::{chain.get('subchain')}"
        industry_status = chain.get("industry_status") or "T2"
        mode = chain.get("recall_mode") or ("direct_t2" if industry_status == "T2" else "conditional_t1")
        tag_modes[tag] = mode
        for code, item in (chain.get("classifications") or {}).items():
            code = str(code).zfill(6)
            if isinstance(item, dict) and item.get("status") == "exposed":
                all_tags_by_code.setdefault(code, []).append(tag)
                (t2_tags if mode == "direct_t2" else t1_tags).setdefault(code, []).append(tag)
                if item.get("reason"):
                    exposure.setdefault(code, []).append(str(item.get("reason")))
        for row in chain.get("cross_industry_discoveries", []) or []:
            code = str(row.get("code") or "").zfill(6)
            if code:
                all_tags_by_code.setdefault(code, []).append(tag)
                (t2_tags if mode == "direct_t2" else t1_tags).setdefault(code, []).append(tag)
                exposure.setdefault(code, []).append(str(row.get("exposure_summary") or "cross-industry verified exposure"))

    recall_codes = set(all_tags_by_code)
    weekly_rows = {
        str(row.get("code")).zfill(6): row
        for row in weekly.get("candidates", [])
        if row.get("status") != "移除"
    }
    weekly_codes = set(weekly_rows)
    overlap = recall_codes & weekly_codes
    merged = recall_codes | weekly_codes
    screen = light.get("screen_results", {})
    stocks = latest.get("stocks", {})
    gate_policy = rep_policy.get("earnings_gate", {})

    gate: dict[str, dict] = {}
    earnings_passed: list[str] = []
    for code in sorted(merged):
        tags = sorted(set(all_tags_by_code.get(code, [])))
        direct_tags = sorted(set(t2_tags.get(code, [])))
        conditional_tags = sorted(set(t1_tags.get(code, [])))
        if code in overlap:
            source = "both"
        elif code in weekly_codes:
            source = "weekly"
        elif direct_tags:
            source = "T2-subchain"
        else:
            source = "T1-conditional"

        name = (stocks.get(code) or {}).get("name") or (weekly_rows.get(code) or {}).get("name") or code
        metrics = (screen.get(code) or {}).get("metrics") or {}
        weekly_row = weekly_rows.get(code)

        if weekly_row:
            status = "pass"
            reason = "周度全市场深验已验证未来1-2季度盈利桥。"
            bridge = weekly_row.get("forward_bridge")
            invalidation = weekly_row.get("invalidation_condition")
            gate_mode = "weekly_deep_review"
        elif direct_tags:
            gate_mode = "direct_t2"
            sufficient = earnings_gate_pass(metrics, name, gate_policy.get("direct_t2", {}))
            if sufficient:
                status = "pass"
                reason = "冻结T2直接盈利链仍有效，且公司H1/Q2主营盈利传导达到T2公司级门槛。"
                driver = " / ".join(direct_tags)
                bridge = f"冻结T2领先变量({driver}) → 公司已验证的直接业务暴露 → 当前收入/利润传导为正 → 若T2链不降级，未来1-2季度盈利方向保持向上。"
                invalidation = "对应T2细分链降级/失效，或公司后续收入、利润率、订单/产销出现与产业链方向相反的明显恶化。"
            else:
                status = "reject"
                reason = "虽然属于冻结T2直接链召回，但本轮公司级H1/Q2盈利传导不足、亏损、ST或缺少可验证财务桥；不能仅靠行业T2自动通过。"
                bridge = None
                invalidation = None
        else:
            gate_mode = "conditional_t1"
            sufficient = earnings_gate_pass(metrics, name, gate_policy.get("conditional_t1", {}))
            if sufficient:
                status = "pass"
                reason = "产业链仍为T1，但公司H1/Q2盈利传导达到更严格的条件召回门槛；允许进入单代表竞争，不代表产业链已升级为T2。"
                driver = " / ".join(conditional_tags)
                bridge = f"T1产业链({driver})尚未完全确认 → 公司自身盈利传导显著强于行业最低证据 → 仅以条件候选进入后续筛选；行业升级仍需独立证据。"
                invalidation = "公司盈利传导减弱，或对应T1链进一步恶化/降级，则条件资格立即失效。"
            else:
                status = "reject"
                reason = "公司属于T1条件召回链，但未达到高于T2普通门槛的公司级确认标准；保留召回审计，不进入正式共同池。"
                bridge = None
                invalidation = None

        gate[code] = {
            "code": code,
            "name": name,
            "source": source,
            "gate_mode": gate_mode,
            "recall_tags": tags,
            "t2_tags": direct_tags,
            "conditional_t1_tags": conditional_tags,
            "recall_exposure": exposure.get(code, []),
            "metrics": metrics,
            "gate_status": status,
            "reason": reason,
            "forward_bridge": bridge,
            "invalidation_condition": invalidation,
        }
        if status == "pass":
            earnings_passed.append(code)

    earnings_passed_set = set(earnings_passed)
    all_tags = sorted({tag for code in earnings_passed for tag in all_tags_by_code.get(code, [])})
    chain_passers = {
        tag: sorted(code for code in earnings_passed if tag in all_tags_by_code.get(code, []))
        for tag in all_tags
    }
    chain_caps = {tag: chain_cap(len(codes), tag_modes.get(tag, "direct_t2"), rep_policy) for tag, codes in chain_passers.items()}

    # Weekly-only names with no active recall tag are independent discoveries and remain eligible.
    selected: set[str] = {
        code for code in earnings_passed
        if code in weekly_codes and not all_tags_by_code.get(code)
    }

    def selected_count(tag: str) -> int:
        return sum(1 for code in selected if tag in all_tags_by_code.get(code, []))

    # Direct T2 chains get priority over conditional T1 chains. T1 can never crowd a T2
    # representative out through a cross-tag cap interaction.
    processing_order = sorted(
        all_tags,
        key=lambda tag: (0 if tag_modes.get(tag) == "direct_t2" else 1, -len(chain_passers[tag]), tag),
    )
    for tag in processing_order:
        cap = chain_caps[tag]
        open_slots = max(0, cap - selected_count(tag))
        if open_slots <= 0:
            continue
        ranked = rank_chain_candidates(
            [code for code in chain_passers[tag] if code not in selected],
            gate,
            rep_policy,
            weekly_codes,
        )
        added = 0
        for code in ranked:
            if added >= open_slots:
                break
            violates_other_chain = False
            for other_tag in all_tags_by_code.get(code, []):
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
    t2_chain_audit: dict[str, dict] = {}
    t1_chain_audit: dict[str, dict] = {}
    for tag in all_tags:
        ranked_all = rank_chain_candidates(chain_passers[tag], gate, rep_policy, weekly_codes)
        selected_in_chain = sorted(code for code in passed if tag in all_tags_by_code.get(code, []))
        weekly_in_chain = sorted(code for code in selected_in_chain if code in weekly_codes)
        selected_nonweekly = [code for code in selected_in_chain if code not in weekly_codes]
        deferred = [code for code in ranked_all if code not in selected]
        audit_row = {
            "recall_mode": tag_modes.get(tag, "direct_t2"),
            "earnings_gate_pass_count": len(chain_passers[tag]),
            "representative_cap": chain_caps[tag],
            "selected_count": len(selected_in_chain),
            "weekly_deep_review_selected_codes": weekly_in_chain,
            "selected_nonweekly_codes": selected_nonweekly,
            "deferred_codes": deferred,
            "ranked_all_codes": ranked_all,
            "selection_scores": {
                code: round(representative_score(gate[code].get("metrics") or {}, rep_policy), 6)
                for code in ranked_all
            },
        }
        (t2_chain_audit if tag_modes.get(tag) == "direct_t2" else t1_chain_audit)[tag] = audit_row
        if len(selected_in_chain) > chain_caps[tag]:
            raise RuntimeError(f"representative cap violated:{tag}:{len(selected_in_chain)}>{chain_caps[tag]}")

    for code, row in gate.items():
        if row.get("gate_status") != "pass":
            row["representative_selection_status"] = "not_eligible"
            row["final_pool_status"] = "reject"
            continue
        if code in selected:
            if code in weekly_codes and not all_tags_by_code.get(code):
                status = "weekly_independent_kept"
                selected_via = ["weekly_deep_review"]
            elif code in weekly_codes:
                status = "weekly_priority_recalled_representative"
                selected_via = ["weekly_deep_review"] + all_tags_by_code.get(code, [])
            elif row.get("conditional_t1_tags") and not row.get("t2_tags"):
                status = "selected_conditional_t1_representative"
                selected_via = row.get("conditional_t1_tags", [])
            else:
                status = "selected_t2_representative"
                selected_via = row.get("t2_tags", [])
            row["representative_selection_status"] = status
            row["selected_via"] = sorted(set(selected_via))
            row["final_pool_status"] = "pass"
        else:
            row["representative_selection_status"] = rep_policy.get("output_policy", {}).get(
                "deferred_status", "deferred_by_subchain_diversification"
            )
            row["selected_via"] = []
            row["final_pool_status"] = "deferred"
            row["representative_selection_reason"] = (
                "公司已通过对应召回模式的未来盈利门槛，但所在细分链已有更强代表公司占用正式候选名额；"
                "保留在宽召回审计中，不进入共同资格池。"
            )

    reverse_trigger_audit = build_reverse_trigger_audit(light, industry, exposure_rules, rep_policy, stocks)
    review_required_tags = sorted(tag for tag, row in reverse_trigger_audit.items() if row.get("review_status") == "review_required")

    earnings_gate_removals = len(merged) - len(earnings_passed_set)
    representative_deferrals = len(earnings_passed_set) - len(passed)
    t2_recall_codes = set(t2_tags)
    t1_recall_codes = set(t1_tags)
    arithmetic = {
        "recall_unique_count": len(recall_codes),
        "direct_t2_recall_unique_count": len(t2_recall_codes),
        "conditional_t1_recall_unique_count": len(t1_recall_codes),
        "weekly_pool_effective_count": len(weekly_codes),
        "overlap_count": len(overlap),
        "merged_pre_gate_count": len(merged),
        "future_earnings_gate_removals": earnings_gate_removals,
        "future_earnings_gate_pass_count": len(earnings_passed_set),
        "representative_selection_deferrals": representative_deferrals,
        "common_qualification_pool_count": len(passed),
        "unconfirmed_reverse_review_required_count": len(review_required_tags),
        # Legacy key retained for downstream diagnostics that have not yet migrated.
        "t2_recall_unique_count": len(t2_recall_codes),
    }
    if arithmetic["recall_unique_count"] + arithmetic["weekly_pool_effective_count"] - arithmetic["overlap_count"] != arithmetic["merged_pre_gate_count"]:
        raise RuntimeError("merge reconciliation failed")
    if arithmetic["merged_pre_gate_count"] - arithmetic["future_earnings_gate_removals"] != arithmetic["future_earnings_gate_pass_count"]:
        raise RuntimeError("earnings gate reconciliation failed")
    if arithmetic["future_earnings_gate_pass_count"] - arithmetic["representative_selection_deferrals"] != arithmetic["common_qualification_pool_count"]:
        raise RuntimeError("representative selection reconciliation failed")

    payload = {
        "schema_version": 3,
        "generated_at": now,
        "t2_recall_frozen_at": recall.get("t2_recall_frozen_at"),
        "weekly_pool_generated_at": weekly.get("generated_at"),
        "representative_policy_reviewed_at": rep_policy.get("reviewed_at"),
        "representative_policy_schema_version": rep_policy.get("schema_version"),
        "arithmetic": arithmetic,
        "overlap_codes": sorted(overlap),
        "merged_pre_gate_codes": sorted(merged),
        "future_earnings_gate": gate,
        "t2_representative_selection": t2_chain_audit,
        "conditional_t1_representative_selection": t1_chain_audit,
        "unconfirmed_reverse_trigger_audit": reverse_trigger_audit,
        "unconfirmed_review_required_tags": review_required_tags,
        "common_pool_codes": passed,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", **arithmetic, "review_required_tags": review_required_tags}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
