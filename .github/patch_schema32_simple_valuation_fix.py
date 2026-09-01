from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT/'.github/patch_schema32_simple_valuation.py'),run_name='__main__')

# Preserve explicit no-lowering discipline in the V3 Near-miss section.
op=ROOT/'skills/a-share-low-risk/orchestrator/SKILL.md'
t=op.read_text(encoding='utf-8')
t=t.replace('正式买点仍只允许 `buyable_now`。即使当前买点为0，也必须输出Top10。','正式买点仍只允许 `buyable_now`，绝不为了凑榜降低买点门槛。即使当前买点为0，也必须输出Top10。')
op.write_text(t,encoding='utf-8')

# Migrate old Near-miss contract tests to V3 metrics/naming.
p=ROOT/'tests/test_near_miss_ranking_contract.py'
x=p.read_text(encoding='utf-8')
x=x.replace('assert "ceiling_structure_gap_pct" in c["required_metrics"]','assert "value_gap_pct" in c["required_metrics"]\n    assert "structure_gap_pct" in c["required_metrics"]')
x=x.replace('assert "## 接近买点榜（Near-miss Ranking V2）" in text','assert "## 接近买点榜（Near-miss Ranking V3）" in text')
p.write_text(x,encoding='utf-8')
print('schema32 old near-miss tests migrated and discipline wording restored')
