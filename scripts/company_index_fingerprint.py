from __future__ import annotations

import hashlib
import json


def canonical_company_index(index: dict) -> dict:
    companies = {}
    for raw_code, item in sorted((index.get("companies") or {}).items()):
        code = str(raw_code).zfill(6)
        hierarchy = item.get("hierarchy") or {}
        companies[code] = {
            "registry_broad_industry_id": item.get("registry_broad_industry_id"),
            "industry_code": item.get("industry_code"),
            "sw_level1_code": item.get("sw_level1_code"),
            "sw_level1_name": item.get("sw_level1_name"),
            "hierarchy": {
                str(key): hierarchy.get(key)
                for key in sorted(hierarchy)
            },
        }

    return {
        "main_board_universe_count": index.get("main_board_universe_count"),
        "companies": companies,
        "missing_codes": sorted(str(code).zfill(6) for code in index.get("missing_codes", [])),
        "unmapped_codes": sorted(str(code).zfill(6) for code in index.get("unmapped_codes", [])),
    }


def company_index_fingerprint(index: dict) -> str:
    payload = canonical_company_index(index)
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()
