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

def main():
    root = Path(__file__).resolve().parent
    pair = os.getenv("FR_PAIR","BTCUSDT")
    max_bars = int(os.getenv("FR_MAX_BARS","0") or "0")

    ohlc, src = load_ohlc(root, pair)
    if max_bars>0 and len(ohlc)>max_bars:
        ohlc = ohlc.iloc[-max_bars:].copy()

    runner = BacktestRunner(
        data_dir=pick_data_dir(root),
        cache_dir=root/"cache",
        results_dir=root/"results_ga",
        notional_usdt=float(os.getenv("FR_NOTIONAL","50") or "50"),
        tp_pct=float(os.getenv("FR_TP_PCT","0.004") or "0.004"),
        sl_pct=float(os.getenv("FR_SL_PCT","0.003") or "0.003"),
        starting_equity=float(os.getenv("FR_START_EQ","100") or "100"),
    )

    print("[DIAG] pair=", pair)
    print("[DIAG] src =", src)
    print("[DIAG] bars=", len(ohlc))

    t0=time.perf_counter()
    res = runner.run_pair_fast(pair, ohlc)
    dt=time.perf_counter()-t0

    print("[DIAG] seconds=", round(dt,4))
    print("[DIAG] type=", type(res))

    if isinstance(res, dict):
        keys = sorted(list(res.keys()))
        print("[DIAG] dict_keys=", keys)
        # print common fields if exist
        for k in ("trades","num_trades","net_pnl","pnl","fees","gross_pnl","win_rate","max_dd","profit_factor"):
            if k in res:
                print(f"[DIAG] {k}=", res[k])

        # try dump sample list-like fields
        for k in ("trades_list","trades","fills","events","orders","history"):
            v = res.get(k)
            if isinstance(v, list) and len(v)>0:
                outp = root/"results_ga"/f"diag_trades_sample_{pair}_{int(time.time())}.json"
                with open(outp,"w",encoding="utf-8") as f:
                    json.dump({"key":k,"count":len(v),"sample":v[:15]}, f, ensure_ascii=False, indent=2)
                print("[DIAG] trades_sample_saved=", outp)
                break
    else:
        # object-like
        d = getattr(res,"__dict__",None)
        if isinstance(d, dict):
            print("[DIAG] obj_dict_keys=", sorted(list(d.keys())))
        print("[DIAG] repr=", repr(res)[:600])

if __name__=="__main__":
    main()