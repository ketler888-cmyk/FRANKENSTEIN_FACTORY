import sys
sys.path.insert(0, ".")
from ga_adapters.runner_bridge import RunnerBridge
rb = RunnerBridge(starting_equity=500.0, train_ratio=0.7, timeout_sec=1800)
m = rb.eval_once("BTCUSDT", {"_probe": True})
print("profit:", m.get("profit"))
print("drawdown:", m.get("drawdown"))
print("fitness:", m.get("fitness"))
print("error_code:", m.get("error_code"))
