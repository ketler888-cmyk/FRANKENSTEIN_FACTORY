from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
FACTORY = ROOT / "factory_ga.py"
RUNNER  = ROOT / "ga_adapters" / "runner_bridge.py"

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def _write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")

def patch_runner_bridge():
    if not RUNNER.exists():
        print("PATCH_RUNNER_SKIP (no file)", RUNNER)
        return

    s = _read(RUNNER)
    changed = False

    # 1) Make sure eval_once is considered usable
    # Typical patterns we saw in your logs: bridge has eval_once but code says "no usable method"
    # We'll add eval_once to any tuple/list of allowed names if present
    s2 = re.sub(
        r'(\(\s*["\']run_backtest["\']\s*,\s*["\']run["\']\s*,\s*["\']__call__["\']\s*\))',
        r'("eval_once","run_backtest","run","__call__")',
        s
    )
    s2 = re.sub(
        r'(\[\s*["\']run_backtest["\']\s*,\s*["\']run["\']\s*,\s*["\']__call__["\']\s*\])',
        r'["eval_once","run_backtest","run","__call__"]',
        s2
    )
    if s2 != s:
        s = s2
        changed = True

    # 2) Ensure out_dir is always a Path (avoid None / operator crash)
    # We try to patch __init__ assigning self.out_dir
    # If it already exists but allows None -> convert None to "."
    if "self.out_dir" in s:
        s3 = re.sub(
            r'(?m)^(?P<i>\s*)self\.out_dir\s*=\s*(?P<rhs>.+?)\s*$',
            lambda m: (m.group(0)
                       if "Path(" in m.group("rhs") or "_P(" in m.group("rhs")
                       else f'{m.group("i")}self.out_dir = Path({m.group("rhs").strip()}) if {m.group("rhs").strip()} else Path(".")'),
            s
        )
        if s3 != s:
            s = s3
            changed = True

    # As fallback: if we can find __init__(..., out_dir=None) we inject a safe normalization after signature
    if "def __init__(" in s and "out_dir" in s and "Path(" not in s:
        # minimal safe inject: after first line of __init__ block
        m = re.search(r"(?m)^(?P<defi>\s*def\s+__init__\([^\)]*\)\s*:\s*)$", s)
        if m:
            # Find next line indent
            line_end = m.end()
            # infer body indent = def indent + 4 spaces (best-effort)
            def_indent = re.match(r"^\s*", m.group("defi")).group(0)
            body_indent = def_indent + "    "
            inject = (
                f'{body_indent}from pathlib import Path as _P\n'
                f'{body_indent}try:\n'
                f'{body_indent}    out_dir = out_dir if out_dir else "."\n'
                f'{body_indent}except Exception:\n'
                f'{body_indent}    out_dir = "."\n'
                f'{body_indent}self.out_dir = _P(out_dir)\n'
            )
            if "self.out_dir = _P(out_dir)" not in s:
                s = s[:line_end] + "\n" + inject + s[line_end:]
                changed = True

    if changed:
        _write(RUNNER, s)
        print("PATCH_RUNNER_OK")
    else:
        print("PATCH_RUNNER_NOCHANGE")

def patch_factory_ga():
    s = _read(FACTORY)
    orig = s

    # Ensure imports exist (we only add if missing)
    if re.search(r"(?m)^\s*import\s+logging\b", s) and not re.search(r"(?m)^\s*import\s+traceback\b", s):
        s = re.sub(r"(?m)^\s*import\s+logging\b.*$", lambda m: m.group(0) + "\nimport traceback", s, count=1)

    # Ensure helper _ensure_out_dir exists (once)
    if "_ensure_out_dir(" not in s:
        # Insert after imports block (best-effort: after last top import/from line)
        lines = s.splitlines(True)
        idx = 0
        last_imp = -1
        for i,ln in enumerate(lines[:200]):
            if re.match(r"^\s*(import|from)\s+", ln):
                last_imp = i
        if last_imp >= 0:
            helper = (
                "\n"
                "def _ensure_out_dir(root_dir, pair):\n"
                "    out = Path(root_dir) / \"results_ga\" / \"factory_top\" / str(pair)\n"
                "    out.mkdir(parents=True, exist_ok=True)\n"
                "    return out\n"
                "\n"
            )
            lines.insert(last_imp+1, helper)
            s = "".join(lines)

    # Find args=parse_args (more flexible than exact string)
    m = re.search(r"(?m)^(?P<i>\s*)args\s*=\s*.*parse_args\(\)\s*$", s)
    if not m:
        raise SystemExit("PATCH_FACTORY: cannot find args = ...parse_args() line")

    indent = m.group("i")
    insert_pos = m.end()

    inject = (
        f"\n{indent}# ---- FRANKEN TRACE/OUTDIR/LOG SETUP ----\n"
        f"{indent}out = _ensure_out_dir('.', args.pair)\n"
        f"{indent}log_path = out / 'log.txt'\n"
        f"{indent}root = logging.getLogger()\n"
        f"{indent}root.setLevel(logging.INFO)\n"
        f"{indent}# avoid duplicate handlers on re-run\n"
        f"{indent}if not any(getattr(h, 'baseFilename', None) == str(log_path) for h in root.handlers):\n"
        f"{indent}    fh = logging.FileHandler(str(log_path), encoding='utf-8')\n"
        f"{indent}    fh.setLevel(logging.INFO)\n"
        f"{indent}    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')\n"
        f"{indent}    fh.setFormatter(fmt)\n"
        f"{indent}    root.addHandler(fh)\n"
        f"{indent}logging.info('[TRACE] OUTDIR=%s', out)\n"
        f"{indent}logging.info('[TRACE] ARGS=%s', vars(args))\n"
        f"{indent}_trace_eval_calls = 0\n"
        f"{indent}_trace_eval_fail  = 0\n"
        f"{indent}# ---- END TRACE SETUP ----\n"
    )

    # Only inject once
    if "[TRACE] OUTDIR=" not in s:
        s = s[:insert_pos] + inject + s[insert_pos:]

    # Add trace around any "EVAL_FAIL" logging lines (keep stable, do not change indentation blindly)
    # We also ensure exceptions print traceback into log
    if "traceback.format_exc()" not in s:
        s = re.sub(
            r"(?m)^(?P<i>\s*)logging\.error\(\s*f?['\"]EVAL_FAIL:.*?\)\s*$",
            r"\g<i>logging.error(traceback.format_exc())\n\g<0>",
            s,
            count=1
        )

    # Add summary before GA FINISHED (if present)
    if "[TRACE] SUMMARY" not in s:
        s = re.sub(
            r"(?m)^(?P<i>\s*)logging\.info\(\s*['\"]GA FINISHED['\"]\s*\)\s*$",
            r"\g<i>logging.info('[TRACE] SUMMARY eval_calls=%s eval_fail=%s', _trace_eval_calls, _trace_eval_fail)\n\g<0>",
            s,
            count=1
        )

    if s != orig:
        _write(FACTORY, s)
        print("PATCH_FACTORY_OK")
    else:
        print("PATCH_FACTORY_NOCHANGE")

def main():
    patch_factory_ga()
    patch_runner_bridge()

if __name__ == "__main__":
    main()