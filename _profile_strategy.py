import os, time, traceback

PAIR = os.environ.get("FR_PAIR", "BTCUSDT")
MAX_BARS = int(os.environ.get("FR_MAX_BARS", "0"))  # 0 => NO TRIM (keep aligned)

print("[PROFILE_STRAT] start")
print("[PROFILE_STRAT] pair=", PAIR, "max_bars=", MAX_BARS)

t0 = time.perf_counter()
try:
    from backtest_runner import BacktestRunner
    from data_loader import ScalpingDataLoader
except Exception as e:
    print("[PROFILE_STRAT] IMPORT ERROR:", repr(e))
    traceback.print_exc()
    raise SystemExit(2)

t1 = time.perf_counter()
print(f"[PROFILE_STRAT] imports: {t1 - t0:.3f}s")

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "SCALPING_DATA")
CACHE_DIR = os.path.join(ROOT, "cache", "indicators")
RESULTS_DIR = os.path.join(ROOT, "results")

runner = BacktestRunner(
    data_dir=DATA_DIR,
    cache_dir=CACHE_DIR,
    results_dir=RESULTS_DIR,
    notional_usdt=50.0,
    tp_pct=0.004,
    sl_pct=0.003,
    fee_taker=0.00055,
    fee_maker=0.0002,
    starting_equity=100.0,
    use_taker=True,
)

t2 = time.perf_counter()
loader = ScalpingDataLoader(DATA_DIR)
data = loader.load_all([PAIR])
t3 = time.perf_counter()
print(f"[PROFILE_STRAT] load_all: {t3 - t2:.3f}s keys={list(data.keys())}")

ohlc = data[PAIR]
print("[PROFILE_STRAT] ohlc rows=", len(ohlc), "cols=", list(ohlc.columns))

# NO TRIM to keep alignment with cached indicators
if MAX_BARS and len(ohlc) > MAX_BARS:
    # if you ever set MAX_BARS >0, keep full length alignment by trimming IND too (not done here)
    ohlc = ohlc.iloc[:MAX_BARS].copy()
    print("[PROFILE_STRAT] ohlc trimmed rows=", len(ohlc))

t4 = time.perf_counter()
try:
    trades, metrics, eq, pair_report = runner.run_pair(PAIR, ohlc)
except Exception as e:
    print("[PROFILE_STRAT] RUN_PAIR ERROR:", repr(e))
    traceback.print_exc()
    raise SystemExit(4)
t5 = time.perf_counter()

print(f"[PROFILE_STRAT] run_pair: {t5 - t4:.3f}s")
print("[PROFILE_STRAT] trades=", len(trades))
print("[PROFILE_STRAT] net_pnl=", getattr(metrics, "net_pnl", None),
      "fees=", getattr(metrics, "fees", None),
      "dd=", getattr(metrics, "max_drawdown", None))
print("[PROFILE_STRAT] done")
