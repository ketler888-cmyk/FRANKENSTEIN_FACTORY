import io, os, sys, re

PATH = sys.argv[1]
with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

orig = src

def already_has_flag(s: str) -> bool:
    return "--debug_signals" in s or "debug_signals" in s and "DEBUG_SIGNALS" in s

# ---- A) Add argparse flag ----
def add_argparse_flag(s: str) -> str:
    if "--debug_signals" in s:
        return s

    lines = s.splitlines(True)

    # Heuristic 1: insert after a parser.add_argument("--no_optimize"...)
    for i, line in enumerate(lines):
        if 'add_argument("--no_optimize"' in line or "add_argument('--no_optimize'" in line:
            indent = re.match(r"^(\s*)", line).group(1)
            ins = [
                f'{indent}parser.add_argument("--debug_signals", action="store_true", help="Print entry filter pass statistics (diagnostic)")\n'
            ]
            lines[i+1:i+1] = ins
            return "".join(lines)

    # Heuristic 2: insert right after parser = argparse.ArgumentParser(...)
    for i, line in enumerate(lines):
        if "argparse.ArgumentParser" in line and "parser" in line and "=" in line:
            indent = re.match(r"^(\s*)", line).group(1)
            ins = [
                f'{indent}parser.add_argument("--debug_signals", action="store_true", help="Print entry filter pass statistics (diagnostic)")\n'
            ]
            lines[i+1:i+1] = ins
            return "".join(lines)

    # Heuristic 3: insert after "import argparse" (fallback, rare)
    for i, line in enumerate(lines):
        if re.match(r"^\s*import\s+argparse\s*$", line):
            ins = ['\n# debug flag injected by patcher\n']
            lines[i+1:i+1] = ins
            return "".join(lines)

    return s

# ---- B) Pass flag into runner ----
def add_runner_flag_assign(s: str) -> str:
    if "runner.debug_signals" in s:
        return s

    lines = s.splitlines(True)
    for i, line in enumerate(lines):
        # runner = BacktestRunnerV3(...)
        if re.search(r"\brunner\s*=\s*BacktestRunnerV3\s*\(", line):
            indent = re.match(r"^(\s*)", line).group(1)
            ins = [f'{indent}runner.debug_signals = bool(getattr(args, "debug_signals", False))\n']
            # insert AFTER the runner= line (not inside parentheses)
            lines[i+1:i+1] = ins
            return "".join(lines)
    return s

# ---- C) Insert diagnostic block in run_backtest_segment ----
DIAG_BLOCK = r'''
        # ===== DEBUG ENTRY FILTERS (diagnostic only; does NOT change trading logic) =====
        if getattr(self, "debug_signals", False):
            try:
                n = int(len(df))
                if n > 0:
                    trend = (df["ema_9"] > df["ema_21"])
                    rsi   = (df["rsi_14"] < 35)
                    bb    = (df["close"] < df["bb_middle"])
                    mult  = float(params.get("min_atr_multiplier", 1.0)) if isinstance(params, dict) else 1.0
                    atr   = (df["atr_14"] >= (median_atr * mult))
                    all_ok = (trend & rsi & bb & atr)

                    def pct(x): return 100.0 * float(x) / float(n)

                    logger.info(
                        f"[DEBUG_SIGNALS] bars={n} "
                        f"trend={int(trend.sum())}({pct(trend.sum()):.2f}%) "
                        f"rsi<35={int(rsi.sum())}({pct(rsi.sum()):.2f}%) "
                        f"close<bbmid={int(bb.sum())}({pct(bb.sum()):.2f}%) "
                        f"atr_gate(mult={mult:.3f})={int(atr.sum())}({pct(atr.sum()):.2f}%) "
                        f"ALL={int(all_ok.sum())}({pct(all_ok.sum()):.4f}%)"
                    )
            except Exception as e:
                try:
                    logger.info(f"[DEBUG_SIGNALS] error: {e}")
                except Exception:
                    pass
        # ============================================================================

'''

def add_diag_block(s: str) -> str:
    if "[DEBUG_SIGNALS]" in s or "DEBUG ENTRY FILTERS" in s:
        return s

    lines = s.splitlines(True)

    # locate def run_backtest_segment
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*def\s+run_backtest_segment\s*\(", line):
            start = i
            break
    if start is None:
        return s

    # find end of function block (next def at same or lower indent)
    base_indent = re.match(r"^(\s*)", lines[start]).group(1)
    base_len = len(base_indent)

    end = len(lines)
    for j in range(start+1, len(lines)):
        if re.match(r"^\s*def\s+\w+\s*\(", lines[j]) and len(re.match(r"^(\s*)", lines[j]).group(1)) <= base_len:
            end = j
            break

    fn = lines[start:end]

    # Prefer anchor: first line that assigns median_atr
    insert_at = None
    for k, line in enumerate(fn):
        if re.search(r"\bmedian_atr\b\s*=", line):
            insert_at = k + 1
            break

    # Fallback anchor: a line computing median of atr_14
    if insert_at is None:
        for k, line in enumerate(fn):
            if "atr_14" in line and ".median" in line:
                insert_at = k + 1
                break

    # Fallback anchor: just before the main for-loop over bars
    if insert_at is None:
        for k, line in enumerate(fn):
            if re.search(r"^\s*for\s+\w+\s+in\s+range\s*\(", line):
                insert_at = k
                break

    if insert_at is None:
        return s

    # Determine indent for inserted block: one level deeper than function def
    body_indent = base_indent + (" " * 4)

    block_lines = []
    for bl in DIAG_BLOCK.splitlines(True):
        if bl.strip() == "":
            block_lines.append(bl)
        else:
            block_lines.append(body_indent + bl.lstrip("\n"))

    fn[insert_at:insert_at] = block_lines
    new_lines = lines[:start] + fn + lines[end:]
    return "".join(new_lines)

# Apply patches
src = add_argparse_flag(src)
src = add_runner_flag_assign(src)
src = add_diag_block(src)

if src == orig:
    print("PATCH: no changes needed (already patched or anchors not found)")
else:
    with io.open(PATH, "w", encoding="utf-8", newline="") as f:
        f.write(src)
    print("PATCH: applied OK")
