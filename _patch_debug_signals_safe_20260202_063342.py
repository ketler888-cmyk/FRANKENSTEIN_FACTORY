import io, re, sys

PATH = sys.argv[1]
with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

orig = src

# ---------------- A) argparse flag ----------------
def add_debug_flag(s: str) -> str:
    if "--debug_signals" in s:
        return s

    lines = s.splitlines(True)

    # insert after --no_optimize if exists
    for i, line in enumerate(lines):
        if 'add_argument("--no_optimize"' in line or "add_argument('--no_optimize'" in line:
            indent = re.match(r"^(\s*)", line).group(1)
            ins = f'{indent}parser.add_argument("--debug_signals", action="store_true", help="Print entry filter pass statistics (diagnostic)")\n'
            lines[i+1:i+1] = [ins]
            return "".join(lines)

    # else insert after parser = argparse.ArgumentParser(...)
    for i, line in enumerate(lines):
        if "argparse.ArgumentParser" in line and "parser" in line and "=" in line:
            indent = re.match(r"^(\s*)", line).group(1)
            ins = f'{indent}parser.add_argument("--debug_signals", action="store_true", help="Print entry filter pass statistics (diagnostic)")\n'
            lines[i+1:i+1] = [ins]
            return "".join(lines)

    # else insert near other add_argument lines (fallback): after first parser.add_argument
    for i, line in enumerate(lines):
        if "parser.add_argument(" in line:
            indent = re.match(r"^(\s*)", line).group(1)
            ins = f'{indent}parser.add_argument("--debug_signals", action="store_true", help="Print entry filter pass statistics (diagnostic)")\n'
            lines[i+1:i+1] = [ins]
            return "".join(lines)

    return s

# ---------------- B) runner flag assign ----------------
def add_runner_assign(s: str) -> str:
    if "runner.debug_signals" in s:
        return s
    lines = s.splitlines(True)
    for i, line in enumerate(lines):
        if re.search(r"\brunner\s*=\s*BacktestRunnerV3\s*\(", line):
            indent = re.match(r"^(\s*)", line).group(1)
            ins = f'{indent}runner.debug_signals = bool(getattr(args, "debug_signals", False))\n'
            lines[i+1:i+1] = [ins]
            return "".join(lines)
    return s

# ---------------- C) diag block in run_backtest_segment ----------------
DIAG = [
'if getattr(self, "debug_signals", False):\n',
'    try:\n',
'        n = int(len(df))\n',
'        if n > 0:\n',
'            trend = (df["ema_9"] > df["ema_21"])\n',
'            rsi   = (df["rsi_14"] < 35)\n',
'            bb    = (df["close"] < df["bb_middle"])\n',
'            mult  = float(params.get("min_atr_multiplier", 1.0)) if isinstance(params, dict) else 1.0\n',
'            atr   = (df["atr_14"] >= (atr_median * mult))\n',
'            all_ok = (trend & rsi & bb & atr)\n',
'            def pct(x): return 100.0 * float(x) / float(n)\n',
'            logger.info(\n',
'                f"[DEBUG_SIGNALS] bars={n} "\n',
'                f"trend={int(trend.sum())}({pct(trend.sum()):.2f}%) "\n',
'                f"rsi<35={int(rsi.sum())}({pct(rsi.sum()):.2f}%) "\n',
'                f"close<bbmid={int(bb.sum())}({pct(bb.sum()):.2f}%) "\n',
'                f"atr_gate(mult={mult:.3f})={int(atr.sum())}({pct(atr.sum()):.2f}%) "\n',
'                f"ALL={int(all_ok.sum())}({pct(all_ok.sum()):.4f}%)"\n',
'            )\n',
'    except Exception as e:\n',
'        try:\n',
'            logger.info(f"[DEBUG_SIGNALS] error: {e}")\n',
'        except Exception:\n',
'            pass\n'
]

def add_diag(s: str) -> str:
    if "[DEBUG_SIGNALS]" in s:
        return s

    lines = s.splitlines(True)

    # find run_backtest_segment block
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*def\s+run_backtest_segment\s*\(", line):
            start = i
            break
    if start is None:
        return s

    base_indent = re.match(r"^(\s*)", lines[start]).group(1)
    base_len = len(base_indent)

    end = len(lines)
    for j in range(start+1, len(lines)):
        if re.match(r"^\s*def\s+\w+\s*\(", lines[j]) and len(re.match(r"^(\s*)", lines[j]).group(1)) <= base_len:
            end = j
            break

    fn = lines[start:end]

    # anchor: atr_median assignment (this file uses atr_median, not median_atr)
    insert_at = None
    anchor_indent = None
    for k, line in enumerate(fn):
        if re.search(r"\batr_median\b\s*=", line):
            insert_at = k + 1
            anchor_indent = re.match(r"^(\s*)", line).group(1)
            break

    if insert_at is None:
        # fallback: before first "pos = PositionState()"
        for k, line in enumerate(fn):
            if "pos = PositionState()" in line:
                insert_at = k
                anchor_indent = re.match(r"^(\s*)", line).group(1)
                break

    if insert_at is None:
        return s

    # Insert a comment marker + diag with EXACT same indent level as surrounding code
    block = []
    block.append(anchor_indent + "# ===== DEBUG ENTRY FILTERS (diagnostic only; does NOT change trading logic) =====\n")
    for dl in DIAG:
        block.append(anchor_indent + dl)
    block.append(anchor_indent + "# ============================================================================\n")

    fn[insert_at:insert_at] = block
    new_lines = lines[:start] + fn + lines[end:]
    return "".join(new_lines)

# apply
src = add_debug_flag(src)
src = add_runner_assign(src)
src = add_diag(src)

if src == orig:
    print("PATCH: no changes (already patched or anchors not found)")
else:
    with io.open(PATH, "w", encoding="utf-8", newline="") as f:
        f.write(src)
    print("PATCH: applied OK")
