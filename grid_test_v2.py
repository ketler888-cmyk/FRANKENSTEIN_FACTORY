import os, json, time, csv
from pathlib import Path
import pandas as pd

from backtest_runner import BacktestRunner

def pick_data_dir(root: Path) -> Path:
    p = root / "SCALPING_DATA_PARQUET"
    return p if p.exists() else (root / "SCALPING_DATA")

def load_ohlc(root: Path, pair: str) -> pd.DataFrame:
    d = pick_data_dir(root)
    parq = d / f"{pair}_1m.parquet"
    csvp = d / f"{pair}_1m.csv"
    if parq.exists():
        df = pd.read_parquet(parq)
        src = str(parq)
    elif csvp.exists():
        df = pd.read_csv(csvp)
        src = str(csvp)
    else:
        raise FileNotFoundError(f"OHLC not found for {pair}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=False)
    return df, src

def unpack_result(res):
    # Expected: tuple like (trades, metrics?, ...)
    trades = []
    extra = None
    if isinstance(res, tuple) and len(res) >= 1:
        trades = res[0] if isinstance(res[0], list) else []
        extra = res[1] if len(res) > 1 else None
        return trades, extra, {"raw_type":"tuple","raw_len":len(res)}
    if isinstance(res, dict):
        # fallback
        trades = res.get("trades") or res.get("trades_list") or []
        return trades if isinstance(trades,list) else [], res, {"raw_type":"dict"}
    # unknown
    return [], res, {"raw_type":str(type(res))}

def calc_metrics_from_trades(trades, start_eq=100.0):
    cnt = len(trades)
    gross = sum(getattr(t, "gross_pnl", 0.0) for t in trades)
    fees  = sum(getattr(t, "total_fee", 0.0) for t in trades)
    net   = sum(getattr(t, "net_pnl", 0.0) for t in trades)
    wins  = sum(1 for t in trades if getattr(t, "net_pnl", 0.0) > 0)
    win_rate = (wins / cnt) if cnt > 0 else 0.0

    # equity curve + max drawdown
    eq = start_eq
    peak = start_eq
    max_dd = 0.0
    for t in trades:
        eq += float(getattr(t, "net_pnl", 0.0))
        if eq > peak: peak = eq
        dd = (peak - eq)
        if dd > max_dd: max_dd = dd

    # holding bars average
    holds = []
    for t in trades:
        ei = getattr(t, "entry_bar_index", None)
        xi = getattr(t, "exit_bar_index", None)
        if isinstance(ei, int) and isinstance(xi, int) and xi >= ei:
            holds.append(xi - ei)
    avg_hold = (sum(holds)/len(holds)) if holds else 0.0

    # profit factor (gross wins / gross losses)
    win_g = sum(float(getattr(t, "gross_pnl", 0.0)) for t in trades if float(getattr(t, "gross_pnl", 0.0)) > 0)
    loss_g = sum(-float(getattr(t, "gross_pnl", 0.0)) for t in trades if float(getattr(t, "gross_pnl", 0.0)) < 0)
    pf = (win_g / loss_g) if loss_g > 0 else (float('inf') if win_g > 0 else 0.0)

    return {
        "trades": cnt,
        "gross_pnl": gross,
        "fees": fees,
        "net_pnl": net,
        "win_rate": win_rate,
        "max_dd": max_dd,
        "avg_hold_bars": avg_hold,
        "profit_factor": pf,
        "end_equity": start_eq + net,
    }

def save_sample(out_root: Path, pair: str, notional: float, tp: float, sl: float, trades):
    if not trades:
        return ""
    sample = []
    for t in trades[:15]:
        # serialize best-effort
        d = getattr(t, "__dict__", None)
        if isinstance(d, dict):
            sample.append(d)
        else:
            sample.append({"repr": repr(t)[:500]})
    p = out_root / f"trades_sample_{pair}_{int(notional)}_{tp}_{sl}.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"count": len(trades), "sample": sample}, f, ensure_ascii=False, indent=2)
    return str(p)

def main():
    root = Path(__file__).resolve().parent
    pairs = [p.strip() for p in os.getenv("FR_PAIRS","BTCUSDT,ETHUSDT,SOLUSDT").split(",") if p.strip()]
    max_bars = int(os.getenv("FR_MAX_BARS","0") or "0")

    notionals = [float(x) for x in os.getenv("FR_NOTIONALS","8,50").split(",")]
    tps = [float(x) for x in os.getenv("FR_TPS","0.003,0.004").split(",")]
    sls = [float(x) for x in os.getenv("FR_SLS","0.003,0.004").split(",")]
    start_eq = float(os.getenv("FR_START_EQ","100") or "100")

    out_root = root / "results_ga" / f"grid_v2_{time.strftime('%Y%m%d_%H%M%S')}"
    out_root.mkdir(parents=True, exist_ok=True)

    jsonl = out_root / "grid_v2_results.jsonl"
    csvp  = out_root / "grid_v2_summary.csv"

    print(f"[GRID_V2] out={out_root}")
    print(f"[GRID_V2] pairs={pairs} max_bars={max_bars}")
    print(f"[GRID_V2] notionals={notionals} tps={tps} sls={sls} start_eq={start_eq}")

    rows=[]
    with open(jsonl, "w", encoding="utf-8") as fj:
        for pair in pairs:
            ohlc, src = load_ohlc(root, pair)
            if max_bars>0 and len(ohlc)>max_bars:
                ohlc = ohlc.iloc[-max_bars:].copy()

            for notional in notionals:
                for tp in tps:
                    for sl in sls:
                        runner = BacktestRunner(
                            data_dir=pick_data_dir(root),
                            cache_dir=root/"cache",
                            results_dir=root/"results_ga",
                            notional_usdt=notional,
                            tp_pct=tp,
                            sl_pct=sl,
                            starting_equity=start_eq,
                        )

                        t0=time.perf_counter()
                        r1 = runner.run_pair_fast(pair, ohlc)
                        dt1=time.perf_counter()-t0
                        trades1, extra1, meta1 = unpack_result(r1)
                        m1 = calc_metrics_from_trades(trades1, start_eq)

                        t1=time.perf_counter()
                        r2 = runner.run_pair_fast(pair, ohlc)
                        dt2=time.perf_counter()-t1
                        trades2, extra2, meta2 = unpack_result(r2)
                        m2 = calc_metrics_from_trades(trades2, start_eq)

                        same = (m1["trades"]==m2["trades"] and abs(m1["net_pnl"]-m2["net_pnl"])<1e-12 and abs(m1["fees"]-m2["fees"])<1e-12)
                        sample_path = save_sample(out_root, pair, notional, tp, sl, trades1)

                        out = {
                            "pair": pair,
                            "src": src,
                            "bars": int(len(ohlc)),
                            "notional": notional,
                            "tp_pct": tp,
                            "sl_pct": sl,
                            "t1_sec": dt1,
                            "t2_sec": dt2,
                            "t2_over_t1": (dt2/dt1 if dt1>0 else None),
                            "same_metrics": same,
                            "raw_meta": meta1,
                            "sample_trades_file": sample_path,
                        }
                        out.update(m1)

                        fj.write(json.dumps(out, ensure_ascii=False) + "\n")
                        rows.append(out)

                        print(f"[GRID_V2] {pair} n={notional} tp={tp} sl={sl} t1={dt1:.3f}s t2={dt2:.3f}s trades={m1['trades']} net={m1['net_pnl']:.6f} fees={m1['fees']:.6f} dd={m1['max_dd']:.6f} same={same} sample={'YES' if sample_path else 'NO'}")

    cols=["pair","bars","notional","tp_pct","sl_pct","t1_sec","t2_sec","t2_over_t1","trades","net_pnl","fees","gross_pnl","win_rate","max_dd","profit_factor","avg_hold_bars","end_equity","same_metrics","sample_trades_file"]
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

    print(f"[GRID_V2] jsonl={jsonl}")
    print(f"[GRID_V2] csv={csvp}")
    print("[GRID_V2] done")

if __name__=="__main__":
    main()