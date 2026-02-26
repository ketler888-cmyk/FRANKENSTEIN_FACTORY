import os
import glob
import pandas as pd

ROOT = r"C:\Users\user\Desktop\Франкинштэйн"
OUT = r"C:\Users\user\Desktop\FRANKEN_DATA_AUDIT_20260219_202339.txt"
TARGET_PAIR = "DOGEUSDT"

def pick_time_col(cols):
    for c in ["timestamp","time","open_time","date","datetime","ts","openTime","open_time_ms"]:
        if c in cols:
            return c
    return None

def safe_dt(series):
    try:
        return pd.to_datetime(series, unit="ms", errors="coerce")
    except:
        try:
            return pd.to_datetime(series, errors="coerce")
        except:
            return None

def find_parquets():
    dirs = [
        ROOT,
        os.path.join(ROOT, "SCALPING_DATA_PARQUET"),
        os.path.join(ROOT, "SCALPING_DATA_RAW"),
        os.path.join(ROOT, "data"),
        os.path.join(ROOT, "datasets"),
    ]
    found = []
    for d in dirs:
        if os.path.isdir(d):
            found += glob.glob(os.path.join(d, "**", "*.parquet"), recursive=True)
    return sorted(list(set(found)))

files = find_parquets()

with open(OUT, "w", encoding="utf-8") as w:
    w.write("=== FRANKEN DATA AUDIT ===\\n")
    w.write(f"ROOT: {ROOT}\\n")
    w.write(f"PARQUET FILES FOUND: {len(files)}\\n\\n")

    pair_files = [f for f in files if TARGET_PAIR in os.path.basename(f)]

    w.write("=== PAIR FILES (DOGEUSDT) ===\\n")
    if not pair_files:
        w.write("NO DOGEUSDT FILES FOUND ❌\\n")
    else:
        for f in pair_files:
            w.write(f"{f}\\n")
    w.write("\\n")

    w.write("=== FILE SUMMARY (FIRST 50) ===\\n")
    for f in files[:50]:
        try:
            df = pd.read_parquet(f)
            rows = len(df)
            cols = list(df.columns)
            tcol = pick_time_col(cols)

            tmin = tmax = "N/A"
            if tcol and rows > 0:
                s = safe_dt(df[tcol])
                if s is not None:
                    tmin = str(s.min())
                    tmax = str(s.max())

            w.write(f"FILE: {os.path.basename(f)}\\n")
            w.write(f"PATH: {f}\\n")
            w.write(f"ROWS: {rows}\\n")
            w.write(f"COLUMNS: {cols}\\n")
            w.write(f"TIME_COL: {tcol}\\n")
            w.write(f"DATE_RANGE: {tmin} -> {tmax}\\n")
            w.write("-"*60 + "\\n")

        except Exception as e:
            w.write(f"READ FAIL: {f} | ERROR: {e}\\n")