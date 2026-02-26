import os, json, time, csv
from pathlib import Path
import pandas as pd

from backtest_runner import BacktestRunner

def pick_data_dir(root: Path) -> Path:
    p = root / "SCALPING_DATA_PARQUET"
    return p if p.exists() else (root / "SCALPING_DATA")

def load_ohlc(root: Path, pair: str) -> pd.DataFrame:
    data_dir = pick_data_dir(root)
    parq = data_dir / f"{pair}_1m.parquet"
    csvp = data_dir / f"{pair}_1m.csv"
    if parq.exists():
        df = pd.read_parquet(parq)
        src = str(parq)
    elif csvp.exists():
        df = pd.read_csv(csvp)
        src = str(csvp)
    else:
        raise FileNotFoundError(f"OHLC not found for {pair}: {parq} or {csvp}")
    if "timestamp" not in df.columns:
        raise ValueError(f"{pair}: OHLC missing 'timestamp' column (src={src})")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=False)
    return df

def normalize_result(res):
    if isinstance(res, dict):
        out = dict(res)
    else:
        out = getattr(res, "__dict__", {"result_repr": repr(res)})

    # Common key aliases (best-effort)
    if "num_trades" in out and "trades" not in out:
        out["trades"] = out["num_trades"]
    if "pnl" in out and "net_pnl" not in out:
        out["net_pnl"] = out["pnl"]

    return out

def try_extract_trades(out):
    # Try several likely keys
    for k in ("trades_list","trades","fills","events","orders","history"):
        v = out.get(k)
        if isinstance(v, list) and len(v) > 0:
            return k, v
    return None, None

def main():
    root = Path(__file__).resolve().parent
    pairs = [p.strip() for p in os.getenv("FR_PAIRS","BTCUSDT,ETHUSDT,SOLUSDT").split(",") if p.strip()]
    max_bars = int(os.getenv("FR_MAX_BARS","0") or "0")

    notionals = [float(x) for x in os.getenv("FR_NOTIONALS","8,50").split(",")]
    tps = [float(x) for x in os.getenv("FR_TPS","0.003,0.004").split(",")]
    sls = [float(x) for x in os.getenv("FR_SLS","0.003,0.004").split(",")]
    start_eq = float(os.getenv("FR_START_EQ","100") or "100")

    out_root = root / "results_ga" / f"grid_full_{time.strftime('%Y%m%d_%H%M%S')}"
    out_root.mkdir(parents=True, exist_ok=True)

    jsonl = out_root / "grid_results.jsonl"
    csvp  = out_root / "grid_summary.csv"

    data_dir = pick_data_dir(root)
    cache_dir = root / "cache"

    print(f"[GRID_FULL] out={out_root}")
    print(f"[GRID_FULL] pairs={pairs} max_bars={max_bars}")
    print(f"[GRID_FULL] notionals={notionals} tps={tps} sls={sls} start_eq={start_eq}")
    print(f"[GRID_FULL] data_dir={data_dir} cache_dir={cache_dir}")

    rows=[]
    with open(jsonl,"w",encoding="utf-8") as fj:
        for pair in pairs:
            ohlc = load_ohlc(root, pair)
            if max_bars>0 and len(ohlc)>max_bars:
                ohlc = ohlc.iloc[-max_bars:].copy()

            # One runner instance per pair (so _ind_cache benefits within pair grid)
            for notional in notionals:
                for tp in tps:
                    for sl in sls:
                        runner = BacktestRunner(
                            data_dir=data_dir,
                            cache_dir=cache_dir,
                            results_dir=root / "results_ga",
                            notional_usdt=notional,
                            tp_pct=tp,
                            sl_pct=sl,
                            starting_equity=start_eq,
                        )

                        # Run twice to verify determinism + cache
                        t0=time.perf_counter()
                        r1 = normalize_result(runner.run_pair_fast(pair, ohlc))
                        dt1=time.perf_counter()-t0

                        t1=time.perf_counter()
                        r2 = normalize_result(runner.run_pair_fast(pair, ohlc))
                        dt2=time.perf_counter()-t1

                        keys_to_check = ["trades","net_pnl","fees"]
                        same=True
                        for k in keys_to_check:
                            if k in r1 and k in r2 and r1[k]!=r2[k]:
                                same=False

                        # capture sample trades if any
                        tk, tv = try_extract_trades(r1)
                        sample_path = ""
                        if tv is not None:
                            sample = tv[:10]
                            sample_path = str(out_root / f"trades_sample_{pair}_{int(notional)}_{tp}_{sl}.json")
                            try:
                                with open(sample_path,"w",encoding="utf-8") as ft:
                                    json.dump({"key":tk,"count":len(tv),"sample":sample}, ft, ensure_ascii=False, indent=2)
                            except Exception:
                                sample_path = ""

                        out={
                            "pair":pair,"bars":int(len(ohlc)),
                            "notional":notional,"tp_pct":tp,"sl_pct":sl,
                            "t1_sec":dt1,"t2_sec":dt2,"t2_over_t1": (dt2/dt1 if dt1>0 else None),
                            "same_metrics":same,
                            "sample_trades_file": sample_path,
                            "keys_head": sorted(list(r1.keys()))[:30],
                        }
                        for k in ["trades","net_pnl","fees","gross_pnl","win_rate","max_dd","profit_factor"]:
                            if k in r1: out[k]=r1[k]

                        fj.write(json.dumps(out,ensure_ascii=False)+"\n")
                        rows.append(out)

                        print(f"[GRID_FULL] {pair} n={notional} tp={tp} sl={sl}  t1={dt1:.3f}s t2={dt2:.3f}s same={same} trades={out.get('trades')} net_pnl={out.get('net_pnl')} fees={out.get('fees')} sample={'YES' if sample_path else 'NO'}")

    cols=["pair","bars","notional","tp_pct","sl_pct","t1_sec","t2_sec","t2_over_t1","same_metrics","trades","net_pnl","fees","sample_trades_file"]
    cols=[c for c in cols if any(c in r for r in rows)]
    with open(csvp,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols)
        w.writeheader()
        for r in rows: w.writerow({c:r.get(c,"") for c in cols})

    print(f"[GRID_FULL] jsonl={jsonl}")
    print(f"[GRID_FULL] csv={csvp}")
    print("[GRID_FULL] done")

if __name__=="__main__":
    main()