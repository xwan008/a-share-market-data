from scripts.validate_research_pipeline import (
    validate_company_index,
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


def valid_registry():
    return {"companies": {}}


def valid_company_index():
    return {
        "generated_at": "2026-08-29T17:00:00+08:00",
        "main_board_universe_count": 2,
        "indexed_count": 2,
        "missing_codes": [],
        "unmapped_codes": [],
        "companies": {
            "600362": {
                "name": "江西铜业",
                "registry_broad_industry_id": "nonferrous",
            },
            "601899": {
                "name": "紫金矿业",
                "registry_broad_industry_id": "nonferrous",
            },
        },
    }


def valid_recall(scan, index=None):
    index = index or valid_company_index()
    return {
        "weekly_pool_read": False,
        "industry_scan_frozen_at": scan["industry_frozen_at"],
        "company_index_generated_at": index["generated_at"],
        "t2_recall_frozen_at": "2026-08-29T18:20:00+08:00",
        "t2_subchains": [
            {
                "broad_industry_id": "nonferrous",
                "subchain": "铜矿/冶炼",
                "candidate_universe_count": 2,
                "classifications": {
                    "600362": {
                        "status": "exposed",
                        "reason": "铜资源及冶炼业务构成直接暴露",
                        "evidence_sources": ["annual-report"],
                    },
                    "601899": {
                        "status": "not_exposed",
                        "reason": "测试样例中排除",
                    },
                },
                "classification_counts": {
                    "exposed": 1,
                    "not_exposed": 1,
                    "uncertain": 0,
                },
                "cross_industry_search_queries": ["铜矿 A股 上市公司"],
                "cross_industry_discoveries": [],
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


def test_company_index_requires_explicit_missing_and_unmapped_reconciliation():
    index = valid_company_index()
    assert validate_company_index(index, mini_universe()) == []
    index["indexed_count"] = 1
    errors = validate_company_index(index, mini_universe())
    assert any("company_index_indexed_count_mismatch" in error for error in errors)


def test_t2_recall_requires_full_mechanical_candidate_classification():
    scan = valid_scan()
    index = valid_company_index()
    recall = valid_recall(scan, index)
    assert validate_t2_recall(recall, scan, valid_registry(), index, mini_universe()) == []

    recall["t2_subchains"][0]["classifications"].pop("601899")
    recall["t2_subchains"][0]["classification_counts"]["not_exposed"] = 0
    errors = validate_t2_recall(recall, scan, valid_registry(), index, mini_universe())
    assert any("candidate_classification_coverage_mismatch" in error for error in errors)


def test_unknown_index_codes_are_forced_into_every_t2_candidate_universe():
    scan = valid_scan()
    index = valid_company_index()
    index["main_board_universe_count"] = 3
    index["missing_codes"] = ["600111"]
    recall = valid_recall(scan, index)
    # Missing/unmapped codes cannot be silently ignored.
    errors = validate_t2_recall(recall, scan, valid_registry(), index, mini_universe())
    assert any("candidate_universe_count_mismatch" in error for error in errors)


def test_t2_recall_requires_exposed_codes_in_value_chain():
    scan = valid_scan()
    index = valid_company_index()
    recall = valid_recall(scan, index)
    recall["t2_subchains"][0]["classifications"]["601899"] = {
        "status": "exposed",
        "reason": "铜矿资源暴露",
        "evidence_sources": ["annual-report"],
    }
    recall["t2_subchains"][0]["classification_counts"] = {
        "exposed": 2,
        "not_exposed": 0,
        "uncertain": 0,
    }
    errors = validate_t2_recall(recall, scan, valid_registry(), index, mini_universe())
    assert any("exposed_codes_missing_from_value_chain" in error for error in errors)


def test_uncertain_company_forces_chain_incomplete():
    scan = valid_scan()
    index = valid_company_index()
    recall = valid_recall(scan, index)
    recall["t2_subchains"][0]["classifications"]["601899"] = {
        "status": "uncertain",
        "reason": "主营披露不足",
    }
    recall["t2_subchains"][0]["classification_counts"] = {
        "exposed": 1,
        "not_exposed": 0,
        "uncertain": 1,
    }
    errors = validate_t2_recall(recall, scan, valid_registry(), index, mini_universe())
    assert any("recall_status_mismatch" in error for error in errors)


def test_company_registry_prevents_active_mapping_from_disappearing():
    scan = valid_scan()
    index = valid_company_index()
    recall = valid_recall(scan, index)
    registry = {
        "companies": {
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
            }
        }
    }
    assert validate_company_registry(registry) == []
    errors = validate_t2_recall(recall, scan, registry, index, mini_universe())
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
