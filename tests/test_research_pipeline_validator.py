from scripts.validate_research_pipeline import (
    validate_company_registry,
    validate_industry_scan,
    validate_stage_order,
    validate_t2_recall,
)


def mini_universe():
    return {
        "broad_industries": [
            {
                "id": "nonferrous",
                "name": "有色金属",
                "minimum_subchains": ["铜矿/冶炼", "电解铝/氧化铝"],
            }
        ]
    }


def valid_scan():
    return {
        "weekly_pool_read": False,
        "industry_frozen_at": "2026-08-29T18:10:00+08:00",
        "broad_industries": [
            {
                "id": "nonferrous",
                "name": "有色金属",
                "subchains": [
                    {
                        "name": "铜矿/冶炼",
                        "registry_source": "minimum",
                        "status": "T2",
                        "direct_profit_driver": "铜价与矿山成本",
                        "leading_variables": ["铜价", "库存"],
                        "evidence_for": ["库存低"],
                        "evidence_against": [],
                        "future_1_2q_transmission": "铜价中枢影响矿山利润",
                        "invalidation_condition": "铜价与供需同时转弱",
                    },
                    {
                        "name": "电解铝/氧化铝",
                        "registry_source": "minimum",
                        "status": "unconfirmed",
                        "direct_profit_driver": "",
                        "leading_variables": [],
                        "evidence_for": [],
                        "evidence_against": [],
                        "future_1_2q_transmission": "",
                        "invalidation_condition": "",
                    },
                ],
                "coverage_gap": [],
            }
        ],
    }


def valid_recall(scan):
    return {
        "weekly_pool_read": False,
        "industry_scan_frozen_at": scan["industry_frozen_at"],
        "t2_recall_frozen_at": "2026-08-29T18:20:00+08:00",
        "t2_subchains": [
            {
                "broad_industry_id": "nonferrous",
                "subchain": "铜矿/冶炼",
                "value_chain_links": [
                    {
                        "name": "铜矿",
                        "company_count": 1,
                        "companies": [
                            {
                                "code": "600362",
                                "name": "江西铜业",
                                "exposure_summary": "铜资源及冶炼",
                                "evidence_sources": ["annual-report"],
                            }
                        ],
                        "coverage_gap": [],
                    }
                ],
                "recall_status": "complete",
                "coverage_gap": [],
            }
        ],
    }


def test_industry_scan_passes_when_every_registry_subchain_is_explicit():
    assert validate_industry_scan(valid_scan(), mini_universe()) == []


def test_industry_scan_fails_on_silent_missing_aluminum():
    scan = valid_scan()
    scan["broad_industries"][0]["subchains"] = scan["broad_industries"][0]["subchains"][:1]
    errors = validate_industry_scan(scan, mini_universe())
    assert any("missing_minimum_subchains:nonferrous" in error for error in errors)


def test_industry_scan_fails_if_weekly_pool_was_read():
    scan = valid_scan()
    scan["weekly_pool_read"] = True
    errors = validate_industry_scan(scan, mini_universe())
    assert "industry_scan_weekly_pool_must_be_false" in errors


def test_t2_recall_requires_every_t2_chain_and_non_silent_links():
    scan = valid_scan()
    recall = valid_recall(scan)
    assert validate_t2_recall(recall, scan) == []

    recall["t2_subchains"][0]["value_chain_links"][0]["companies"] = []
    recall["t2_subchains"][0]["value_chain_links"][0]["company_count"] = 0
    errors = validate_t2_recall(recall, scan)
    assert any("silent_empty_value_chain_link" in error for error in errors)


def test_company_registry_prevents_active_mapping_from_disappearing():
    scan = valid_scan()
    recall = valid_recall(scan)
    registry = {
        "companies": {
            "600362": {
                "name": "江西铜业",
                "mappings": [
                    {
                        "broad_industry_id": "nonferrous",
                        "subchain": "铜矿/冶炼",
                        "value_chain_link": "铜矿",
                        "exposure_summary": "铜资源及冶炼",
                        "status": "active",
                        "evidence_sources": ["annual-report"],
                    }
                ],
            },
            "601899": {
                "name": "紫金矿业",
                "mappings": [
                    {
                        "broad_industry_id": "nonferrous",
                        "subchain": "铜矿/冶炼",
                        "value_chain_link": "铜矿",
                        "exposure_summary": "铜矿资源",
                        "status": "active",
                        "evidence_sources": ["annual-report"],
                    }
                ],
            },
        }
    }
    assert validate_company_registry(registry) == []
    errors = validate_t2_recall(recall, scan, registry)
    assert any("active_registry_mappings_missing_from_recall" in error for error in errors)


def test_stage_order_blocks_weekly_pool_before_freeze():
    good = {
        "industry_frozen_at": "2026-08-29T18:10:00+08:00",
        "t2_recall_frozen_at": "2026-08-29T18:20:00+08:00",
        "weekly_pool_read_at": "2026-08-29T18:21:00+08:00",
    }
    assert validate_stage_order(good) == []

    bad = dict(good)
    bad["weekly_pool_read_at"] = "2026-08-29T18:05:00+08:00"
    errors = validate_stage_order(bad)
    assert "weekly_pool_read_before_t2_recall_freeze" in errors
