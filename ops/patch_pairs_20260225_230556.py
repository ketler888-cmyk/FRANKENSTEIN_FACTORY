import re
from pathlib import Path
import sys

p = Path(r"C:\FRANKEN\backtest_runner_v3.py")
txt = p.read_text(encoding="utf-8")

needle1 = 'files = list(self.data_dir.glob("*_1m.csv"))'
needle2 = 'pairs = [f.stem.replace("_1m", "") for f in files]'

if needle1 not in txt or needle2 not in txt:
    print("PATTERN NOT FOUND. No changes made.")
    sys.exit(2)

lines = txt.splitlines(True)  # keep newlines
out = []
i = 0
changed = False

while i < len(lines):
    line = lines[i]
    if needle1 in line:
        indent = re.match(r'^(\s*)', line).group(1)

        out.append(f'{indent}files_csv = list(self.data_dir.glob("*_1m.csv"))\n')
        out.append(f'{indent}files_pq  = list(self.data_dir.glob("*_1m.parquet"))\n')
        out.append(f'{indent}files = files_csv + files_pq\n')
        out.append(f'{indent}if not files:\n')
        out.append(f'{indent}    raise FileNotFoundError(f"No files matching \'*_1m.csv\' or \'*_1m.parquet\' found in {self.data_dir}")\n')
        out.append(f'{indent}pairs = [f.stem.replace("_1m", "") for f in files]\n')

        # Skip current line and then skip until (and including) the original pairs line
        i += 1
        while i < len(lines) and needle2 not in lines[i]:
            i += 1
        if i < len(lines) and needle2 in lines[i]:
            i += 1
        changed = True
        continue

    out.append(line)
    i += 1

if not changed:
    print("NO CHANGE APPLIED.")
    sys.exit(3)

p.write_text("".join(out), encoding="utf-8")
print("OK: patched data discovery to support CSV + PARQUET")
