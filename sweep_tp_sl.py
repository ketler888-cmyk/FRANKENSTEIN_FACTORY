import os, json, time
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
    if parq.exists(): df = pd.read_parquet(parq)
    elif csvp.exists(): df = pd.read_csv(csvp)
    else: raise FileNotFoundError(f"OHLC not found for {pair}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=False)
    return df

def unpack_trades(res):
    if isinstance(res, tuple) and len(res) >= 1 and isinstance(res[0], list):
        return res[0]
    if isinstance(res, dict):
        v = res.get("trades") or res.get("trades_list") or []
        return v if isinstance(v, list) else []
    return []

def metrics(trades, start_eq=100.0):
    cnt = len(trades)
    gross = sum(getattr(t, "gross_pnl", 0.0) for t in trades)
    fees  = sum(getattr(t, "total_fee", 0.0) for t in trades)
    net   = sum(getattr(t, "net_pnl", 0.0) for t in trades)
    eq = start_eq; peak = start_eq; max_dd = 0.0
    for t in trades:
        eq += float(getattr(t, "net_pnl", 0.0))
        if eq > peak: peak = eq
        dd = peak - eq
        if dd > max_dd: max_dd = dd
    return cnt, gross, fees, net, max_dd, eq

def main():
    root = Path(__file__).resolve().parent
    pair = os.getenv("FR_PAIR","SOLUSDT")
    notional = float(os.getenv("FR_NOTIONAL","50") or "50")
    start_eq = float(os.getenv("FR_START_EQ","100") or "100")
    max_bars = int(os.getenv("FR_MAX_BARS","0") or "0")

    ohlc = load_ohlc(root, pair)
    if max_bars>0 and len(ohlc)>max_bars:
        ohlc = ohlc.iloc[-max_bars:].copy()

    # deliberately wide TP/SL
    grid = [
        (0.0020, 0.0020),
        (0.0040, 0.0030),
        (0.0080, 0.0040),
        (0.0120, 0.0060),
        (0.0200, 0.0100),
    ]

    out_dir = root/"results_ga"/f"sweep_tp_sl_{time.strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir/"sweep_results.jsonl"

    print(f"[SWEEP] pair={pair} bars={len(ohlc)} notional={notional} out={out_dir}")
    with open(outp,"w",encoding="utf-8") as f:
        for tp, sl in grid:
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
            res = runner.run_pair_fast(pair, ohlc)
            dt=time.perf_counter()-t0
            trades = unpack_trades(res)
            cnt,gross,fees,net,dd,eq = metrics(trades, start_eq)
            row={"tp":tp,"sl":sl,"sec":dt,"trades":cnt,"gross":gross,"fees":fees,"net":net,"dd":dd,"end_eq":eq}
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
            print(f"[SWEEP] tp={tp:.4f} sl={sl:.4f} sec={dt:.3f} trades={cnt} net={net:.6f} fees={fees:.6f} dd={dd:.6f}")
    print(f"[SWEEP] saved={outp}")

if __name__=="__main__":
    main()