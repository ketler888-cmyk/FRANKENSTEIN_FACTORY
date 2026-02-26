import re
from pathlib import Path

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

lines = src.splitlines(True)

patched = 0
out = []
i = 0

# Heuristic patch:
# Replace lines like:
#   df = pd.read_csv(some_path, ...)
# when recent context likely refers to OHLC 1m CSV (contains "_1m.csv" or "SCALPING_DATA")
# with:
#   parq_path = <csvpath with SCALPING_DATA->SCALPING_DATA_PARQUET and .csv->.parquet>
#   if exists -> pd.read_parquet else pd.read_csv(original)
while i < len(lines):
    line = lines[i]
    m = re.search(r'^(\s*)(\w+)\s*=\s*pd\.read_csv\((.+)\)\s*$', line)
    if not m:
        out.append(line)
        i += 1
        continue

    indent, var, args = m.group(1), m.group(2), m.group(3)

    # Look back a few lines for hints that this read_csv is OHLC loader
    ctx = "".join(lines[max(0, i-8):i+1])
    looks_ohlc = ("_1m.csv" in ctx) or ("SCALPING_DATA" in ctx) or ("ohlc" in ctx.lower())

    if not looks_ohlc:
        out.append(line)
        i += 1
        continue

    # Try to locate the first argument (path expression) - simplest: take until first comma not inside quotes/parens
    # We'll keep original args for csv read, but we need the path expr as text.
    # Common cases: file_path / csv_path / path / f"..."
    path_expr = args.strip()
    # Split by first comma at top level (best-effort)
    depth = 0
    in_s = False
    in_d = False
    cut = None
    for j,ch in enumerate(path_expr):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif not in_s and not in_d:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth-1)
            elif ch == "," and depth == 0:
                cut = j
                break
    if cut is None:
        first = path_expr
        rest = ""
    else:
        first = path_expr[:cut].strip()
        rest = path_expr[cut:]  # includes comma

    # Replace this one line with parquet-prefer block
    block = []
    block.append(f"{indent}# FR: prefer parquet for OHLC if available")
    block.append(f"{indent}__csv_path = {first}")
    block.append(f"{indent}__parq_path = str(__csv_path)")
    block.append(f"{indent}__parq_path = __parq_path.replace('SCALPING_DATA','SCALPING_DATA_PARQUET')")
    block.append(f"{indent}if __parq_path.lower().endswith('.csv'):")
    block.append(f"{indent}    __parq_path = __parq_path[:-4] + '.parquet'")
    block.append(f"{indent}if os.path.exists(__parq_path):")
    block.append(f"{indent}    {var} = pd.read_parquet(__parq_path)")
    block.append(f"{indent}else:")
    block.append(f"{indent}    {var} = pd.read_csv(__csv_path{rest})")
    out.append("\n".join(block) + "\n")
    patched += 1
    i += 1

new_src = "".join(out)
path.write_text(new_src, encoding="utf-8")
print(f"[OK] Patched read_csv->prefer_parquet count={patched}")
if patched == 0:
    print("[WARN] Nothing matched. Your loader may not use pd.read_csv in an obvious way; we will patch by exact function name next.")
