import sys, os, json
from pathlib import Path

root = Path(sys.argv[1])
paths = [Path(p) for p in sys.argv[2:]]

def is_ohlcv_cols(cols):
    low = [c.lower() for c in cols]
    need = ["open","high","low","close"]
    # allow variants: o,h,l,c
    if all(any(n in c for c in low) for n in need): 
        return True
    if set(["o","h","l","c"]).issubset(set(low)): 
        return True
    return False

def sniff_csv(p):
    import pandas as pd
    # read only header + first 5 rows
    df = pd.read_csv(p, nrows=5)
    return list(df.columns)

def sniff_parquet(p):
    import pandas as pd
    df = pd.read_parquet(p)  # parquet reads columns metadata quickly; still ok for small-medium
    return list(df.columns)

def sniff_feather(p):
    import pandas as pd
    df = pd.read_feather(p)
    return list(df.columns)

def sniff_json(p):
    import pandas as pd
    # try json lines first
    try:
        df = pd.read_json(p, lines=True, nrows=5)
    except Exception:
        df = pd.read_json(p)
        df = df.head(5)
    return list(df.columns)

sniffers = {
    ".csv": sniff_csv,
    ".parquet": sniff_parquet,
    ".feather": sniff_feather,
    ".json": sniff_json,
    ".jsonl": sniff_json,
}

hits = []
for p in paths:
    ext = p.suffix.lower()
    fn = sniffers.get(ext)
    if not fn:
        continue
    try:
        cols = fn(p)
        if is_ohlcv_cols(cols):
            hits.append((str(p), cols[:40]))
    except Exception:
        continue

print(json.dumps(hits, ensure_ascii=False, indent=2))
