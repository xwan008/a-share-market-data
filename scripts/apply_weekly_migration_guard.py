from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIGHT = ROOT / "data" / "research" / "pipeline" / "weekly_light_recall.json"
SUMMARY = ROOT / "data" / "research" / "pipeline" / "weekly_light_candidates.json"
OLD = ROOT / "data" / "research" / "weekly_fundamental_opportunity_pool.json"
ACTIVE_STATUS = {"新发现", "继续保留", "盈利强化", "盈利转弱"}


def main() -> int:
    light = json.loads(LIGHT.read_text(encoding="utf-8"))
    old = json.loads(OLD.read_text(encoding="utf-8")) if OLD.exists() else {"candidates": []}
    screen = light.get("screen_results", {})
    promoted = []
    for row in old.get("candidates", []):
        code = str(row.get("code") or "").zfill(6)
        if row.get("status") not in ACTIVE_STATUS or code not in screen:
            continue
        item = screen[code]
        if item.get("status") == "reject":
            item["status"] = "uncertain"
            item["reason"] = (item.get("reason") or "") + "；旧周度active候选，按状态迁移规则强制进入深验，不代表自动保留"
            promoted.append(code)
    counts = {k: sum(1 for v in screen.values() if v.get("status") == k) for k in ("pass", "uncertain", "reject")}
    light["status_counts"] = counts
    light["legacy_migration_forced_review_codes"] = promoted
    candidates = [{"code": code, **item} for code, item in screen.items() if item.get("status") in {"pass", "uncertain"}]
    candidates.sort(key=lambda x: (-float(x.get("triage_score") or 0), x["code"]))
    summary = {
        "schema_version": 1,
        "generated_at": light.get("generated_at"),
        "universe_count": light.get("universe_count"),
        "candidate_count": len(candidates),
        "source_status": light.get("source_status", {}),
        "legacy_migration_forced_review_codes": promoted,
        "candidates": candidates,
    }
    LIGHT.write_text(json.dumps(light, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"ok","promoted_for_explicit_migration":promoted,"candidate_count":len(candidates)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
