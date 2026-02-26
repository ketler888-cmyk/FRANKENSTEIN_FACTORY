import re
from pathlib import Path

def patch_file(path: Path) -> bool:
    if not path.exists():
        return False

    s = path.read_text(encoding="utf-8", errors="replace")

    # If file never mentions entry_signal, skip.
    if "entry_signal" not in s:
        return False

    changed = False

    # ---- 1) If def entry_signal(self): (no args) -> replace function block with compat ----
    # We replace the whole function body by detecting the def line and consuming until next "def " at same indent.
    def_pat = re.compile(r'(?m)^([ \t]*)def\s+entry_signal\s*\(\s*self\s*\)\s*:\s*\n')
    m = def_pat.search(s)

    compat_fn = None

    def build_compat(indent: str) -> str:
        # Conservative: do NOT block trades if data missing; only block when clearly invalid.
        # Accept both 5-indicator call and "row-like" call (single arg).
        return (
            f"{indent}def entry_signal(self, *args, **kwargs):\n"
            f"{indent}    \"\"\"Compat entry filter.\n"
            f"{indent}    Supports:\n"
            f"{indent}      - entry_signal(e9, e21, rr, cc, mid)\n"
            f"{indent}      - entry_signal(row)\n"
            f"{indent}    Returns True/False.\n"
            f"{indent}    \"\"\"\n"
            f"{indent}    try:\n"
            f"{indent}        if len(args) == 1 and args[0] is not None:\n"
            f"{indent}            row = args[0]\n"
            f"{indent}            # try mapping-like\n"
            f"{indent}            get = (row.get if hasattr(row, 'get') else None)\n"
            f"{indent}            if get:\n"
            f"{indent}                e9  = get('ema9', None)\n"
            f"{indent}                e21 = get('ema21', None)\n"
            f"{indent}                rr  = get('rsi', None)\n"
            f"{indent}                cc  = get('close', None)\n"
            f"{indent}                mid = get('bb_mid', None)\n"
            f"{indent}            else:\n"
            f"{indent}                # object-like\n"
            f"{indent}                e9  = getattr(row, 'ema9', None)\n"
            f"{indent}                e21 = getattr(row, 'ema21', None)\n"
            f"{indent}                rr  = getattr(row, 'rsi', None)\n"
            f"{indent}                cc  = getattr(row, 'close', None)\n"
            f"{indent}                mid = getattr(row, 'bb_mid', None)\n"
            f"{indent}        else:\n"
            f"{indent}            # expected: (e9,e21,rr,cc,mid)\n"
            f"{indent}            e9, e21, rr, cc, mid = (args + (None, None, None, None, None))[:5]\n"
            f"{indent}\n"
            f"{indent}        # if indicators missing -> do not block\n"
            f"{indent}        def _f(x):\n"
            f"{indent}            try:\n"
            f"{indent}                return float(x)\n"
            f"{indent}            except Exception:\n"
            f"{indent}                return None\n"
            f"{indent}\n"
            f"{indent}        e9f  = _f(e9)\n"
            f"{indent}        e21f = _f(e21)\n"
            f"{indent}        rrf  = _f(rr)\n"
            f"{indent}        ccf  = _f(cc)\n"
            f"{indent}        midf = _f(mid)\n"
            f"{indent}\n"
            f"{indent}        ok_trend = True\n"
            f"{indent}        if (e9f is not None) and (e21f is not None):\n"
            f"{indent}            ok_trend = (e9f >= e21f)\n"
            f"{indent}\n"
            f"{indent}        ok_rsi = True\n"
            f"{indent}        if rrf is not None:\n"
            f"{indent}            # wide default window (doesn't choke)\n"
            f"{indent}            ok_rsi = (rrf >= 30.0) and (rrf <= 70.0)\n"
            f"{indent}\n"
            f"{indent}        ok_bb = True\n"
            f"{indent}        if (ccf is not None) and (midf is not None):\n"
            f"{indent}            ok_bb = (ccf <= midf)\n"
            f"{indent}\n"
            f"{indent}        return bool(ok_trend and ok_rsi and ok_bb)\n"
            f"{indent}    except Exception:\n"
            f"{indent}        return True\n"
        )

    if m:
        indent = m.group(1)
        compat_fn = build_compat(indent)

        # find function end: next def at same indent
        start = m.start()
        # from end of def line
        pos = m.end()
        next_def = re.search(r'(?m)^%sdef\s+' % re.escape(indent), s[pos:])
        if next_def:
            end = pos + next_def.start()
        else:
            end = len(s)

        s = s[:start] + compat_fn + "\n" + s[end:]
        changed = True
    else:
        # ---- 2) If calls exist but def entry_signal missing -> inject into class BacktestRunner/BacktestRunnerV3 ----
        if "entry_signal(" in s and "def entry_signal" not in s:
            # pick first class that looks like runner
            cm = re.search(r'(?m)^class\s+(BacktestRunnerV3|BacktestRunner)\b[^\n]*:\s*\n', s)
            if cm:
                cls_name = cm.group(1)
                cls_start = cm.end()
                # find insertion point: after class docstring (if any) or after first line
                insert_at = cls_start
                # if there is an indented docstring right after:
                doc = re.search(r'(?s)\A([ \t]+)("""|\'\'\').*?\2\s*\n', s[cls_start:])
                if doc:
                    insert_at = cls_start + doc.end()
                    indent = doc.group(1)
                else:
                    # default indent inside class: 4 spaces
                    indent = "    "
                compat_fn = build_compat(indent)
                s = s[:insert_at] + compat_fn + "\n\n" + s[insert_at:]
                changed = True

    if changed:
        path.write_text(s, encoding="utf-8")
        print(f"OK: patched {path.name}")
    else:
        print(f"OK: no changes needed in {path.name}")

    return changed

any_changed = False
any_changed |= patch_file(Path("backtest_runner_v3.py"))
any_changed |= patch_file(Path("backtest_runner.py"))

print("DONE")