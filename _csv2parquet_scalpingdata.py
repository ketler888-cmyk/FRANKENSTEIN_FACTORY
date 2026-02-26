import os, sys, time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC  = ROOT / "SCALPING_DATA"
DST  = ROOT / "SCALPING_DATA_PARQUET"

# You can override:
#   set SRC_DIR / DST_DIR env vars
SRC = Path(os.getenv("SRC_DIR", str(SRC)))
DST = Path(os.getenv("DST_DIR", str(DST)))

def main():
    if not SRC.exists():
        print(f"[ERR] SRC not found: {SRC}")
        return 2

    DST.mkdir(parents=True, exist_ok=True)

    csvs = sorted(SRC.glob("*.csv"))
    print(f"[INFO] SRC={SRC}")
    print(f"[INFO] DST={DST}")
    print(f"[INFO] found csv: {len(csvs)}")
    if not csvs:
        return 0

    # Read hints for speed + stable dtypes
    dtype = {
        "open":"float64","high":"float64","low":"float64","close":"float64","volume":"float64"
    }

    ok = 0
    bad = 0
    t0 = time.perf_counter()

    for p in csvs:
        out = DST / (p.stem + ".parquet")
        try:
            if out.exists() and out.stat().st_mtime >= p.stat().st_mtime:
                print(f"[SKIP] {p.name} -> up-to-date")
                continue

            tA = time.perf_counter()
            df = pd.read_csv(p, dtype=dtype)
            # ensure timestamp exists; keep as is (string/int) – downstream can parse
            # reorder if columns exist
            cols = [c for c in ["timestamp","open","high","low","close","volume"] if c in df.columns]
            rest = [c for c in df.columns if c not in cols]
            df = df[cols + rest]

            tB = time.perf_counter()
            df.to_parquet(out, index=False)  # uses pyarrow
            tC = time.perf_counter()

            print(f"[OK] {p.name} -> {out.name}  read={tB-tA:.3f}s write={tC-tB:.3f}s rows={len(df)}")
            ok += 1
        except Exception as e:
            print(f"[FAIL] {p.name}: {repr(e)}")
            bad += 1

    t1 = time.perf_counter()
    print(f"[DONE] ok={ok} bad={bad} elapsed={t1-t0:.2f}s")
    return 0 if bad == 0 else 3

if __name__ == "__main__":
    raise SystemExit(main())
