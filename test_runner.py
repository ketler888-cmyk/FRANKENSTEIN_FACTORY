import sys
sys.path.insert(0, ".")
from ga_adapters.runner_bridge import RunnerBridge

rb = RunnerBridge(starting_equity=500.0, train_ratio=0.7, timeout_sec=60)
metrics = rb.eval_once("BTCUSDT", {"_probe": True})

print("metrics keys:", sorted(list(metrics.keys())))
print("fitness:", metrics.get("fitness"))
print("profit:", metrics.get("profit"))
print("error_code:", metrics.get("error_code"))