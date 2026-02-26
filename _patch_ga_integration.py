import re
from pathlib import Path

root = Path(".").resolve()

# --- 1) Patch runner_bridge.py: use sys.executable instead of "python" everywhere ---
rb = root / "ga_adapters" / "runner_bridge.py"
s = rb.read_text(encoding="utf-8", errors="replace")

if "import sys" not in s:
    # add after first import block
    s = re.sub(r'(?m)^(import\s+[^\n]+\n)+', lambda m: m.group(0) + "import sys\n", s, count=1)

# replace ["python", ...] -> [sys.executable, ...]
s2 = re.sub(r'\[\s*["\']python["\']\s*,', r'[sys.executable,', s)

# also replace subprocess help probe if it uses ["python", ...]
s2 = re.sub(r'(?m)\[\s*["\']python["\']\s*,', r'[sys.executable,', s2)

rb.write_text(s2, encoding="utf-8")
print("OK: patched ga_adapters/runner_bridge.py -> sys.executable")

# --- 2) Patch backtest_runner_v3.py: ensure entry_signal supports 5-args call ---
bt = root / "backtest_runner_v3.py"
t = bt.read_text(encoding="utf-8", errors="replace")

# If generate_entry_signal calls self.entry_signal(e9,e21,rr,cc,mid), add compat entry_signal if missing
needs_compat = "self.entry_signal(" in t and re.search(r"def\s+entry_signal\s*\(", t) is None

if needs_compat:
    # Insert compat method inside BacktestRunner class (after class line)
    m = re.search(r'(?m)^class\s+BacktestRunner\s*:\s*$', t)
    if not m:
        raise SystemExit("Cannot find 'class BacktestRunner:' in backtest_runner_v3.py")

    insert_at = m.end()

    compat = """

    # --- compat: old GA expects entry_signal(e9,e21,rr,cc,mid) ---
    # e9=ema9, e21=ema21, rr=rsi, cc=close, mid=bb_mid (naming from older runners)
    def entry_signal(self, e9, e21, rr, cc, mid):
        try:
            # trend filter (ema9 above ema21)
            ok_trend = (e9 is not None) and (e21 is not None) and (float(e9) > float(e21))
        except Exception:
            ok_trend = False

        # rsi filter: prefer oversold entries
        rsi_buy = getattr(self, "RSI_BUY_MIN", None)
        if rsi_buy is None:
            rsi_buy = getattr(self, "rsi_buy_min", 32)

        try:
            ok_rsi = (rr is not None) and (float(rr) <= float(rsi_buy))
        except Exception:
            ok_rsi = False

        # bb filter: price below mid-band as mean-reversion entry
        try:
            ok_bb = (cc is not None) and (mid is not None) and (float(cc) <= float(mid))
        except Exception:
            ok_bb = True  # do not block if bb not available

        return bool(ok_trend and ok_rsi and ok_bb)
    # --- /compat ---
"""
    t2 = t[:insert_at] + compat + t[insert_at:]
    bt.write_text(t2, encoding="utf-8")
    print("OK: injected compat entry_signal(e9,e21,rr,cc,mid) into BacktestRunner")
else:
    print("OK: backtest_runner_v3.py already has entry_signal or does not need compat")

print("DONE")