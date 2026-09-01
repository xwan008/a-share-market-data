from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/research_pipeline_manifest.json"
ORCH = ROOT / "skills/a-share-low-risk/orchestrator/SKILL.md"
STATE = ROOT / "data/research/v2/research_state.json"
TEST = ROOT / "tests/test_near_miss_ranking_contract.py"


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def pct_gap(a, b, ref):
    if a is None or b is None or ref is None or ref <= 0:
        return None
    return abs(a - b) / ref * 100.0


def distance_to_range(price, rng):
    if price is None or not rng or len(rng) != 2 or price <= 0:
        return None
    lo, hi = num(rng[0]), num(rng[1])
    if lo is None or hi is None:
        return None
    if lo <= price <= hi:
        return 0.0
    if price < lo:
        return (lo - price) / price * 100.0
    return (price - hi) / price * 100.0


def intersection(a, b):
    if not a or not b or len(a) != 2 or len(b) != 2:
        return None
    a0, a1, b0, b1 = map(num, [a[0], a[1], b[0], b[1]])
    if None in {a0, a1, b0, b1}:
        return None
    lo, hi = max(a0, b0), min(a1, b1)
    return [lo, hi] if lo <= hi else None


def range_gap(a, b, ref):
    if not a or not b or len(a) != 2 or len(b) != 2 or ref is None or ref <= 0:
        return None
    a0, a1, b0, b1 = map(num, [a[0], a[1], b[0], b[1]])
    if None in {a0, a1, b0, b1}:
        return None
    if max(a0, b0) <= min(a1, b1):
        return 0.0
    if a1 < b0:
        return (b0 - a1) / ref * 100.0
    return (a0 - b1) / ref * 100.0


manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
contract = {
    "purpose": "在不降低buyable_now硬门槛的前提下，对所有完成估值且非review_required公司计算距可执行买点的可审计距离，避免当前买点为0时输出空白。",
    "eligible_universe": "all complete non-review valuations with buy_point_assessment",
    "review_required_excluded_from_distance_ranking": True,
    "buyable_now_stays_separate": True,
    "must_output_when_eligible_universe_nonempty": True,
    "default_display_limit": 10,
    "research_admission_top_n_forbidden": True,
    "ranking_is_display_only_not_candidate_pool": True,
    "cross_run_persistence_as_pool_forbidden": True,
    "required_metrics": [
        "missing_hard_conditions",
        "value_gap_pct",
        "structure_gap_pct",
        "safe_structure_range_gap_pct",
        "current_to_intersection_pct",
        "blocking_reason",
    ],
    "missing_hard_conditions_definition": [
        "value_eligible=false adds 1",
        "timing_eligible=false adds 1",
        "safe_price_range and structure_entry_range do not intersect adds 1",
        "if the ranges intersect but current price is outside their intersection adds 1",
        "avoid status adds 1 risk-gate penalty",
    ],
    "ranking_order": [
        "avoid_penalty ascending",
        "missing_hard_conditions ascending",
        "safe_structure_range_gap_pct ascending; unavailable sorts last",
        "current_to_intersection_pct ascending; unavailable sorts last",
        "value_gap_pct plus structure_gap_pct ascending; unavailable component sorts last",
        "fundamental comparison score descending only as final tie-breaker",
        "stock_code ascending final deterministic tie-breaker",
    ],
    "interpretation": "rank 1 means closest to satisfying the existing low-risk buy-point rules, not highest expected return and not a recommendation to buy now.",
}
manifest.setdefault("buy_point_contract", {})["near_miss_ranking_contract"] = contract
public = manifest.setdefault("public_output", {})
public["near_miss_section_title"] = "【接近买点榜】"
public["near_miss_limit"] = 10
public["near_miss_must_be_nonempty_when_eligible_universe_nonempty"] = True
public["near_miss_columns"] = [
    "rank",
    "code",
    "name",
    "industry_chain",
    "current_price",
    "safe_price_range",
    "structure_status",
    "structure_entry_range",
    "missing_hard_conditions",
    "value_gap_pct",
    "structure_gap_pct",
    "safe_structure_range_gap_pct",
    "current_to_intersection_pct",
    "blocking_reason",
    "next_trigger",
]
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

orch = ORCH.read_text(encoding="utf-8")
section = r'''
## 接近买点榜（Near-miss Ranking）

【当前低风险买点】继续只允许 `buy_point_status=buyable_now`，不得为了凑榜降低价值、安全边际、结构或交集门槛。

但只要存在完成估值且非 `review_required` 的公司，每次正式输出都必须同时生成【接近买点榜】，默认展示前10名；即使当前买点为0，也不得只输出空列表或一句“暂无买点”。该榜只做当期展示排序，不得持久化为候选池、机会池或下一轮发现种子。

对全部完成估值且非review公司计算：
- `missing_hard_conditions`：`value_eligible=false` +1；`timing_eligible=false` +1；安全价区与结构入场区无交集 +1；若已有交集但当前价不在交集内 +1；`avoid` 额外 +1风险门惩罚。
- `value_gap_pct`：当前价高于安全价上沿时，计算降到安全价上沿所需百分比；已满足价值条件则为0。
- `structure_gap_pct`：当前价距离独立 `structure_entry_range` 最近边界的百分比；已位于结构入场区则为0；无有效结构入场区则记为不可测并排在可测者之后。
- `safe_structure_range_gap_pct`：安全价区与结构入场区不相交时，计算两区间最近边界的百分比距离；已有交集则为0。
- `current_to_intersection_pct`：两区间已有交集时，计算当前价距离交集最近边界的百分比；当前价已在交集内则为0。

固定排序为：`avoid_penalty`升序 → `missing_hard_conditions`升序 → `safe_structure_range_gap_pct`升序（不可测最后） → `current_to_intersection_pct`升序（不可测最后） → `value_gap_pct + structure_gap_pct`升序 → 基本面横比得分降序 → 股票代码升序。

每个上榜公司必须明确写出【当前还缺什么】和【下一触发条件】。第1名只表示“离现有低风险买点规则最近”，不表示预期收益最高，也不等于现在可以买。
'''.strip()
marker = "## Completion Gate"
if "## 接近买点榜（Near-miss Ranking）" not in orch:
    if marker in orch:
        orch = orch.replace(marker, section + "\n\n" + marker, 1)
    else:
        orch += "\n\n" + section + "\n"
