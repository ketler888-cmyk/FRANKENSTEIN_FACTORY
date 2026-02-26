import time
import os
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
PARQ = os.path.join(ROOT, "cache", "indicators", "BTCUSDT_indicators.parquet")

def pick_col(df, candidates):
    cols = list(df.columns)
    low = {c.lower(): c for c in cols}
    # exact (case-insensitive)
    for cand in candidates:
        c = low.get(cand.lower())
        if c: return c
    # contains
    for cand in candidates:
        candl = cand.lower()
        for c in cols:
            if candl in c.lower():
                return c
    return None

print("[PROFILE] start")
t0 = time.perf_counter()
df = pd.read_parquet(PARQ)
t1 = time.perf_counter()

print(f"[PROFILE] parquet load: {t1 - t0:.3f}s rows={len(df)} cols={len(df.columns)}")
print("[PROFILE] columns sample:", list(df.columns)[:60])

# detect close/open/high/low/volume
close_col = pick_col(df, ["close","c","close_price","price_close","closing_price","last","last_price"])
open_col  = pick_col(df, ["open","o","open_price"])
high_col  = pick_col(df, ["high","h","high_price"])
low_col   = pick_col(df, ["low","l","low_price"])
vol_col   = pick_col(df, ["volume","vol","v","base_volume","quote_volume","turnover"])

print("[PROFILE] detected:",
      {"open":open_col, "high":high_col, "low":low_col, "close":close_col, "volume":vol_col})

if close_col is None:
    raise SystemExit("[PROFILE] ERROR: cannot find close-like column in parquet. Use the printed columns to update mapping.")

# convert only what exists (minimum close)
t2a = time.perf_counter()
arr_close = df[close_col].to_numpy(dtype=np.float64)
t2b = time.perf_counter()
print(f"[PROFILE] to_numpy(close): {t2b - t2a:.3f}s")

# Optional: also convert OHLCV if found (extra info)
extra = {}
for name, col in [("open",open_col),("high",high_col),("low",low_col),("volume",vol_col)]:
    if col is not None:
        tA = time.perf_counter()
        extra[name] = df[col].to_numpy(dtype=np.float64)
        tB = time.perf_counter()
        print(f"[PROFILE] to_numpy({name}): {tB - tA:.3f}s")

# minimal simulate loop on close only (NO strategy logic)
cash = 100.0
pos = 0.0

N = min(200_000, arr_close.shape[0])  # cap for safety
t3a = time.perf_counter()
for i in range(N):
    price = arr_close[i]
    if pos == 0 and (i % 1000) == 0:
        pos = cash / price
        cash = 0.0
    elif pos > 0 and (i % 1000) == 500:
        cash = pos * price
        pos = 0.0
t3b = time.perf_counter()
print(f"[PROFILE] simulate {N} bars (close-only): {t3b - t3a:.3f}s")

print("[PROFILE] done")
