from __future__ import annotations

import json
from pathlib import Path
import akshare as ak

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "pipeline" / "weekly_source_debug.json"
TARGETS = {"000338","002475","603259","601138","600160","601600"}


def inspect(name, func):
    try:
        df = func()
        columns = [str(x) for x in df.columns]
        samples = []
        code_cols = [c for c in columns if "代码" in c or "证券" in c]
        for _, row in df.iterrows():
            raw_code = None
            for c in code_cols:
                v = row.get(c)
                if v not in (None, ""):
                    raw_code = str(v)
                    break
            if raw_code is None:
                continue
            digits = "".join(ch for ch in raw_code if ch.isdigit())
            code = digits[-6:].zfill(6) if digits else ""
            if code in TARGETS:
                samples.append({str(k): (None if str(v) == "nan" else v) for k, v in dict(row).items()})
        return {"rows": len(df), "columns": columns, "code_columns": code_cols, "target_samples": samples[:30]}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}:{exc}"}


def main():
    payload = {
        "yjbb": inspect("yjbb", lambda: ak.stock_yjbb_em(date="20260630")),
        "yjkb": inspect("yjkb", lambda: ak.stock_yjkb_em(date="20260630")),
        "yjyg": inspect("yjyg", lambda: ak.stock_yjyg_em(date="20260930")),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k:{"rows":v.get("rows"),"columns":v.get("columns"),"targets":len(v.get("target_samples",[])),"error":v.get("error")} for k,v in payload.items()}, ensure_ascii=False))

if __name__ == "__main__":
    main()
