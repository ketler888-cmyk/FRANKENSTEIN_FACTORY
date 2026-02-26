import sys, json
from pathlib import Path

root = Path(sys.argv[1])
paths = [Path(p) for p in sys.argv[2:]]

def norm(s): return str(s).strip().lower()

def is_ohlcv(cols):
    low = [norm(c) for c in cols]
    has = lambda keys: any(any(k in c for c in low) for k in keys)
    close_ok = has(["close","closing","last","price_close","closeprice","c"])
    open_ok  = has(["open","opening","openprice","o"])
    high_ok  = has(["high","highprice","h"])
    low_ok   = has(["low","lowprice","l"])
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

hits = []
errors = []

for p in paths:
    ext = p.suffix.lower()
    fn = sniffers.get(ext)
    if not fn:
        continue
    try:
        cols = fn(p)
        if is_ohlcv(cols):
            hits.append({"path": str(p), "cols": cols[:40]})
    except Exception as e:
        if len(errors) < 30:
            errors.append({"path": str(p), "err": repr(e)})

print(json.dumps({"hits": hits, "errors": errors}, ensure_ascii=False, indent=2))
