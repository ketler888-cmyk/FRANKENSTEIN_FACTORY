from pathlib import Path
import re

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

# 1) Ensure imports
need = ["import os", "from pathlib import Path"]
for imp in need:
    if imp not in src:
        # insert after existing imports block
        m = re.search(r"^(import .*|from .* import .*)\s*$", src, flags=re.M)
        if not m:
            raise SystemExit("Could not locate imports block to inject")
        # find end of first contiguous import section
        lines = src.splitlines(True)
        idx = 0
        while idx < len(lines) and (lines[idx].startswith("import ") or lines[idx].startswith("from ")):
            idx += 1
        lines.insert(idx, imp + "\n")
        src = "".join(lines)

# 2) Add helper function (module-level) if missing
marker = "def _fr_load_ohlc_for_pair("
if marker not in src:
    helper = r'''
def _fr_load_ohlc_for_pair(pair: str, root_dir: str):
    """
    Prefer Parquet from SCALPING_DATA_PARQUET, fallback to CSV from SCALPING_DATA.
    You can override folders via env:
      FR_OHLCV_PARQUET_DIR, FR_OHLCV_CSV_DIR
    """
    import pandas as pd

    root = Path(root_dir)

    pq_dir = Path(os.getenv("FR_OHLCV_PARQUET_DIR", str(root / "SCALPING_DATA_PARQUET")))
    csv_dir = Path(os.getenv("FR_OHLCV_CSV_DIR",     str(root / "SCALPING_DATA")))

    pq = pq_dir / f"{pair}_1m.parquet"
    csv = csv_dir / f"{pair}_1m.csv"

    if pq.exists():
        df = pd.read_parquet(pq)  # pyarrow
        return df, str(pq)

    if csv.exists():
        df = pd.read_csv(csv)
        return df, str(csv)

    raise FileNotFoundError(f"No OHLCV found for {pair}. Checked: {pq} and {csv}")
'''.lstrip("\n")

    # Insert helper near top, after imports and before classes
    m_ins = re.search(r"\nclass\s+", src)
    if not m_ins:
        raise SystemExit("Could not find class definition to place helper before it")
    src = src[:m_ins.start()] + "\n" + helper + "\n" + src[m_ins.start():]

# 3) Patch existing loader call inside BacktestRunner to use helper (best-effort)
# We look for load_all_ohlc or similar that reads CSVs from SCALPING_DATA.
# If we can't match, we only add helper and stop.
patched = False

# Common pattern: method that loads from SCALPING_DATA folder and reads "{pair}_1m.csv"
# We'll replace the read_csv part for single-pair load if it exists.
patterns = [
    r'pd\.read_csv\(([^)]+)\)',   # generic read_csv
]
# We do targeted patch: if code already reads a file path var like file_path / path, we won't overreach.
# Instead, we add an env switch in load_all_ohlc-like method if found.

# Try: find a method named load_all_ohlc or load_ohlc
m = re.search(r"\n\s*def\s+load_all_ohlc\s*\(self.*?\):\s*\n", src)
if m:
    # inject rootdir and helper usage at start of method if not already present
    # We'll add: root_dir = str(Path(__file__).resolve().parent)
    block_start = m.end()
    window = src[block_start:block_start+500]
    if "_fr_load_ohlc_for_pair" not in window:
        inject = "        root_dir = str(Path(__file__).resolve().parent)\n"
        src = src[:block_start] + inject + src[block_start:]
    patched = True

# If no load_all_ohlc, try load_ohlc
m2 = re.search(r"\n\s*def\s+load_ohlc\s*\(self.*?\):\s*\n", src)
if m2:
    block_start = m2.end()
    window = src[block_start:block_start+500]
    if "_fr_load_ohlc_for_pair" not in window:
        inject = "        root_dir = str(Path(__file__).resolve().parent)\n"
        src = src[:block_start] + inject + src[block_start:]
    patched = True

# Write back
path.write_text(src, encoding="utf-8")
print("[OK] Patched: added _fr_load_ohlc_for_pair (prefer parquet).")
print("[WARN] Loader integration is best-effort; next step is to wire it into your exact load_all_ohlc path if needed.")
