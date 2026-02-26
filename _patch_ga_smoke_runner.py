import re
from pathlib import Path

p = Path("ga_smoke.py")
s = p.read_text(encoding="utf-8", errors="replace")
lines = s.splitlines(True)

# find runner = BacktestRunner(
start = None
for i, ln in enumerate(lines):
    if re.search(r'\brunner\s*=\s*BacktestRunner\s*\(', ln):
        start = i
        break
if start is None:
    raise SystemExit("Cannot find runner = BacktestRunner(")

# match parentheses until call ends
paren = 0
end = None
for j in range(start, len(lines)):
    ln = lines[j]
    for ch in ln:
        if ch == '(':
            paren += 1
        elif ch == ')':
            paren -= 1
            if paren == 0:
                end = j
                break
    if end is not None:
        break
if end is None:
    raise SystemExit("Could not match parentheses for BacktestRunner(...) block")

indent = re.match(r'^(\s*)', lines[start]).group(1)

patch = (
    f"{indent}# --- runner factory (compat) ---\\n"
    f"{indent}# do NOT pass out_dir to __init__ (some versions don't accept it)\\n"
    f"{indent}runner = BacktestRunner()\\n"
    f"{indent}# set output dir if runner supports it\\n"
    f"{indent}out_dir = locals().get('out_dir', None) or locals().get('out', None)\\n"
    f"{indent}if out_dir is not None and hasattr(runner, 'out_dir'):\\n"
    f"{indent}    runner.out_dir = out_dir\\n"
    f"{indent}# --- /runner factory ---\\n"
)

new_lines = lines[:start] + [patch] + lines[end+1:]
p.write_text("".join(new_lines), encoding="utf-8")

print("OK: ga_smoke.py runner block replaced")
print(f"Replaced lines {start+1}..{end+1}")