ORCH.write_text(orch, encoding="utf-8")

TEST.write_text('''import json\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\ndef test_near_miss_ranking_contract_is_auditable_and_nonempty_by_rule():\n    manifest = json.loads((ROOT / "config/research_pipeline_manifest.json").read_text(encoding="utf-8"))\n    c = manifest["buy_point_contract"]["near_miss_ranking_contract"]\n    assert c["buyable_now_stays_separate"] is True\n    assert c["must_output_when_eligible_universe_nonempty"] is True\n    assert c["review_required_excluded_from_distance_ranking"] is True\n    assert c["ranking_is_display_only_not_candidate_pool"] is True\n    assert c["cross_run_persistence_as_pool_forbidden"] is True\n    assert c["default_display_limit"] == 10\n    assert c["research_admission_top_n_forbidden"] is True\n    assert "missing_hard_conditions" in c["required_metrics"]\n    assert "safe_structure_range_gap_pct" in c["required_metrics"]\n    assert manifest["public_output"]["near_miss_section_title"] == "【接近买点榜】"\n    assert manifest["public_output"]["near_miss_must_be_nonempty_when_eligible_universe_nonempty"] is True\n\ndef test_orchestrator_requires_near_miss_output_without_lowering_buy_gate():\n    text = (ROOT / "skills/a-share-low-risk/orchestrator/SKILL.md").read_text(encoding="utf-8")\n    assert "## 接近买点榜（Near-miss Ranking）" in text\n    assert "不得为了凑榜降低" in text\n    assert "即使当前买点为0" in text\n    assert "不得持久化为候选池" in text\n''', encoding="utf-8")

# Derive a current near-miss list from the existing completed state. This is output-only: do not persist it.
state = json.loads(STATE.read_text(encoding="utf-8"))
vals = state.get("valuations") or {}
bps = state.get("buy_point_assessments") or {}
companies = state.get("companies") or {}
pstruct = state.get("price_structures") or {}
rows = []
for code, v in vals.items():
    if v.get("review_required") or v.get("model_execution_status") != "complete":
        continue
    bp = bps.get(code)
    if not bp:
        continue
    price = num(v.get("current_price"))
    safe = v.get("safe_price_range")
    er = bp.get("structure_entry_range")
    inter = intersection(safe, er)
    value = bool(bp.get("value_eligible"))
    timing = bool(bp.get("timing_eligible"))
    status = bp.get("buy_point_status")
    value_gap = 0.0 if value else distance_to_range(price, safe)
    structure_gap = distance_to_range(price, er)
    rgap = range_gap(safe, er, price)
    current_inter_gap = distance_to_range(price, inter) if inter else None
    missing = (0 if value else 1) + (0 if timing else 1)
    if inter is None:
        missing += 1
    elif current_inter_gap and current_inter_gap > 1e-12:
        missing += 1
    avoid_penalty = 1 if status == "avoid" else 0
    missing += avoid_penalty
    if status == "avoid":
        blocking = "价格结构处于avoid（damaged/overheated）"
    elif not value and not timing:
        blocking = "估值与结构条件均未满足"
    elif not value:
        blocking = "当前价格尚未进入安全价条件"
    elif not timing:
        blocking = "价格结构尚未形成可执行入场区"
    elif inter is None:
        blocking = "安全价区与结构入场区尚无交集"
    elif current_inter_gap and current_inter_gap > 0:
        blocking = "已有价值-结构交集，但当前价尚未进入交集"
    else:
        blocking = "已满足全部条件"
    c = companies.get(code) or {}
    ps = pstruct.get(code) or {}
    score = num(c.get("comparison_score"))
    composite_distance = (value_gap if value_gap is not None else 9999.0) + (structure_gap if structure_gap is not None else 9999.0)
    key = (
        avoid_penalty,
        missing,
        rgap if rgap is not None else 9999.0,
        current_inter_gap if current_inter_gap is not None else 9999.0,
        composite_distance,
        -(score if score is not None else -9999.0),
        code,
    )
    rows.append((key, {
        "code": code,
        "name": c.get("name") or code,
        "source_chain_ids": c.get("source_chain_ids") or [],
        "current_price": price,
        "safe_price_range": safe,
        "structure_status": ps.get("structure_type"),
        "structure_entry_range": er,
        "buy_point_status": status,
        "missing_hard_conditions": missing,
        "value_gap_pct": None if value_gap is None else round(value_gap, 2),
        "structure_gap_pct": None if structure_gap is None else round(structure_gap, 2),
        "safe_structure_range_gap_pct": None if rgap is None else round(rgap, 2),
        "current_to_intersection_pct": None if current_inter_gap is None else round(current_inter_gap, 2),
        "blocking_reason": blocking,
        "fundamental_score": score,
    }))
rows.sort(key=lambda x: x[0])
print("NEAR_MISS_RANKING_JSON")
print(json.dumps([dict(rank=i + 1, **r) for i, (_, r) in enumerate(rows[:10])], ensure_ascii=False, indent=2))
print("NEAR_MISS_ELIGIBLE_COUNT", len(rows))
