import os, json, time, csv
main()
import os, sys
if os.name == "nt":
try:
# Make prints safe even when console is cp1252
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
pass
import os, json, time, csv
from pathlib import Path
import pandas as pd

from backtest_runner import BacktestRunner
# === FRANKEN_ENV_KNOBS ===
# === FRANKEN_SCREEN_PATCH (readers wrapper) ===
import os
try:
import math
import pandas as pd
except Exception:
pd = None

def _fr_screen_df(df):
try:
frac = float(os.environ.get("FR_SCREEN_FRAC","0") or "0")
except Exception:
frac = 0.0
if pd is None or df is None or frac <= 0:
return df
try:
n = int(len(df))
if n < 2000:
return df
target = int(max(500, min(n, math.floor(n * frac))))
if target >= n:
return df
step = int(math.ceil(n / float(target)))
# uniform thinning over full span, keeps chronology
out = df.iloc[::step].copy()
return out
except Exception:
return df

def _fr_wrap_pandas_readers():
if pd is None:
return
if getattr(pd, "_fr_screen_wrapped", False):
return
try:
_orig_rp = pd.read_parquet
_orig_rc = pd.read_csv

def _rp(*args, **kwargs):
df = _orig_rp(*args, **kwargs)
return _fr_screen_df(df)

def _rc(*args, **kwargs):
df = _orig_rc(*args, **kwargs)
return _fr_screen_df(df)

pd.read_parquet = _rp
pd.read_csv = _rc
pd._fr_screen_wrapped = True
except Exception:
pass

_fr_wrap_pandas_readers()
# === /FRANKEN_SCREEN_PATCH ===
import os
FR_WORKERS = int(os.environ.get("FR_WORKERS", "0") or "0")
FR_SCREEN_FRAC = float(os.environ.get("FR_SCREEN_FRAC", "0") or "0")
FR_SCREEN_KEEP = int(os.environ.get("FR_SCREEN_KEEP", "0") or "0")
# These are OPTIONAL knobs. If script doesn't use them yet, they are no-ops.


def pick_data_dir(root: Path) -> Path:
p = root / "SCALPING_DATA_PARQUET"
return p if p.exists() else (root / "SCALPING_DATA")

def load_ohlc(root: Path, pair: str) -> pd.DataFrame:
data_dir = pick_data_dir(root)
parq = data_dir / f"{pair}_1m.parquet"
csvp = data_dir / f"{pair}_1m.csv"
if parq.exists():
df = pd.read_parquet(parq)
elif csvp.exists():
df = pd.read_csv(csvp)
else:
raise FileNotFoundError(f"OHLC not found for {pair}")
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=False)
return df

def run_once(runner, pair, ohlc):
# run_pair_fast expected dict-like result
r = runner.run_pair_fast(pair, ohlc)
return r if isinstance(r, dict) else {"result_repr": repr(r)}

def main():
root = Path(__file__).resolve().parent
pairs = [p.strip() for p in os.getenv("FR_PAIRS","BTCUSDT,ETHUSDT,SOLUSDT").split(",") if p.strip()]
max_bars = int(os.getenv("FR_MAX_BARS","0") or "0")

notionals = [float(x) for x in os.getenv("FR_NOTIONALS","8,50").split(",")]
tps = [float(x) for x in os.getenv("FR_TPS","0.003,0.004").split(",")]
sls = [float(x) for x in os.getenv("FR_SLS","0.003,0.004").split(",")]
start_eq = float(os.getenv("FR_START_EQ","100") or "100")

out_root = root / "results_ga" / f"grid_{time.strftime('%Y%m%d_%H%M%S')}"
out_root.mkdir(parents=True, exist_ok=True)

jsonl = out_root / "grid_results.jsonl"
csvp  = out_root / "grid_summary.csv"

data_dir = pick_data_dir(root)
cache_dir = root / "cache"

print(f"[GRID] out={out_root}")
print(f"[GRID] pairs={pairs} max_bars={max_bars}")
print(f"[GRID] notionals={notionals} tps={tps} sls={sls} start_eq={start_eq}")

rows=[]
with open(jsonl,"w",encoding="utf-8") as fj:
for pair in pairs:
ohlc = load_ohlc(root, pair)
if max_bars>0 and len(ohlc)>max_bars:
ohlc = ohlc.iloc[-max_bars:].copy()

for notional in notionals:
for tp in tps:
for sl in sls:
runner = BacktestRunner(
data_dir=data_dir,
cache_dir=cache_dir,
results_dir=root / "results_ga",
notional_usdt=notional,
tp_pct=tp,
sl_pct=sl,
starting_equity=start_eq,
)

t0=time.perf_counter()
r1=run_once(runner, pair, ohlc)
dt1=time.perf_counter()-t0

t1=time.perf_counter()
r2=run_once(runner, pair, ohlc)
dt2=time.perf_counter()-t1

# Determinism check for key fields if present
keys = ["trades","net_pnl","fees"]
same=True
for k in keys:
if k in r1 and k in r2 and r1[k]!=r2[k]:
same=False

out={
"pair":pair,"bars":int(len(ohlc)),
"notional":notional,"tp_pct":tp,"sl_pct":sl,
"t1_sec":dt1,"t2_sec":dt2,"t2_over_t1": (dt2/dt1 if dt1>0 else None),
"same_metrics":same,
}
for k in ["trades","net_pnl","fees","gross_pnl","win_rate","max_dd","profit_factor"]:
if k in r1: out[k]=r1[k]
fj.write(json.dumps(out,ensure_ascii=False)+"\n")
rows.append(out)
print(f"[GRID] {pair} n={notional} tp={tp} sl={sl}  t1={dt1:.3f}s t2={dt2:.3f}s same={same} trades={out.get('trades')}")

cols=["pair","bars","notional","tp_pct","sl_pct","t1_sec","t2_sec","t2_over_t1","same_metrics","trades","net_pnl","fees"]
cols=[c for c in cols if any(c in r for r in rows)]
with open(csvp,"w",newline="",encoding="utf-8") as f:
w=csv.DictWriter(f,fieldnames=cols)
w.writeheader()
for r in rows: w.writerow({c:r.get(c,"") for c in cols})

print(f"[GRID] jsonl={jsonl}")
print(f"[GRID] csv={csvp}")
print("[GRID] done")

if __name__=="__main__":
main()



