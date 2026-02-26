from pathlib import Path
import re

FACTORY = Path(r'''C:\Users\user\Desktop\Франкинштэйн\factory_ga.py''')
RUNNER  = Path(r'''C:\Users\user\Desktop\Франкинштэйн\ga_adapters\runner_bridge.py''')

def patch_factory():
    s = FACTORY.read_text(encoding="utf-8", errors="replace")

    # ensure we have sys imported somewhere (usually already in your combined import line)
    if not re.search(r'(?m)^\s*import\s+sys\b', s):
        # best effort: add a standalone import sys after first import line
        m = re.search(r'(?m)^(import[^\n]*\n)', s)
        if m:
            s = s[:m.end()] + "import sys\n" + s[m.end():]

    # INSERT after first line containing parse_args(
    if "FRANKEN: define per-pair out dir + file logging" not in s:
        m = re.search(r'(?m)^.*parse_args\s*\(.*$', s)
        if not m:
            raise SystemExit("PATCH_FACTORY: cannot find any line containing parse_args(")

        insert = (
            "\n"
            "    # --- FRANKEN: define per-pair out dir + file logging ---\n"
            "    out = _ensure_out_dir('.', getattr(args,'pair','UNKNOWN'))\n"
            "    log_path = out / 'log.txt'\n"
            "    try:\n"
            "        logging.basicConfig(\n"
            "            level=logging.INFO,\n"
            "            format='%(asctime)s [%(levelname)s] %(message)s',\n"
            "            handlers=[\n"
            "                logging.FileHandler(str(log_path), encoding='utf-8'),\n"
            "                logging.StreamHandler(sys.stdout),\n"
            "            ],\n"
            "            force=True,\n"
            "        )\n"
            "    except TypeError:\n"
            "        logging.basicConfig(\n"
            "            level=logging.INFO,\n"
            "            format='%(asctime)s [%(levelname)s] %(message)s',\n"
            "            handlers=[\n"
            "                logging.FileHandler(str(log_path), encoding='utf-8'),\n"
            "                logging.StreamHandler(sys.stdout),\n"
            "            ],\n"
            "        )\n"
            "    logging.info('[TRACE] ARGS=%s', vars(args) if hasattr(args,'__dict__') else args)\n"
        )
        # insert right after that line
        s = s[:m.end()] + insert + s[m.end():]

    # ensure RunnerBridge gets out_dir=out
    # patch first occurrence only; if already has out_dir in next ~400 chars, skip
    m = re.search(r'RunnerBridge\s*\(', s)
    if not m:
        raise SystemExit("PATCH_FACTORY: RunnerBridge( not found")
    window = s[m.start():m.start()+450]
    if "out_dir" not in window:
        s = s[:m.end()] + "out_dir=out, " + s[m.end():]

    FACTORY.write_text(s, encoding="utf-8")
    print("PATCH_FACTORY_OK")

def patch_runner_bridge():
    if not RUNNER.exists():
        print("PATCH_RUNNER_SKIP (missing)")
        return

    s = RUNNER.read_text(encoding="utf-8", errors="replace")
    if "FRANKEN_DEFAULT_OUTDIR" in s:
        print("PATCH_RUNNER_ALREADY")
        return

    injected = False

    # Replace self.out_dir = out_dir  -> safe Path
    pat = r'(?m)^(?P<indent>\s*)self\.out_dir\s*=\s*out_dir\s*$'
    m = re.search(pat, s)
    if m:
        ind = m.group("indent")
        block = (
            f"{ind}# FRANKEN_DEFAULT_OUTDIR\n"
            f"{ind}from pathlib import Path as _P\n"
            f"{ind}self.out_dir = _P(out_dir) if out_dir else _P('.')\n"
        )
        s = re.sub(pat, block.rstrip("\n"), s, count=1)
        injected = True

    # If there was no assignment, inject after python_exe assignment
    if not injected:
        pat2 = r'(?m)^(?P<indent>\s*)self\.python_exe\s*=\s*python_exe\s*$'
        m2 = re.search(pat2, s)
        if m2:
            ind = m2.group("indent")
            ins = (
                f"{m2.group(0)}\n"
                f"{ind}# FRANKEN_DEFAULT_OUTDIR\n"
                f"{ind}from pathlib import Path as _P\n"
                f"{ind}self.out_dir = _P(out_dir) if out_dir else _P('.')\n"
            )
            s = s[:m2.start()] + ins + s[m2.end():]
            injected = True

    if injected:
        RUNNER.write_text(s, encoding="utf-8")
        print("PATCH_RUNNER_OK")
    else:
        print("PATCH_RUNNER_WARN (no insertion point)")

if __name__ == "__main__":
    patch_factory()
    patch_runner_bridge()