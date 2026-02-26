import sys, time
from pathlib import Path
from ga_adapters.runner_bridge import RunnerBridge

ROOT = Path(__file__).resolve().parent

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

    # total_bars can be stored in test_metrics too
    bars_in_metrics = _pick(tm, ["total_bars","bars"], None)
    if bars_in_metrics is not None:
        try:
            bars_in_metrics = int(bars_in_metrics)
        except:
            bars_in_metrics = None

    try: trades = int(trades)
    except: trades = 0
    try: net = float(net)
    except: net = 0.0
    try: fees = float(fees)
    except: fees = 0.0
    try: dd = float(dd)
    except: dd = 0.0

    return {
        "bars_total": bars_total,
        "train_bars": train_bars,
        "test_bars": test_bars,
        "bars_in_metrics": bars_in_metrics,
        "trades": trades,
        "net_pnl": net,
        "fees": fees,
        "max_drawdown": dd,
    }

def main():
    pair = "SOLUSDT"
    out = ROOT / "results_ga" / ("contract_test_" + time.strftime("%Y%m%d_%H%M%S"))
    rb = RunnerBridge(out_dir=str(out), python_exe=sys.executable)

    A = {"max_bars": 60000, "notional_usdt": 50.0, "entry_variant": 0, "rsi_buy": 35.0, "breakout_atr_k": 0.25, "no_optimize": True}
    B = {"max_bars": 20000, "notional_usdt": 50.0, "entry_variant": 1, "rsi_buy": 40.0, "breakout_atr_k": 0.10, "no_optimize": True}

    repA = rb.eval_once(pair, A, timeout_sec=900)
    repB = rb.eval_once(pair, B, timeout_sec=900)

    ma = extract(repA, pair)
    mb = extract(repB, pair)

    print("=== CONTRACT CHECK ===")
    print("A:", ma)
    print("B:", mb)

    ok_bars = (ma["bars_total"] != mb["bars_total"]) or (ma["bars_in_metrics"] != mb["bars_in_metrics"])
    ok_effect = (ma["trades"] != mb["trades"]) or (ma["net_pnl"] != mb["net_pnl"]) or (ma["fees"] != mb["fees"])

    if ok_bars and ok_effect:
        print("[OK] max_bars applied + params affect metrics")
        print("Output:", out.resolve())
        return 0

    if not ok_bars:
        print("[BAD] max_bars NOT applied (bars identical)")
    if not ok_effect:
        print("[BAD] params NOT affecting metrics (metrics identical)")
    print("Output:", out.resolve())
    return 2

if __name__ == "__main__":
    raise SystemExit(main())