import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "industry_scan_universe.json"


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_industry_scan_universe_has_full_broad_coverage_contract():
    cfg = load_config()
    industries = cfg["broad_industries"]

    assert cfg["coverage_rules"]["all_broad_industries_must_be_scanned"] is True
    assert cfg["coverage_rules"]["minimum_subchains_are_floor_not_ceiling"] is True
    assert len(industries) >= 31

    ids = [item["id"] for item in industries]
    names = [item["name"] for item in industries]
    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))
    assert all(item["minimum_subchains"] for item in industries)


def test_high_omission_risk_industries_have_multiple_mandatory_subchains():
    cfg = load_config()
    by_name = {item["name"]: item for item in cfg["broad_industries"]}

    # The point is not these two examples themselves. They guard against the
    # old failure mode where a broad sector was represented by a few familiar
    # leaders and entire profit-driver branches silently disappeared.
    assert "电解铝/氧化铝" in by_name["有色金属"]["minimum_subchains"]
    assert "高速连接器/铜互连" in by_name["电子"]["minimum_subchains"]
    assert "高速铜互连/连接器" in by_name["通信"]["minimum_subchains"]
    assert len(by_name["基础化工"]["minimum_subchains"]) >= 10
    assert len(by_name["有色金属"]["minimum_subchains"]) >= 8
    assert len(by_name["电子"]["minimum_subchains"]) >= 8
