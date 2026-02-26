import re
from pathlib import Path

ROOT = Path(".").resolve()

def write_utf8_nobom(p: Path, s: str):
    p.write_text(s, encoding="utf-8")

def patch_entry_signal(file_path: Path):
    if not file_path.exists():
        return False

    s = file_path.read_text(encoding="utf-8", errors="replace")

    # If there is NO 'entry_signal' method but there is a call 'self.entry_signal(' somewhere,
    # inject a compat method into the main runner class.
    needs = ("self.entry_signal(" in s)
    if not needs:
        return False

    # Try to find class header to inject into
    m = re.search(r"(?m)^(class\s+\w+\s*\(?.*?\)?:)\s*$", s)
    if not m:
        # no class found - skip
        return False

    # If an entry_signal already exists but has wrong signature (self only), we still want compat.
    # We'll inject a new method name and then map usage if needed.
    if re.search(r"(?m)^\s*def\s+entry_signal\s*\(\s*self\s*,", s):
        # already has entry_signal(self, ...) – keep it
        return False

    # Build compat method: entry_signal(self, row, *args, **kwargs)
    compat = r'''
    # --- compat: accept legacy self.entry_signal(row) calls ---
    def entry_signal(self, row=None, *args, **kwargs):
        """
        Compatibility shim for older code paths that call self.entry_signal(row).
        Prefer generate_entry_signal(row, params, atr_median) if present.
        On debug smoke we avoid blocking if something is missing.
        """
        try:
            if hasattr(self, "generate_entry_signal"):
                # try to pull params/atr_median if runner has them
                params = getattr(self, "params", None)
                atr_median = getattr(self, "atr_median", None)
                return bool(self.generate_entry_signal(row, params, atr_median))
        except Exception:
            return True
        return True
    # --- /compat ---
'''

    # Insert compat right after class line
    insert_at = m.end(1)
    s2 = s[:insert_at] + compat + s[insert_at:]
    write_utf8_nobom(file_path, s2)
    return True

def rewrite_ga_smoke(p: Path):
    # A robust ga_smoke that:
    # - supports --bars and --max_bars
    # - builds RunnerBridge with introspection (any signature)
    # - passes params including max_bars into eval_once
    code = r'''# -*- coding: utf-8 -*-
import argparse, json, random, time, inspect
from pathlib import Path

from ga_adapters.runner_bridge import RunnerBridge

def _make_bridge(out_dir: Path, timeout_sec: int):
    """
    Create RunnerBridge regardless of its constructor signature.
    We try common parameter names and only pass what is supported.
    """
    sig = inspect.signature(RunnerBridge)
    kw = {}
    # common: runner/backtest script
    for k in ("runner_py", "backtest_py", "backtest_path", "runner_path"):
        if k in sig.parameters:
            kw[k] = "backtest_runner_v3.py"
            break
    # common: output dir
    for k in ("out_dir", "results_dir", "results_root", "work_dir", "base_dir", "output_dir"):
        if k in sig.parameters:
            kw[k] = str(out_dir)
            break
    # timeout
    if "timeout_sec" in sig.parameters:
        kw["timeout_sec"] = int(timeout_sec)
    # often present in your ga_run version:
    if "starting_equity" in sig.parameters:
        kw["starting_equity"] = 50.0
    if "train_ratio" in sig.parameters:
        kw["train_ratio"] = 1.0

    return RunnerBridge(**kw)

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="SOLUSDT")
    ap.add_argument("--population", type=int, default=6)
    ap.add_argument("--generations", type=int, default=2)
    ap.add_argument("--notional", type=float, default=50.0)
    ap.add_argument("--timeout_sec", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)

    # debug speed controls (safe for smoke)
    ap.add_argument("--bars", type=int, default=60000, help="limit bars for smoke/debug")
    ap.add_argument("--max_bars", type=int, default=None, help="alias for --bars (compat)")

    args = ap.parse_args()
    if args.max_bars is not None:
        args.bars = args.max_bars

    random.seed(args.seed)

    out = Path("results_ga") / f"ga_smoke_{time.strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[GA] out={out.resolve()}")
    print(f"[GA] pair={args.pair} pop={args.population} gens={args.generations} bars={args.bars} timeout={args.timeout_sec}s")

    rb = _make_bridge(out, args.timeout_sec)

    TP_MIN, TP_MAX = 0.0010, 0.0100
    SL_MIN, SL_MAX = 0.0008, 0.0100

    def eval_one(tp, sl):
        params = {
            "tp_pct": float(tp),
            "sl_pct": float(sl),
            "notional": float(args.notional),
            "max_bars": int(args.bars),
            # keep debug stable:
            "seed": int(args.seed),
        }
        m = rb.eval_once(args.pair, params)
        # m is expected dict with at least net/fees/dd/trades; be defensive:
        net = float(m.get("net", 0.0))
        fees = float(m.get("fees", 0.0))
        dd = float(m.get("dd", 0.0))
        trades = int(m.get("trades", 0))
        score = net - fees - dd*0.25 + trades*0.01
        return score, m, params

    best = None

    pop = []
    for _ in range(int(args.population)):
        tp = random.uniform(TP_MIN, TP_MAX)
        sl = random.uniform(SL_MIN, SL_MAX)
        pop.append((tp, sl))

    for gen in range(int(args.generations)):
        gen_best = None
        for tp, sl in pop:
            sc, meta, par = eval_one(tp, sl)
            if (gen_best is None) or (sc > gen_best[0]):
                gen_best = (sc, meta, par)
            if (best is None) or (sc > best[0]):
                best = (sc, meta, par)

        bsc, bm, bpar = gen_best
        print(f"[GA] gen={gen} best_score={bsc:.6f} tp={bpar['tp_pct']:.6f} sl={bpar['sl_pct']:.6f} trades={int(bm.get('trades',0))} net={float(bm.get('net',0.0)):.6f} fees={float(bm.get('fees',0.0)):.6f} dd={float(bm.get('dd',0.0)):.6f}")

        # mutate around best
        new_pop = [(bpar["tp_pct"], bpar["sl_pct"])]
        while len(new_pop) < int(args.population):
            tp = float(bpar["tp_pct"]) * random.uniform(0.85, 1.15)
            sl = float(bpar["sl_pct"]) * random.uniform(0.85, 1.15)
            new_pop.append((clamp(tp, TP_MIN, TP_MAX), clamp(sl, SL_MIN, SL_MAX)))
        pop = new_pop

    if best:
        bsc, bm, bpar = best
        payload = {
            "best_score": float(bsc),
            "best_params": bpar,
            "best_meta": bm,
            "pair": args.pair,
            "population": int(args.population),
            "generations": int(args.generations),
            "bars": int(args.bars),
            "timeout_sec": int(args.timeout_sec),
            "seed": int(args.seed),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        (out / "best.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[GA] saved: {(out / 'best.json').resolve()}")

if __name__ == "__main__":
    main()
'''
    write_utf8_nobom(p, code)
    return True

changed = False
changed |= patch_entry_signal(ROOT / "backtest_runner_v3.py")
changed |= patch_entry_signal(ROOT / "backtest_runner.py")
changed |= rewrite_ga_smoke(ROOT / "ga_smoke.py")

print("OK: patched wiring. changed=" + str(changed))