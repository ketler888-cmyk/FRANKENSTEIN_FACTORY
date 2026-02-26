import os
import sys
from typing import Any, Dict, List

class ParamBridge:
    """
    Мост: DEAP individual (list[int]) -> params dict (для backtest_runner_v3)
    Использует BacktestRunnerV3.PARAM_GRID если есть, иначе пытается runner.param_grid/param_space.
    """
    def __init__(self):
        self.param_grid: Dict[str, List[Any]] = {}
        self._load_param_grid()

    def _load_param_grid(self) -> None:
        import importlib
        m = importlib.import_module("backtest_runner_v3")

        # 1) class-level PARAM_GRID
        if hasattr(m, "BacktestRunnerV3") and hasattr(m.BacktestRunnerV3, "PARAM_GRID"):
            self.param_grid = dict(m.BacktestRunnerV3.PARAM_GRID)
            return

        # 2) module-level PARAM_GRID
        if hasattr(m, "PARAM_GRID") and isinstance(m.PARAM_GRID, dict):
            self.param_grid = dict(m.PARAM_GRID)
            return

        # 3) fallback: try instantiate and read param_grid/param_space
        if hasattr(m, "BacktestRunnerV3"):
            try:
                r = m.BacktestRunnerV3(pairs=["BTCUSDT"], starting_equity=500.0, train_ratio=0.7, output="results\\tmp.json")
                if hasattr(r, "param_grid") and isinstance(r.param_grid, dict):
                    self.param_grid = dict(r.param_grid)
                    return
                if hasattr(r, "param_space") and isinstance(r.param_space, dict):
                    self.param_grid = dict(r.param_space)
                    return
            except Exception:
                pass

        raise RuntimeError("ParamBridge: cannot find PARAM_GRID/param_grid/param_space in backtest_runner_v3")

    def names(self) -> List[str]:
        return list(self.param_grid.keys())

    def individual_to_params(self, individual: List[int]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        keys = self.names()
        for i, k in enumerate(keys):
            values = self.param_grid[k]
            if not values:
                continue
            gene = int(individual[i]) if i < len(individual) else 0
            idx = gene % len(values)
            params[k] = values[idx]
        return params

    def params_to_individual(self, params: Dict[str, Any]) -> List[int]:
        ind: List[int] = []
        for k, values in self.param_grid.items():
            v = params.get(k, None)
            if v in values:
                ind.append(values.index(v))
            else:
                ind.append(0)
        return ind
