# -*- coding: utf-8 -*-
"""
indicator_cache.py - Unified indicator cache builder for FRANKENSTEIN_FACTORY.

Goal:
- Build per-pair indicator caches usable by:
  - backtest_runner_v3.py (walk-forward)
  - backtest_runner.py (legacy)
- Cache location (local only, ignored by git):
    cache/indicators/<PAIR>_indicators.parquet
    cache/indicators/<PAIR>_meta.json

Indicators produced (superset):
- rsi_14
- ema_9, ema_21, ema_50, ema_200
- bb_upper, bb_middle, bb_lower
- atr_14
- macd, macdsignal, macdhist
Plus aliases for compatibility (bb_mid == bb_middle).

Uses TA-Lib if available (fast); otherwise uses ta (pure python).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

from data_loader import ScalpingDataLoader

def _norm_pair(x: str) -> str:
    try:
        s = str(x).strip().upper()
        return s.replace("/", "").replace("-", "").replace("_", "")
    except Exception:
        return str(x)

def _pick_default_data_dir(root: Path) -> Path:
    for d in ("SCALPING_DATA_PARQUET", "SCALPING_DATA_RAW", "SCALPING_DATA"):
        p = root / d
        if p.exists():
            return p
    return root / "SCALPING_DATA"

def _pick_cache_dir(root: Path) -> Path:
    return root / "cache" / "indicators"

def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # expects timestamp, open, high, low, close, volume
    close = df["close"].astype("float64")
    high  = df["high"].astype("float64")
    low   = df["low"].astype("float64")

    out = pd.DataFrame({"timestamp": df["timestamp"].copy()})

    # Prefer TA-Lib if present
    use_talib = False
    try:
        import talib  # type: ignore
        use_talib = True
    except Exception:
        use_talib = False

    if use_talib:
        import talib  # type: ignore
        out["rsi_14"]  = talib.RSI(close.values, timeperiod=14)
        out["ema_9"]   = talib.EMA(close.values, timeperiod=9)
        out["ema_21"]  = talib.EMA(close.values, timeperiod=21)
        out["ema_50"]  = talib.EMA(close.values, timeperiod=50)
        out["ema_200"] = talib.EMA(close.values, timeperiod=200)

        up, mid, lo = talib.BBANDS(close.values, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        out["bb_upper"]  = up
        out["bb_middle"] = mid
        out["bb_lower"]  = lo
        out["bb_mid"]    = out["bb_middle"]

        out["atr_14"] = talib.ATR(high.values, low.values, close.values, timeperiod=14)

        macd, macdsig, macdh = talib.MACD(close.values, fastperiod=12, slowperiod=26, signalperiod=9)
        out["macd"]       = macd
        out["macdsignal"] = macdsig
        out["macdhist"]   = macdh

        return out

    # Fallback: ta (pure python)
    try:
        import ta  # type: ignore
        from ta.momentum import RSIIndicator
        from ta.trend import EMAIndicator, MACD
        from ta.volatility import BollingerBands, AverageTrueRange
    except Exception as e:
        raise RuntimeError("Neither TA-Lib nor ta is available. Install dependencies in .venv.") from e

    out["rsi_14"]  = RSIIndicator(close=close, window=14).rsi()
    out["ema_9"]   = EMAIndicator(close=close, window=9).ema_indicator()
    out["ema_21"]  = EMAIndicator(close=close, window=21).ema_indicator()
    out["ema_50"]  = EMAIndicator(close=close, window=50).ema_indicator()
    out["ema_200"] = EMAIndicator(close=close, window=200).ema_indicator()

    bb = BollingerBands(close=close, window=20, window_dev=2)
    out["bb_upper"]  = bb.bollinger_hband()
    out["bb_middle"] = bb.bollinger_mavg()
    out["bb_lower"]  = bb.bollinger_lband()
    out["bb_mid"]    = out["bb_middle"]

    out["atr_14"] = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()

    m = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    out["macd"]       = m.macd()
    out["macdsignal"] = m.macd_signal()
    out["macdhist"]   = m.macd_diff()

    return out

def build_pair_cache(pair: str, data_dir: Path, cache_dir: Path, *, force: bool, max_bars: int = 0) -> Dict[str, Any]:
    pair = _norm_pair(pair)
    cache_dir.mkdir(parents=True, exist_ok=True)

    out_parq = cache_dir / f"{pair}_indicators.parquet"
    out_meta = cache_dir / f"{pair}_meta.json"

    if (not force) and out_parq.exists() and out_meta.exists():
        return {"pair": pair, "status": "skip", "indicators": str(out_parq), "meta": str(out_meta)}

    loader = ScalpingDataLoader(data_dir)
    data = loader.load_all([pair])
    if pair not in data:
        raise FileNotFoundError(f"OHLC not found for {pair} in {data_dir}")
    df = data[pair].copy()

    if max_bars and len(df) > int(max_bars):
        df = df.tail(int(max_bars)).reset_index(drop=True)

    t0 = time.time()
    ind = _compute_indicators(df)

    # Keep strict alignment
    if len(ind) != len(df):
        raise RuntimeError(f"Indicator length mismatch: ohlc={len(df)} ind={len(ind)}")

    # Persist
    ind.to_parquet(out_parq, index=False)
    meta = {
        "pair": pair,
        "format": "parquet",
        "columns": [c for c in ind.columns if c != "timestamp"],
        "rows": int(len(ind)),
        "data_dir": str(data_dir),
        "cache_dir": str(cache_dir),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "build_seconds": round(time.time() - t0, 3),
    }
    out_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"pair": pair, "status": "built", "indicators": str(out_parq), "meta": str(out_meta), "rows": meta["rows"]}

def _pairs_from_factory_config(root: Path) -> List[str]:
    cfg = root / "configs" / "factory_config.json"
    if not cfg.exists():
        return []
    try:
        j = json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        j = json.loads(cfg.read_text(encoding="utf-8-sig"))
    pairs = j.get("pairs") if isinstance(j, dict) else None
    if not isinstance(pairs, list):
        return []
    out = []
    for x in pairs:
        sx = str(x).strip()
        if sx:
            out.append(_norm_pair(sx))
    # unique stable
    return sorted(list(dict.fromkeys(out)))

def main() -> int:
    root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", type=str, default=str(_pick_default_data_dir(root)))
    ap.add_argument("--cache_dir", type=str, default=str(_pick_cache_dir(root)))
    ap.add_argument("--pair", type=str, default="")
    ap.add_argument("--pairs", type=str, default="")  # comma-separated
    ap.add_argument("--from_factory_config", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max_bars", type=int, default=0)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    cache_dir = Path(args.cache_dir)

    pairs: List[str] = []
    if args.from_factory_config:
        pairs = _pairs_from_factory_config(root)
    if args.pair:
        pairs.append(_norm_pair(args.pair))
    if args.pairs:
        for p in str(args.pairs).split(","):
            p = p.strip()
            if p:
                pairs.append(_norm_pair(p))

    pairs = sorted(list(dict.fromkeys([p for p in pairs if p])))

    if not pairs:
        print(json.dumps({"ok": False, "error": "No pairs provided. Use --pair or --pairs or --from_factory_config"}, ensure_ascii=False, indent=2))
        return 2

    rep: Dict[str, Any] = {"ok": True, "data_dir": str(data_dir), "cache_dir": str(cache_dir), "pairs": {}, "ts": time.time()}
    bad = 0
    for p in pairs:
        try:
            rep["pairs"][p] = build_pair_cache(p, data_dir, cache_dir, force=bool(args.force), max_bars=int(args.max_bars))
        except Exception as e:
            bad += 1
            rep["pairs"][p] = {"pair": p, "status": "error", "error": repr(e)}

    rep["ok"] = (bad == 0)
    print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    return 0 if bad == 0 else 3

if __name__ == "__main__":
    raise SystemExit(main())