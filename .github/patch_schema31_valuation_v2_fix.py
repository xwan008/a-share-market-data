from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT/'.github/patch_schema31_valuation_v2.py'),run_name='__main__')

p=ROOT/'tests/test_research_contract.py'
x=p.read_text(encoding='utf-8').replace("max_method_midpoint_divergence_pct_before_model_instability'] == 31.0","max_method_midpoint_divergence_pct_before_model_instability'] == 30.0")
p.write_text(x,encoding='utf-8')

p=ROOT/'tests/test_near_miss_ranking_contract.py'
x=p.read_text(encoding='utf-8')
x=x.replace('assert "missing_hard_conditions" in c["required_metrics"]','assert "action_distance_pct" in c["required_metrics"]')
x=x.replace('assert "safe_structure_range_gap_pct" in c["required_metrics"]','assert "ceiling_structure_gap_pct" in c["required_metrics"]')
x=x.replace('assert "## 接近买点榜（Near-miss Ranking）" in text','assert "## 接近买点榜（Near-miss Ranking V2）" in text')
x=x.replace('assert "不得为了凑榜降低" in text','assert "绝不为了凑榜降低" in text')
p.write_text(x,encoding='utf-8')
print('schema31 test migration fixed')
