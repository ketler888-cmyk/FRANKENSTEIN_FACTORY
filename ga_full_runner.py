import os
import pandas as pd
import zipfile
import datetime
from strategy.ga_core import run_genetic_optimizer  # Замени на путь до своей функции, если другой

PAIR = "BTCUSDT"
DATA_PATH = os.path.expanduser("~/Desktop/Франкинштэйн/SCALPING_DATA_PARQUET/BTCUSDT_1m.parquet")
OUT_DIR = os.path.expanduser(f"~/Desktop/GA_RESULTS_{PAIR}_{datetime.datetime.now():%Y%m%d_%H%M%S}")

GA_CONFIG = {
    "generations": 50,
    "population": 60,
    "mutation_rate": 0.3,
    "crossover_rate": 0.6,
    "search_space": {
        "W_FAST": [3, 5, 8, 10],
        "W_SLOW": [10, 14, 20, 30],
        "RET_FAST": [0.0003, 0.0006, 0.001, 0.0015],
        "RANGE_FAST": [0.0005, 0.001, 0.0015, 0.002],
        "VOL_MULT": [1.0, 1.25, 1.5, 2.0],
        "COOLDOWN": [2, 4, 6],
        "TP": [0.002, 0.0025, 0.003, 0.004],
        "SL": [0.001, 0.0015, 0.002],
        "MAX_HOLD": [6, 8, 12],
    }
}

os.makedirs(OUT_DIR, exist_ok=True)
print(f"[RUN] GA full optimize -> {OUT_DIR}")

summary, trades_df, logs = run_genetic_optimizer(DATA_PATH, GA_CONFIG)

summary_path = os.path.join(OUT_DIR, "summary.json")
trades_path = os.path.join(OUT_DIR, "trades.csv")
log_path = os.path.join(OUT_DIR, "log.txt")

summary.to_json(summary_path, indent=2)
trades_df.to_csv(trades_path, index=False)
with open(log_path, "w", encoding="utf-8") as f:
    for line in logs:
        f.write(line + "\n")

zip_path = OUT_DIR + ".zip"
with zipfile.ZipFile(zip_path, 'w') as zipf:
    for file in [summary_path, trades_path, log_path]:
        zipf.write(file, arcname=os.path.basename(file))

print(f"[OK] GA finished. ZIP ready -> {zip_path}")