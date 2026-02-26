population = [
    (3, 30.0, 0.4),
    (3, 35.0, 0.3),
    (3, 40.0, 0.2),
    (3, 45.0, 0.5),
    (3, 50.0, 0.1),
    (3, 55.0, 0.6),
    (3, 60.0, 0.2),
    (3, 65.0, 0.3),
]

import time, argparse, random, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from ga_adapters.runner_bridge import RunnerBridge

def _pick(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

def extract(rep: dict, pair: str):
    p = rep.get("pairs", {}).get(pair, {})
    summ = rep.get("summary", {})

    train_bars = int(_pick(p, ["train_bars"], 0) or 0)
    test_bars  = int(_pick(p, ["test_bars"], 0) or 0)
    bars_total = train_bars + test_bars

    tm = p.get("test_metrics") or {}

    trades = _pick(tm, ["trades","total_trades"], None)
    if trades is None:
        trades = _pick(summ, ["total_test_trades"], 0)

    net = _pick(tm, ["net_pnl","pnl","net"], None)
    if net is None:
        net = _pick(summ, ["total_test_net_pnl"], 0.0)

    fees = _pick(tm, ["fees","total_fees","fees_total"], None)
    if fees is None:
        fees = _pick(summ, ["total_test_fees"], 0.0)

    dd = _pick(tm, ["max_drawdown","max_dd","dd"], None)
    if dd is None:
        dd = _pick(summ, ["avg_test_drawdown"], 0.0)

    bars_in_metrics = _pick(tm, ["total_bars","bars"], None)
    if bars_in_metrics is not None:
        try: bars_in_metrics = int(bars_in_metrics)
        except: bars_in_metrics = None

    try: trades = int(trades)
    except: trades = 0
    try: net = float(net)
    except: net = 0.0
    try: fees = float(fees)
    except: fees = 0.0
    try: dd = float(dd)
    except: dd = 0.0

    return {"trades": trades, "net_pnl": net, "fees": fees, "max_dd": dd, "bars": bars_total, "bars_in_metrics": bars_in_metrics}

def score(mm):
    if mm["trades"] <= 0:
        return 0.0
    return max(0.0, (mm["net_pnl"] - mm["fees"]) - 0.25*abs(mm["max_dd"]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="SOLUSDT")
    ap.add_argument("--population", type=int, default=8)
    ap.add_argument("--generations", type=int, default=3)
    ap.add_argument("--bars", type=int, default=60000)
    ap.add_argument("--timeout_sec", type=int, default=900)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--notional", type=float, default=50.0)
    args = ap.parse_args()

    random.seed(args.seed)
    out = ROOT / "results_ga" / ("ga_smoke_" + time.strftime("%Y%m%d_%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    rb = RunnerBridge(out_dir=str(out), python_exe=sys.executable)

    pop = population
    best = None

    for gen in range(args.generations):
        scored = []
        for ev, rsi_buy, bok in pop:
            cfg = {
                "max_bars": int(args.bars),
                "notional_usdt": float(args.notional),
                "entry_variant": int(ev),
                "rsi_buy": float(rsi_buy),
                "use_trend_filter": 1,
                "use_bb_filter": 1,
                "breakout_lookback": 20,
                "breakout_atr_k": float(bok),
                "no_optimize": True,
            }
            rep = rb.eval_once(args.pair, cfg, timeout_sec=args.timeout_sec)
            mm = extract(rep, args.pair)
            sc = score(mm)
            scored.append((sc, cfg, mm))

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0]
        sc, cfg, mm = best
        print(f"[SMOKE] gen={gen} best={sc:.6f} ev={cfg['entry_variant']} rsi_buy={cfg['rsi_buy']:.2f} bok={cfg['breakout_atr_k']:.3f} trades={mm['trades']} net={mm['net_pnl']:.4f} fees={mm['fees']:.4f} dd={mm['max_dd']:.6f} bars={mm['bars']} (m_bars={mm['bars_in_metrics']})")

        elites = [scored[i][1] for i in range(min(2, len(scored)))]
        new_pop = [(e["entry_variant"], e["rsi_buy"], e["breakout_atr_k"]) for e in elites]

        while len(new_pop) < args.population:
            base = scored[random.randint(0, min(3, len(scored)-1))][1]
            ev = base["entry_variant"]
            rsi_buy = base["rsi_buy"] * random.uniform(0.85, 1.15)
            bok = base["breakout_atr_k"] * random.uniform(0.80, 1.20)
            rsi_buy = max(10.0, min(60.0, rsi_buy))
            bok = max(0.01, min(2.0, bok))
            new_pop.append((ev, rsi_buy, bok))

        pop = new_pop

    if best:
        sc, cfg, mm = best
        payload = {"best_score": sc, "best_cfg": cfg, "best_metrics": mm, "pair": args.pair, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        (out / "best.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[SMOKE] saved:", (out / "best.json").resolve())

if __name__ == "__main__":
    main()
