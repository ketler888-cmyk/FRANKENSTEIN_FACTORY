from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# --- Indicator backend selection ---
TA_LIB_AVAILABLE = False
TA_BACKEND = "none"
try:
    import talib  # TA-Lib Python wrapper
    TA_LIB_AVAILABLE = True
    TA_BACKEND = "talib"
except Exception:
    talib = None

# Optional fallback: pure-python indicators -> pip install ta
TA_FALLBACK_AVAILABLE = False
try:
    from ta.volatility import AverageTrueRange
    from ta.trend import CCIIndicator
    TA_FALLBACK_AVAILABLE = True
    if TA_BACKEND == "none":
        TA_BACKEND = "ta"
except Exception:
    AverageTrueRange = None
    CCIIndicator = None

def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _hash_key(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

@dataclass
class IndicatorCache:
    cache_dir: Path

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        _safe_mkdir(self.cache_dir)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.parquet"

    def get_or_compute_atr_cci(self, df: pd.DataFrame, atr_len: int, cci_len: int) -> pd.DataFrame:
        """Return df with columns atr, cci. Cached by (len(df), last_ts, params, backend)."""
        if "timestamp" in df.columns:
            last_ts = str(df["timestamp"].iloc[-1])
        else:
            last_ts = "na"

        key = _hash_key({
            "n": int(len(df)),
            "last_ts": last_ts,
            "atr_len": int(atr_len),
            "cci_len": int(cci_len),
            "backend": TA_BACKEND
        })
        out_path = self._path(key)

        if out_path.exists():
            try:
                return pd.read_parquet(out_path)
            except Exception:
                pass  # corrupted cache -> recompute

        out = df.copy()

        # Ensure float arrays
        close = out["close"].astype(float).to_numpy()
        high  = out["high"].astype(float).to_numpy()
        low   = out["low"].astype(float).to_numpy()

        if TA_LIB_AVAILABLE and talib is not None:
            out["atr"] = talib.ATR(high, low, close, timeperiod=int(atr_len))
            out["cci"] = talib.CCI(high, low, close, timeperiod=int(cci_len))
        elif TA_FALLBACK_AVAILABLE and AverageTrueRange is not None and CCIIndicator is not None:
            out["atr"] = AverageTrueRange(high=out["high"], low=out["low"], close=out["close"], window=int(atr_len)).average_true_range()
            out["cci"] = CCIIndicator(high=out["high"], low=out["low"], close=out["close"], window=int(cci_len)).cci()
        else:
            raise RuntimeError("No indicator backend available. Install TA-Lib or 'ta'.")

        try:
            out.to_parquet(out_path, index=False)
        except Exception:
            pass  # cache is optional

        return out

def default_cache_dir() -> Path:
    return Path(__file__).resolve().parent / "cache" / "indicators"
