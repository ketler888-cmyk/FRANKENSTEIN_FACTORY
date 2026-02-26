from pathlib import Path
import re

FACTORY = Path(r'''C:\Users\user\Desktop\Франкинштэйн\factory_ga.py''')
RUNNER  = Path(r'''C:\Users\user\Desktop\Франкинштэйн\ga_adapters\runner_bridge.py''')

def insert_after_first(s: str, pattern: str, insert: str) -> str:
    m = re.search(pattern, s, flags=re.M)
    if not m:
        return s
    pos = m.end()
    return s[:pos] + insert + s[pos:]

def patch_factory():
    s = FACTORY.read_text(encoding="utf-8", errors="replace")

    # 1) Ensure sys/time imported (some builds have them already)
    if not re.search(r'(?m)^\s*import\s+sys\b', s):
        # best effort: extend the main import line "import argparse, random, time, json, os, sys, logging" already includes sys/time usually
        pass

    # 2) After args=parse_args, ensure out_dir + logging into per-pair folder
    if "out = _ensure_out_dir" not in s:
        insert = (
            "\n"
            "    # --- FRANKEN: define per-pair out dir + file logging ---\n"
            "    out = _ensure_out_dir('.', args.pair)\n"
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
            "        # python <3.8 fallback (no force)\n"
            "        logging.basicConfig(\n"
            "            level=logging.INFO,\n"
            "            format='%(asctime)s [%(levelname)s] %(message)s',\n"
            "            handlers=[\n"
            "                logging.FileHandler(str(log_path), encoding='utf-8'),\n"
            "                logging.StreamHandler(sys.stdout),\n"
            "            ],\n"
            "        )\n"
        )
        s2 = insert_after_first(s, r'(?m)^\s*args\s*=\s*parser\.parse_args\(\)\s*$', insert)
        if s2 == s:
            raise SystemExit("PATCH_FACTORY: cannot find args = parser.parse_args() to insert out/log init")
        s = s2

    # 3) Ensure RunnerBridge(out_dir=out) is passed (prevents NoneType / 'str')
    # Find first RunnerBridge( ... ) call and inject out_dir if missing
    m = re.search(r'RunnerBridge\s*\(', s)
    if not m:
        raise SystemExit("PATCH_FACTORY: RunnerBridge( not found")
    # crude but safe: check within next 300 chars if out_dir already present
    window = s[m.start():m.start()+300]
    if "out_dir" not in window:
        s = s[:m.end()] + "out_dir=out, " + s[m.end():]

    FACTORY.write_text(s, encoding="utf-8")
    print("PATCH_FACTORY_OK")

def patch_runner_bridge():
    if not RUNNER.exists():
        print("PATCH_RUNNER_SKIP (file missing)")
        return

    s = RUNNER.read_text(encoding="utf-8", errors="replace")
    if "FRANKEN_DEFAULT_OUTDIR" in s:
        print("PATCH_RUNNER_ALREADY")
        return

    # Make out_dir robust inside __init__ (or class init area)
    # Try to locate "def __init__(... out_dir" and then set self.out_dir safely.
    # We'll inject a small block after "self.out_dir = out_dir" or after params are assigned.
    injected = False

    # Pattern A: existing assignment
    patA = r'(?m)^(?P<indent>\s*)self\.out_dir\s*=\s*out_dir\s*$'
    mA = re.search(patA, s)
    if mA:
        ind = mA.group("indent")
        block = (
            f"{ind}# FRANKEN_DEFAULT_OUTDIR\n"
            f"{ind}from pathlib import Path as _P\n"
            f"{ind}self.out_dir = _P(out_dir) if out_dir else _P('.')\n"
        )
        s = re.sub(patA, block.rstrip("\n"), s, count=1)
        injected = True

    # Pattern B: no explicit assignment; inject after python_exe assignment if present
    if not injected:
        patB = r'(?m)^(?P<indent>\s*)self\.python_exe\s*=\s*python_exe\s*$'
        mB = re.search(patB, s)
        if mB:
            ind = mB.group("indent")
            block = (
                f"{mB.group(0)}\n"
                f"{ind}# FRANKEN_DEFAULT_OUTDIR\n"
                f"{ind}from pathlib import Path as _P\n"
                f"{ind}self.out_dir = _P(out_dir) if out_dir else _P('.')\n"
            )
            s = s[:mB.start()] + block + s[mB.end():]
            injected = True

    if not injected:
        print("PATCH_RUNNER_WARN (no insertion point found)")
    else:
        RUNNER.write_text(s, encoding="utf-8")
        print("PATCH_RUNNER_OK")

if __name__ == "__main__":
    patch_factory()
    patch_runner_bridge()