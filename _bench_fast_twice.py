import os, time, traceback
from pathlib import Path

import pandas as pd

def load_ohlc(pair: str, root: Path) -> pd.DataFrame:
    # Prefer parquet if present
    p_parq = root / "SCALPING_DATA_PARQUET" / f"{pair}_1m.parquet"
    p_csv  = root / "SCALPING_DATA" / f"{pair}_1m.csv"

    if p_parq.exists():
        df = pd.read_parquet(p_parq)
        src = str(p_parq)
    elif p_csv.exists():
        df = pd.read_csv(p_csv)
        src = str(p_csv)
    else:
        raise FileNotFoundError(f"No OHLC for {pair}. Expected: {p_parq} OR {p_csv}")

    # normalize expected cols
    need = ["timestamp","open","high","low","close","volume"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"OHLC missing cols={missing}. Have={list(df.columns)[:30]}")

    return df[need].copy(), src

def main():
    root = Path(__file__).resolve().parent
    pair = os.getenv("FR_PAIR","BTCUSDT").strip()
    max_bars = int(os.getenv("FR_MAX_BARS","0") or "0")
    fr_fast = os.getenv("FR_FAST","0")

    print("[BENCH] start")
    print("[BENCH] FR_FAST=", fr_fast, "PAIR=", pair, "MAX_BARS=", max_bars)
    print("[BENCH] root=", str(root))

    try:
        ohlc, src = load_ohlc(pair, root)
        if max_bars > 0 and len(ohlc) > max_bars:
            # keep tail to preserve most recent segment
            ohlc = ohlc.iloc[-max_bars:].reset_index(drop=True)

        print("[BENCH] ohlc rows=", len(ohlc), "src=", src)

        import backtest_runner
        from backtest_runner import BacktestRunner

        # Build runner with same defaults as your profiler script uses
        runner = BacktestRunner(
            data_dir=root / "SCALPING_DATA",
            cache_dir=root / "cache",
            results_dir=root / "results_ga",
            notional_usdt=50,
            tp_pct=0.004,
            sl_pct=0.003,
            starting_equity=100,
        )

        def one(tag: str):
            t0 = time.perf_counter()
            trades, metrics, eq, rep = runner.run_pair(pair, ohlc)
            t1 = time.perf_counter()
            print(f"[BENCH] {tag} run_pair: {t1-t0:.3f}s  trades={len(trades)}  net_pnl={getattr(metrics,'net_pnl',None)} fees={getattr(metrics,'fees',None)}")
            return (t1 - t0)

        tA = one("FAST#1")
        tB = one("FAST#2")
        sp = (tA / tB) if tB > 0 else 0.0
        print(f"[BENCH] speedup x{sp:.2f} (2nd faster => cache works)")
        print("[BENCH] done")
        return 0

    except Exception as e:
        print("[BENCH] ERROR:", repr(e))
        traceback.print_exc()
        return 4

if __name__ == "__main__":
    raise SystemExit(main())