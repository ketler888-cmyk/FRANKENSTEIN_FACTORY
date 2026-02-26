import re
from pathlib import Path

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def write(p: Path, s: str):
    p.write_text(s, encoding="utf-8")

# ---------------- backtest_runner.py ----------------
bt = Path("backtest_runner.py")
s = read(bt)

# 1) Remove wrongly injected compat block inside ExitReason (if present)
#    We only remove if it is inside class ExitReason region (best effort).
if "class ExitReason" in s and "# --- compat: entry_signal" in s:
    # remove all compat blocks (safe)
    s2 = re.sub(r"\n\s*# --- compat: entry_signal.*?# --- /compat ---\s*\n", "\n", s, flags=re.S)
    if s2 != s:
        s = s2
        print("OK: removed misplaced compat block(s) from backtest_runner.py")

# 2) Fix BacktestRunner.entry_signal signature: def entry_signal(row...) -> def entry_signal(self, row...)
#    Only inside class BacktestRunner block, with indentation.
m_cls = re.search(r"(?m)^class\s+BacktestRunner\b.*?:\s*$", s)
if not m_cls:
    raise SystemExit("Cannot find class BacktestRunner in backtest_runner.py")

# Find method definition lines that look like: "    def entry_signal(row" (missing self)
pattern = r"(?m)^(?P<ind>\s+)def\s+entry_signal\s*\(\s*row\b"
def repl(m):
    return f"{m.group('ind')}def entry_signal(self, row"
s2 = re.sub(pattern, repl, s, count=1)
if s2 == s:
    # alternate: "def entry_signal(row:" without word boundary issues
    pattern2 = r"(?m)^(?P<ind>\s+)def\s+entry_signal\s*\(\s*row\s*[:\),]"
    s2 = re.sub(pattern2, lambda m: m.group(0).replace("def entry_signal(row", "def entry_signal(self, row"), s, count=1)
if s2 != s:
    s = s2
    print("OK: fixed BacktestRunner.entry_signal(self, row) in backtest_runner.py")
else:
    print("OK: backtest_runner.py already has entry_signal(self, row) or entry_signal not found (no change)")

write(bt, s)

# ---------------- ga_adapters/runner_bridge.py ----------------
rb = Path("ga_adapters") / "runner_bridge.py"
r = read(rb)

# Ensure import sys
if not re.search(r"(?m)^\s*import\s+sys\s*$", r):
    # insert after first import block
    r = re.sub(r"(?m)^(import[^\n]*\n)", r"\1import sys\n", r, count=1) if "import" in r else ("import sys\n" + r)
    print("OK: added import sys to runner_bridge.py")

# Make __init__ accept out_dir if it doesn't
# We do minimal insertion: def __init__(self, ...) -> def __init__(self, out_dir=None, ...) (only if out_dir absent)
def init_patch(txt: str) -> str:
    m = re.search(r"(?m)^(?P<ind>\s*)def\s+__init__\s*\(\s*self\s*(?P<rest>,[^\)]*)?\)\s*:\s*$", txt)
    if not m:
        return txt
    line = m.group(0)
    if "out_dir" in line:
        return txt
    # insert out_dir=None right after self
    new_line = re.sub(r"__init__\s*\(\s*self\s*", "__init__(self, out_dir=None", line)
    return txt.replace(line, new_line, 1)

r2 = init_patch(r)
if r2 != r:
    r = r2
    print("OK: RunnerBridge.__init__ now accepts out_dir")

# Ensure self.out_dir exists if out_dir passed (best effort: add assignment inside __init__ if missing)
if "out_dir" in r and "self.out_dir" not in r:
    r = re.sub(
        r"(?m)^(\s*def\s+__init__\s*\([^\)]*\)\s*:\s*)$",
        r"\1\n        self.out_dir = out_dir\n",
        r, count=1
    )
    print("OK: added self.out_dir = out_dir")

# Replace subprocess python call to sys.executable (if uses hardcoded 'python')
# This covers common patterns: ["python", ...] or ["python.exe", ...]
r_new = re.sub(r'(\[\s*[\'"])(python(?:\.exe)?)([\'"]\s*,)', r'\1sys.executable\3', r)
if r_new != r:
    r = r_new
    print("OK: runner_bridge.py now uses sys.executable in subprocess")

write(rb, r)

print("DONE: patch applied")