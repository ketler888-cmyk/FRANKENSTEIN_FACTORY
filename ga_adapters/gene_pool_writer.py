import os
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path


class GenePoolWriter:
    """
    Пишем best candidates в gene_pool\best_<pair>.jsonl и gene_pool\best_overall.jsonl
    """

    def __init__(self, pool_dir: Optional[str] = None):
        self.root = Path(pool_dir) if pool_dir else Path(__file__).resolve().parent.parent / "gene_pool"
        self.root.mkdir(parents=True, exist_ok=True)

    def push(self, *, pair, params, metrics, fitness, generation, run_id):
        pair_safe = pair.replace("/", "_")
        pf = self.root / f"best_{pair_safe}.jsonl"
        pf.parent.mkdir(parents=True, exist_ok=True)

        with open(pf, "a", encoding="utf-8") as f:
            json.dump({
                "pair": pair,
                "params": params,
                "metrics": metrics,
                "fitness": fitness,
                "generation": generation,
                "run_id": run_id
            }, f)
            f.write("\n")