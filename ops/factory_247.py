import os, sys, json, time, random, subprocess, traceback
from pathlib import Path
from datetime import datetime

def now_s():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def safe_write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def run(cmd, env=None, cwd=None, log_path: Path=None):
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="replace") as f:
            f.write(f"\n[{now_s()}] RUN: {' '.join(cmd)}\n")
            f.flush()
            p = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env, stdout=f, stderr=f)
            return p.wait()
    else:
        p = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env)
        return p.wait()

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["grid","ga"], default="grid")
    ap.add_argument("--pairs", type=str, default="BTCUSDT,ETHUSDT,ADAUSDT,SOLUSDT,AVAXUSDT")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--screen_frac", type=float, default=0.18)
    ap.add_argument("--screen_keep", type=int, default=60)
    ap.add_argument("--top_n_db", type=int, default=200)
    ap.add_argument("--sleep_ok", type=int, default=5)     # seconds between pair jobs
    ap.add_argument("--sleep_cycle", type=int, default=15) # seconds between full cycles
    ap.add_argument("--backoff_min", type=int, default=10)
    ap.add_argument("--backoff_max", type=int, default=120)
    ap.add_argument("--py", type=str, default="")
    ap.add_argument("--results_dir", type=str, default="results")
    ap.add_argument("--db", type=str, default="results_ga/pyramid.duckdb")
    ap.add_argument("--heartbeat", type=str, default="ops/heartbeat.json")
    ap.add_argument("--stop_file", type=str, default="ops/STOP_FACTORY")
    ap.add_argument("--pid_file", type=str, default="ops/factory_247.pid")
    ap.add_argument("--log_dir", type=str, default="logs/factory_247")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    py = args.py.strip() or str(root / ".venv" / "Scripts" / "python.exe")
    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]

    hb_path = (root / args.heartbeat)
    stop_path = (root / args.stop_file)
    pid_path = (root / args.pid_file)
    log_dir = (root / args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # write pid
    safe_write_json(pid_path, {"pid": os.getpid(), "ts": now_s(), "mode": args.mode, "pairs": pairs})

    # env knobs (optional hooks in scripts)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["FR_WORKERS"] = str(args.workers)
    env["FR_SCREEN_FRAC"] = str(args.screen_frac)
    env["FR_SCREEN_KEEP"] = str(args.screen_keep)
    env["FR_MODE"] = args.mode

    runner = root / "ops" / "run_screen_full.py"
    pyr = root / "ops" / "pyramid_store.py"
    results_dir = root / args.results_dir
    db_path = root / args.db

    cycle = 0
    consecutive_errors = 0

    while True:
        cycle += 1
        cycle_start = time.time()

        if stop_path.exists():
            safe_write_json(hb_path, {
                "ok": True, "state": "STOP_FILE_DETECTED", "ts": now_s(),
                "cycle": cycle, "note": f"stop file exists: {str(stop_path)}"
            })
            return 0

        # shuffle pairs to avoid bias
        random.shuffle(pairs)

        for pair in pairs:
            if stop_path.exists():
                safe_write_json(hb_path, {
                    "ok": True, "state": "STOP_FILE_DETECTED", "ts": now_s(),
                    "cycle": cycle, "pair": pair
                })
                return 0

            job_id = f"{cycle:06d}_{pair}_{args.mode}"
            log_path = log_dir / f"{job_id}.log"

            safe_write_json(hb_path, {
                "ok": True,
                "state": "RUN_PAIR",
                "ts": now_s(),
                "cycle": cycle,
                "pair": pair,
                "mode": args.mode,
                "workers": args.workers,
                "screen_frac": args.screen_frac,
                "screen_keep": args.screen_keep,
                "top_n_db": args.top_n_db,
                "log": str(log_path)
            })

            try:
                rc = run([py, str(runner), "--mode", args.mode, "--pair", pair,
                          "--workers", str(args.workers),
                          "--screen_frac", str(args.screen_frac),
                          "--screen_keep", str(args.screen_keep)],
                         env=env, cwd=root, log_path=log_path)
                if rc != 0:
                    raise RuntimeError(f"runner rc={rc}")

                # Always compact to pyramid (keeps best)
                rc2 = run([py, str(pyr),
                           "--results_dir", str(results_dir),
                           "--db", str(db_path),
                           "--top_n", str(args.top_n_db)],
                          env=env, cwd=root, log_path=log_path)
                if rc2 != 0:
                    raise RuntimeError(f"pyramid_store rc={rc2}")

                consecutive_errors = 0
                safe_write_json(hb_path, {
                    "ok": True,
                    "state": "PAIR_DONE",
                    "ts": now_s(),
                    "cycle": cycle,
                    "pair": pair,
                    "mode": args.mode,
                    "log": str(log_path)
                })
                time.sleep(max(0, int(args.sleep_ok)))

            except Exception as e:
                consecutive_errors += 1
                tb = traceback.format_exc(limit=50)
                safe_write_json(hb_path, {
                    "ok": False,
                    "state": "PAIR_ERROR",
                    "ts": now_s(),
                    "cycle": cycle,
                    "pair": pair,
                    "mode": args.mode,
                    "error": str(e),
                    "traceback": tb,
                    "log": str(log_path)
                })
                # exponential-ish backoff bounded
                backoff = min(args.backoff_max, args.backoff_min + consecutive_errors * 10)
                time.sleep(backoff)

        # end cycle heartbeat
        dur = time.time() - cycle_start
        safe_write_json(hb_path, {
            "ok": True,
            "state": "CYCLE_DONE",
            "ts": now_s(),
            "cycle": cycle,
            "duration_sec": round(dur, 2),
            "mode": args.mode,
            "pairs": pairs
        })
        time.sleep(max(0, int(args.sleep_cycle)))

if __name__ == "__main__":
    raise SystemExit(main())
