import re
from pathlib import Path

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

# 1) Extract Metrics block from normal run_pair (trusted)
m_rp = re.search(r"\n\s*def run_pair\([^\n]*\):", src)
if not m_rp:
    raise SystemExit("run_pair not found")

# Take slice of run_pair body (until next def at same indent level inside class)
rp_start = m_rp.start()
m_next = re.search(r"\n\s{4}def\s+\w+\(", src[m_rp.end():])
rp_end = (m_rp.end() + m_next.start()) if m_next else len(src)
rp_block = src[rp_start:rp_end]

m_metrics = re.search(r"\n\s*# Metrics\s*\n", rp_block)
m_pairrep = re.search(r"\n\s*pair_report\s*=\s*\{\s*\n", rp_block)
if not m_metrics or not m_pairrep or m_pairrep.start() <= m_metrics.start():
    raise SystemExit("Could not extract Metrics block from run_pair")

metrics_block = rp_block[m_metrics.start():m_pairrep.start()]
# Ensure it assigns to 'm = Metrics(' etc
if "m = Metrics(" not in metrics_block:
    raise SystemExit("Extracted Metrics block doesn't look right (missing 'm = Metrics(')")

# 2) Locate run_pair_fast anywhere (robust)
ix = src.find("def run_pair_fast")
if ix < 0:
    raise SystemExit("run_pair_fast not found")

# find start of its line
line_start = src.rfind("\n", 0, ix) + 1
# determine indent (spaces before 'def')
indent = re.match(r"(\s*)def run_pair_fast", src[ix:]).group(1)
# In class, indent should be 4 spaces, but we handle any.
# Find end of function by next line that starts with same indent + 'def '
pattern_next = "\n" + indent + "def "
j = src.find(pattern_next, ix + 1)
fast_end = j if j != -1 else len(src)
fast_block = src[line_start:fast_end]

if "compute_metrics" not in fast_block:
    print("[OK] run_pair_fast already has no compute_metrics. Nothing to do.")
    raise SystemExit(0)

# 3) Replace the section inside run_pair_fast between 'eq = pd.Series' and 'pair_report = {'
m_eq = re.search(r"\n\s*eq\s*=\s*pd\.Series\([^\n]*\)\s*\n", fast_block)
m_pr = re.search(r"\n\s*pair_report\s*=\s*\{\s*\n", fast_block)
if not m_eq or not m_pr or m_pr.start() <= m_eq.end():
    raise SystemExit("Could not locate eq=... or pair_report=... inside run_pair_fast for replacement")

new_fast = fast_block[:m_eq.end()] + metrics_block + fast_block[m_pr.start():]

# Safety: ensure compute_metrics removed in new block
if "compute_metrics" in new_fast:
    raise SystemExit("Replacement failed: compute_metrics still present after patch")

src2 = src[:line_start] + new_fast + src[fast_end:]
path.write_text(src2, encoding="utf-8")
print("[OK] Patched: run_pair_fast now uses Metrics block from run_pair (no compute_metrics).")
