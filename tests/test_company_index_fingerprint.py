from copy import deepcopy

from scripts.company_index_fingerprint import company_index_fingerprint


def sample_index() -> dict:
    return {
        "generated_at": "2026-08-30T08:00:00+08:00",
        "main_board_universe_count": 2,
        "missing_codes": [],
        "unmapped_codes": [],
        "companies": {
            "000001": {
                "name": "示例A",
                "registry_broad_industry_id": "bank",
                "industry_code": "480101",
                "sw_level1_code": "480000",
                "sw_level1_name": "银行",
                "hierarchy": {"大类": "股份制银行", "中类": "股份制银行III"},
                "last_verified_at": "2026-08-30T08:00:00+08:00",
            },
            "000002": {
                "name": "示例B",
                "registry_broad_industry_id": "nonferrous",
                "industry_code": "330201",
                "sw_level1_code": "330000",
                "sw_level1_name": "有色金属",
                "hierarchy": {"大类": "工业金属", "中类": "铝"},
                "last_verified_at": "2026-08-30T08:00:00+08:00",
            },
        },
    }


def test_operational_timestamp_changes_do_not_change_fingerprint():
    base = sample_index()
    refreshed = deepcopy(base)
    refreshed["generated_at"] = "2026-08-31T08:00:00+08:00"
    refreshed["companies"]["000001"]["last_verified_at"] = "2026-08-31T08:00:00+08:00"
    assert company_index_fingerprint(base) == company_index_fingerprint(refreshed)


def test_industry_mapping_change_changes_fingerprint():
    base = sample_index()
    changed = deepcopy(base)
    changed["companies"]["000002"]["hierarchy"]["中类"] = "铜"
    assert company_index_fingerprint(base) != company_index_fingerprint(changed)


def test_universe_coverage_change_changes_fingerprint():
    base = sample_index()
    changed = deepcopy(base)
    changed["missing_codes"] = ["000003"]
    changed["main_board_universe_count"] = 3
    assert company_index_fingerprint(base) != company_index_fingerprint(changed)
