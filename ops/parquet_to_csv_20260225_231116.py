import sys
from pathlib import Path
import pandas as pd

data_dir = Path(sys.argv[1])
pairs = sys.argv[2:]  # optional stems

def convert_one(pq: Path):
    csv = pq.with_suffix("").with_suffix(".csv")  # *_1m.parquet -> *_1m.csv
    if csv.exists():
        return ("SKIP", str(pq), str(csv))
    df = pd.read_parquet(pq)
    df.to_csv(csv, index=False, encoding="utf-8")
    return ("OK", str(pq), str(csv))

parquets = list(data_dir.glob("*_1m.parquet"))
if pairs:
    wanted = set([p.strip().upper() for p in pairs if p.strip()])
    parquets = [p for p in parquets if p.stem.replace("_1m","").upper() in wanted]

if not parquets:
    print("NO PARQUETS FOUND")
    sys.exit(2)

ok=0; skip=0; fail=0
for pq in parquets:
    try:
        st, a, b = convert_one(pq)
        print(st, a, "->", b)
        if st=="OK": ok+=1
        else: skip+=1
    except Exception as e:
        fail+=1
        print("FAIL", str(pq), "err:", repr(e))

print(f"SUMMARY ok={ok} skip={skip} fail={fail}")
sys.exit(0 if fail==0 else 3)
