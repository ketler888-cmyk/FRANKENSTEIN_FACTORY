import json, os
from pathlib import Path

ROOT = Path(os.environ.get("FR_ROOT", ".")).resolve()

SCAN_DIRS = [
    ROOT / "data",
    ROOT / "datasets",
    ROOT / "quotes",
    ROOT / "ohlcv",
    ROOT / "cache",
    ROOT / "results",
    ROOT,
]

EXTS = {".csv",".parquet",".feather",".json",".jsonl"}
MAX_FILES = 1200  # safety cap

def norm(s): return str(s).strip().lower()

def is_ohlcv(cols):
    low = [norm(c) for c in cols]
    def has_any(keys):
        return any(any(k in c for c in low) for k in keys)
    close_ok = has_any(["close","closing","last","closeprice","close_price","price_close","c"])
    open_ok  = has_any(["open","opening","openprice","open_price","o"])
    high_ok  = has_any(["high","highprice","high_price","h"])
    low_ok   = has_any(["low","lowprice","low_price","l"])
    return close_ok and open_ok and high_ok and low_ok

def sniff_csv(p):
    import pandas as pd
    df = pd.read_csv(p, nrows=1)
    return list(df.columns)

def sniff_json(p):
    import pandas as pd
    try:
        df = pd.read_json(p, lines=True, nrows=1)
    except Exception:
        df = pd.read_json(p).head(1)
    return list(df.columns)

def sniff_parquet_schema(p):
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(p)
    return [f.name for f in pf.schema_arrow]

def sniff_feather_schema(p):
    import pyarrow.feather as feather
    tbl = feather.read_table(p, columns=None)
    return tbl.schema.names

sniffers = {
    ".csv": sniff_csv,
    ".json": sniff_json,
    ".jsonl": sniff_json,
    ".parquet": sniff_parquet_schema,
    ".feather": sniff_feather_schema,
}

def iter_files():
    seen = set()
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in EXTS:
                continue
            # skip huge zip-like json dumps if any (optional)
            if p.name.lower().endswith(".zip"):
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p

hits = []
errors = []
count = 0

for p in iter_files():
    count += 1
    if count > MAX_FILES:
        break
    ext = p.suffix.lower()
    fn = sniffers.get(ext)
    if not fn:
        continue
    try:
        cols = fn(p)
        if is_ohlcv(cols):
            hits.append({"path": str(p), "cols": cols[:60]})
    except Exception as e:
        if len(errors) < 40:
            errors.append({"path": str(p), "err": repr(e)})

out = {
    "root": str(ROOT),
    "files_scanned": count,
    "hits": hits,
    "errors": errors,
}
print(json.dumps(out, ensure_ascii=False, indent=2))
