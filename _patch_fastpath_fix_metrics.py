import re
from pathlib import Path

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

if "def run_pair_fast" not in src:
    raise SystemExit("run_pair_fast not found. Apply fastpath patch first.")

# Locate run_pair_fast block
m_fast = re.search(r"^\s{4}def run_pair_fast\([^\n]*\):\s*$", src, flags=re.M)
if not m_fast:
    raise SystemExit("Could not locate run_pair_fast signature")

# Find end of run_pair_fast by next method at same indent
m_next = re.search(r"^\s{4}def\s+\w+\(", src[m_fast.end():], flags=re.M)
fast_end = (m_fast.end() + m_next.start()) if m_next else len(src)
fast_block = src[m_fast.start():fast_end]

# If compute_metrics call is present, replace metrics section
if "compute_metrics" not in fast_block:
    print("[OK] run_pair_fast already has no compute_metrics call.")
    raise SystemExit(0)

# Replace between 'eq = pd.Series...' and 'pair_report = {'
pat = re.compile(
    r'(eq\s*=\s*pd\.Series\(eq_list,\s*dtype="float64"\)\s*\n)'
    r'(?:.*?\n)*?'
    r'(\s*pair_report\s*=\s*\{\n)',
    flags=re.S
)

rep = r"""\1
    # metrics (copied from run_pair)
    if len(trades) == 0:
        m = Metrics(
            pair=pair, trades=0, winrate=0.0, gross_pnl=0.0, fees=0.0, net_pnl=0.0,
            max_drawdown=0.0, avg_trade=0.0, profit_factor=0.0,
            total_bars=total_bars, bars_in_trade=bars_in_trade,
            time_in_market=(bars_in_trade / total_bars) if total_bars else 0.0
        )
    else:
        gross_pnl = float(sum([t.gross_pnl for t in trades]))
        fees      = float(sum([t.total_fee for t in trades]))
        net_pnl   = float(sum([t.net_pnl for t in trades]))

        wins   = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl <= 0]
        total_wins = float(sum([t.net_pnl for t in wins])) if wins else 0.0
        total_losses = float(abs(sum([t.net_pnl for t in losses]))) if losses else 0.0

        winrate = float(len(wins) / len(trades)) if len(trades) else 0.0
        profit_factor = float(total_wins / total_losses) if total_losses > 0 else float("inf")

        roll_max = eq.cummax()
        dd = (eq - roll_max) / roll_max.replace(0, float("nan"))
        max_dd = float(abs(dd.min())) if len(dd) else 0.0

        avg_trade = float(sum([t.net_pnl for t in trades]) / len(trades))

        m = Metrics(
            pair=pair, trades=int(len(trades)), winrate=winrate, gross_pnl=gross_pnl, fees=fees, net_pnl=net_pnl,
            max_drawdown=max_dd, avg_trade=avg_trade, profit_factor=profit_factor,
            total_bars=total_bars, bars_in_trade=bars_in_trade,
            time_in_market=(bars_in_trade / total_bars) if total_bars else 0.0
        )

\2"""

new_fast = pat.sub(rep, fast_block, count=1)
if new_fast == fast_block:
    raise SystemExit("Could not patch metrics section (pattern not matched).")

src2 = src[:m_fast.start()] + new_fast + src[fast_end:]
path.write_text(src2, encoding="utf-8")
print("[OK] Patched run_pair_fast: inlined metrics, removed compute_metrics dependency.")
