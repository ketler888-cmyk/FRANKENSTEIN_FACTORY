import os, sys, json, time, subprocess
from pathlib import Path

def run(cmd, env=None):
    print("[RUN]", " ".join(cmd), flush=True)
    p = subprocess.Popen(cmd, env=env)
    rc = p.wait()
    if rc != 0:
        raise SystemExit(rc)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--screen_frac", type=float, default=0.18)
    ap.add_argument("--screen_keep", type=int, default=60)
    ap.add_argument("--mode", choices=["grid","ga"], default="grid")
    ap.add_argument("--py", default=str(Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe"))
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    py = args.py

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["FR_WORKERS"] = str(args.workers)
    env["FR_SCREEN_FRAC"] = str(args.screen_frac)
    env["FR_SCREEN_KEEP"] = str(args.screen_keep)
    env["FR_MODE"] = args.mode

    # Contract:
    # - grid_test_fast.py / factory_ga.py MAY read FR_* env vars to enable acceleration
    # If they don't, this script still works as a future-proof orchestrator.

    if args.mode == "grid":
        script = root / "grid_test_fast.py"
        if not script.exists():
            raise SystemExit("grid_test_fast.py missing")
        run([py, str(script), "--pair", args.pair], env=env)
    else:
        script = root / "factory_ga.py"
        if not script.exists():
            raise SystemExit("factory_ga.py missing")
        run([py, str(script), "--pair", args.pair], env=env)

    # Always compact results into pyramid storage
    pyr = root / "ops" / "pyramid_store.py"
    db  = root / "results_ga" / "pyramid.duckdb"
    run([py, str(pyr), "--results_dir", str(root / "results"), "--db", str(db), "--top_n", "200"], env=env)

if __name__ == "__main__":
    main()
