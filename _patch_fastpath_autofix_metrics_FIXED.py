import re
from pathlib import Path

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

if "def run_pair_fast" not in src:
    raise SystemExit("run_pair_fast not found. Apply fastpath patch first.")

# -------- Parse Metrics fields (regex-safe, indentation-based) --------
m_cls = re.search(r"^class\s+Metrics\b.*?:\s*$", src, flags=re.M)
if not m_cls:
    raise SystemExit("class Metrics not found")

# class body starts next line
cls_body_start = src.find("\n", m_cls.end()) + 1
lines = src[cls_body_start:].splitlines()

fields = []
for ln in lines:
    # stop when leaving class indentation (next top-level def/class or blank line at col0)
    if ln.startswith("class ") or ln.startswith("def "):
        break
    if ln and (not ln.startswith(" ") and not ln.startswith("\t")):
        break

    s = ln.strip()
    if not s or s.startswith("#") or s.startswith('"""'):
        continue

    mm = re.match(r"^([A-Za-z_]\w*)\s*:\s*[^=]+(?:=\s*.+)?$", s)
    if mm:
        name = mm.group(1)
        fields.append(name)

# de-dup keep order
seen=set(); f2=[]
for x in fields:
    if x not in seen:
        seen.add(x); f2.append(x)
fields = f2
if not fields:
    raise SystemExit("Could not parse Metrics fields (Metrics not dataclass-like?)")

# -------- Locate run_pair_fast block --------
ix = src.find("def run_pair_fast")
line_start = src.rfind("\n", 0, ix) + 1

m_ind = re.match(r"(\s*)def run_pair_fast", src[ix:])
if not m_ind:
    raise SystemExit("Could not read run_pair_fast indent")
f_indent = m_ind.group(1)

pattern_next = "\n" + f_indent + "def "
j = src.find(pattern_next, ix + 1)
fast_end = j if j != -1 else len(src)
fast_block = src[line_start:fast_end]

if "compute_metrics" not in fast_block:
    print("[OK] run_pair_fast already has no compute_metrics; nothing to do.")
    raise SystemExit(0)

m_eq = re.search(r"\n(\s*)eq\s*=\s*pd\.Series\([^\n]*\)\s*\n", fast_block)
m_pr = re.search(r"\n\s*pair_report\s*=\s*\{\s*\n", fast_block)
if not m_eq or not m_pr or m_pr.start() <= m_eq.end():
    raise SystemExit("Could not locate eq=... and pair_report=... inside run_pair_fast.")

indent_eq = m_eq.group(1)

# -------- Build auto metrics block --------
code = []
code.append(f"{indent_eq}# metrics (auto-filled; profiling/bench)")
code.append(f"{indent_eq}gross_pnl = float(sum([t.gross_pnl for t in trades])) if trades else 0.0")
code.append(f"{indent_eq}fees      = float(sum([t.total_fee for t in trades])) if trades else 0.0")
code.append(f"{indent_eq}net_pnl   = float(sum([t.net_pnl for t in trades])) if trades else 0.0")
code.append(f"{indent_eq}wins      = [t for t in trades if t.net_pnl > 0] if trades else []")
code.append(f"{indent_eq}losses    = [t for t in trades if t.net_pnl <= 0] if trades else []")
code.append(f"{indent_eq}winrate   = float(len(wins)/len(trades)) if trades else 0.0")
code.append(f"{indent_eq}tw = float(sum([t.net_pnl for t in wins])) if wins else 0.0")
code.append(f"{indent_eq}tl = float(abs(sum([t.net_pnl for t in losses]))) if losses else 0.0")
code.append(f"{indent_eq}profit_factor = float(tw/tl) if tl > 0 else (float('inf') if tw > 0 else 0.0)")
code.append(f"{indent_eq}roll_max = eq.cummax()")
code.append(f"{indent_eq}dd = (eq - roll_max) / roll_max.replace(0, float('nan'))")
code.append(f"{indent_eq}max_dd = float(abs(dd.min())) if len(dd) else 0.0")
code.append(f"{indent_eq}avg_trade = float(net_pnl/len(trades)) if trades else 0.0")
code.append(f"{indent_eq}tim = (bars_in_trade/total_bars) if total_bars else 0.0")

known = {
    "pair": "pair",
    "trades": "int(len(trades))",
    "winrate": "winrate",
    "gross_pnl": "gross_pnl",
    "fees": "fees",
    "net_pnl": "net_pnl",
    "max_drawdown": "max_dd",
    "avg_trade": "avg_trade",
    "profit_factor": "profit_factor",
    "total_bars": "int(total_bars)",
    "bars_in_trade": "int(bars_in_trade)",
    "time_in_market": "tim",
    "final_equity": "float(equity)",
}

kwargs = []
for name in fields:
    if name in known:
        kwargs.append(f"{name}={known[name]}")
    else:
        kwargs.append(f"{name}=0.0")

code.append(f"{indent_eq}m = Metrics(" + ", ".join(kwargs) + ")")
code.append("")
insert = "\n".join(code) + "\n"

# remove any line that calls compute_metrics between eq and pair_report
mid = fast_block[m_eq.end():m_pr.start()]
mid2 = re.sub(r"^\s*.*compute_metrics.*$\n?", "", mid, flags=re.M)

new_fast = fast_block[:m_eq.end()] + insert + mid2 + fast_block[m_pr.start():]
if "compute_metrics" in new_fast:
    raise SystemExit("Patch failed: compute_metrics still present after rewrite.")

src2 = src[:line_start] + new_fast + src[fast_end:]
path.write_text(src2, encoding="utf-8")
print("[OK] Patched run_pair_fast: removed compute_metrics; auto-built Metrics fields.")
