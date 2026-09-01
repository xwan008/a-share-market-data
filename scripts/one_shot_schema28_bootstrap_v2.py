from __future__ import annotations

import requests
import one_shot_schema28_bootstrap as base


def fetch_report(report_date: str) -> dict[str, dict]:
    # RPT_LICO_FN_CPD uses REPORTDATE (not REPORT_DATE).
    filters = [f"(REPORTDATE='{report_date}')", f"(REPORTDATE='{report_date} 00:00:00')"]
    for flt in filters:
        rows = []
        page = 1
        while True:
            params = {
                "reportName": "RPT_LICO_FN_CPD",
                "columns": "ALL",
                "filter": flt,
                "pageNumber": page,
                "pageSize": 500,
                "sortColumns": "SECURITY_CODE",
                "sortTypes": "1",
            }
            r = requests.get(base.REPORT_URL, params=params, headers=base.HEADERS, timeout=30)
            r.raise_for_status()
            payload = r.json()
            result = payload.get("result") or {}
            batch = result.get("data") or []
            rows.extend(batch)
            pages = int(result.get("pages") or 0)
            if not batch or page >= pages:
                break
            page += 1
        if rows:
            out = {}
            for row in rows:
                code = str(row.get("SECURITY_CODE") or row.get("SECURITY_CODE_1") or "").zfill(6)
                if len(code) == 6:
                    out[code] = row
            if out:
                return out
    raise RuntimeError(f"no_report_rows:{report_date}")


base.fetch_report = fetch_report
base.main()
