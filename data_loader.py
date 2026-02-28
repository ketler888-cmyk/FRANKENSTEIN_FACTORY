# -*- coding: utf-8 -*-
\""\""
data_loader.py - Production loader for 1m OHLCV scalping data.

STRICT RULES:
- Load FULL datasets (no synthetic).
- 1m timeframe. Gap is any delta > 60 seconds.
- Supports CSV and Parquet. If both exist for a pair, Parquet is preferred.
\""\""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("scalping_data_loader")

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
TIMEFRAME_SECONDS = 60
GAP_THRESHOLD_SECONDS = 60  # strictly >60 sec is a gap


def normalize_pair(pair: Any) -> str:
    if pair is None:
        return ""
    p = str(pair).strip().upper()
    p = p.replace("/", "").replace("-", "").replace("_", "")
    if p.startswith("XBT"):
        p = "BTC" + p[3:]
    return p


def _fr_colmap(df: pd.DataFrame) -> pd.DataFrame:
    # Best-effort column normalization: maps common aliases to required columns.
    try:
        cols = list(df.columns)
    except Exception:
        return df

    norm = {c: str(c).strip() for c in cols}
    low = {c: norm[c].lower() for c in cols}

    alias = {
        "timestamp": ["timestamp", "time", "datetime", "date", "open_time", "opentime", "open time", "t", "ts"],
        "open":      ["open", "o", "op", "price_open", "openprice"],
        "high":      ["high", "h", "hi", "price_high", "highprice"],
        "low":       ["low", "l", "lo", "price_low", "lowprice"],
        "close":     ["close", "c", "cl", "price_close", "closeprice", "last"],
        "volume":    ["volume", "vol", "v", "qty", "quantity", "base_volume", "basevol", "amount"],
    }

    rename = {}
    taken = set()

    for target, al in alias.items():
        found = None
        for a in al:
            for c in cols:
                if c in taken:
                    continue
                if low[c] == a:
                    found = c
                    break
            if found is not None:
                break
        if found is not None and found != target:
            rename[found] = target
            taken.add(found)

    if rename:
        df = df.rename(columns=rename)

    return df


@dataclass(frozen=True)
class GapExample:
    gap_start: str
    gap_end: str
    gap_seconds: int
    missing_bars: int


class ScalpingDataLoader:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        self.data: Dict[str, pd.DataFrame] = {}
        self.report: Dict[str, Any] = {}

    def discover_files(self, pairs: Optional[List[str]] = None) -> List[Path]:
        csvs = sorted(self.data_dir.glob("*_1m.csv"))
        parqs = sorted(self.data_dir.glob("*_1m.parquet"))
        all_files = sorted(list(set(csvs + parqs)), key=lambda p: p.name)

        if not all_files:
            raise FileNotFoundError(
                f"No files matching '*_1m.csv' or '*_1m.parquet' found in {self.data_dir}"
            )

        if not pairs:
            # Prefer parquet duplicates: if both exist, keep parquet
            by_pair: Dict[str, Path] = {}
            for fp in all_files:
                pair = fp.stem.replace("_1m", "")
                if fp.suffix.lower() == ".parquet":
                    by_pair[pair] = fp
                elif pair not in by_pair:
                    by_pair[pair] = fp
            return [by_pair[k] for k in sorted(by_pair.keys())]

        out: List[Path] = []
        for p in pairs:
            pp = str(p).replace("_1m", "")
            pq = self.data_dir / f"{pp}_1m.parquet"
            cs = self.data_dir / f"{pp}_1m.csv"
            if pq.exists():
                out.append(pq)
            elif cs.exists():
                out.append(cs)
            else:
                logger.warning(f"No file found for pair: {pp} (expected: {pq} OR {cs})")
        if not out:
            raise FileNotFoundError(f"No files found for specified pairs: {pairs}")
        return out

    @staticmethod
    def _parse_timestamp_series(ts: pd.Series) -> pd.Series:
        if pd.api.types.is_datetime64_any_dtype(ts):
            return pd.to_datetime(ts, utc=True, errors="coerce")

        if pd.api.types.is_numeric_dtype(ts):
            v = ts.astype("float64")
            finite = v[np.isfinite(v)]
            if len(finite) == 0:
                return pd.to_datetime(pd.Series([pd.NaT] * len(ts)), utc=True)
            median = float(np.median(finite))
            unit = "ms" if median > 1e12 else "s"
            return pd.to_datetime(ts, unit=unit, utc=True, errors="coerce")

        return pd.to_datetime(ts, utc=True, errors="coerce")

    @staticmethod
    def _enforce_required_columns(df: pd.DataFrame, file_name: str) -> pd.DataFrame:
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{file_name}: missing required columns: {missing}")
        return df[REQUIRED_COLUMNS].copy()

    @staticmethod
    def _coerce_numeric(df: pd.DataFrame, file_name: str) -> pd.DataFrame:
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ["open", "high", "low", "close", "volume"]:
            nan_count = int(df[col].isna().sum())
            inf_count = int(np.isinf(df[col]).sum())
            if nan_count > 0 or inf_count > 0:
                logger.warning(f"{file_name}: {col} has NaN={nan_count}, Inf={inf_count}")
        return df

    def _load_csv(self, file_path: Path) -> pd.DataFrame:
        file_name = file_path.name
        df = pd.read_csv(file_path, engine="c")
        df = _fr_colmap(df)
        df = self._enforce_required_columns(df, file_name)
        df["timestamp"] = self._parse_timestamp_series(df["timestamp"])
        nat_count = int(df["timestamp"].isna().sum())
        if nat_count > 0:
            raise ValueError(f"{file_name}: timestamp parse failed for {nat_count} rows (NaT).")
        df = df.sort_values("timestamp", ascending=True).reset_index(drop=True)
        if not df["timestamp"].is_unique:
            dup = int(df["timestamp"].duplicated().sum())
            raise AssertionError(f"{file_name}: Found {dup} duplicate timestamps (clean base expected).")
        df = self._coerce_numeric(df, file_name)
        return df

    def _load_parquet(self, file_path: Path) -> pd.DataFrame:
        file_name = file_path.name
        df = pd.read_parquet(file_path)
        df = _fr_colmap(df)
        df = self._enforce_required_columns(df, file_name)
        df["timestamp"] = self._parse_timestamp_series(df["timestamp"])
        nat_count = int(df["timestamp"].isna().sum())
        if nat_count > 0:
            raise ValueError(f"{file_name}: timestamp parse failed for {nat_count} rows (NaT).")
        df = df.sort_values("timestamp", ascending=True).reset_index(drop=True)
        if not df["timestamp"].is_unique:
            dup = int(df["timestamp"].duplicated().sum())
            raise AssertionError(f"{file_name}: Found {dup} duplicate timestamps (clean base expected).")
        df = self._coerce_numeric(df, file_name)
        return df

    def load_any(self, file_path: Path) -> pd.DataFrame:
        if file_path.suffix.lower() == ".parquet":
            return self._load_parquet(file_path)
        return self._load_csv(file_path)

    @staticmethod
    def analyze_gaps(df: pd.DataFrame) -> Tuple[int, List[GapExample]]:
        if len(df) < 2:
            return 0, []
        ts = df["timestamp"]
        deltas = ts.diff().iloc[1:]
        threshold = pd.Timedelta(seconds=GAP_THRESHOLD_SECONDS)
        mask = deltas > threshold
        gap_count = int(mask.sum())

        examples: List[GapExample] = []
        if gap_count > 0:
            idxs = list(deltas[mask].index)
            for i in idxs[:5]:
                gap_start = ts.iloc[i - 1]
                gap_end = ts.iloc[i]
                gap_sec = int((gap_end - gap_start).total_seconds())
                missing = max(int(round(gap_sec / TIMEFRAME_SECONDS)) - 1, 0)
                examples.append(GapExample(
                    gap_start=gap_start.isoformat(),
                    gap_end=gap_end.isoformat(),
                    gap_seconds=gap_sec,
                    missing_bars=missing,
                ))
        return gap_count, examples

    def generate_pair_report(self, df: pd.DataFrame, pair: str) -> Dict[str, Any]:
        rows = int(len(df))
        start = df["timestamp"].min().isoformat() if rows else None
        end = df["timestamp"].max().isoformat() if rows else None

        gap_count, gap_examples = self.analyze_gaps(df)
        nan_counts = {c: int(df[c].isna().sum()) for c in ["open", "high", "low", "close", "volume"]}
        inf_counts = {c: int(np.isinf(df[c]).sum()) for c in ["open", "high", "low", "close", "volume"]}

        return {
            "pair": pair,
            "rows": rows,
            "date_range": {"start": start, "end": end},
            "gap_count": gap_count,
            "gap_examples": [e.__dict__ for e in gap_examples],
            "nan_counts": nan_counts,
            "inf_counts": inf_counts,
            "columns": list(df.columns),
        }

    def load_all(self, pairs: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        files = self.discover_files(pairs)
        logger.info(f"Found {len(files)} file(s) to load in: {self.data_dir}")

        for fp in files:
            pair = fp.stem.replace("_1m", "")
            try:
                df = self.load_any(fp)
                self.data[pair] = df
                self.report[pair] = self.generate_pair_report(df, pair)
                logger.info(f"Loaded {pair}: {len(df)} rows ({fp.suffix})")
            except Exception as e:
                logger.error(f"Failed to load {fp.name}: {e}")
                self.report[pair] = {"pair": pair, "rows": 0, "error": str(e)}

        attempted = len(files)
        loaded = len(self.data)
        total_rows_loaded = int(sum(len(df) for df in self.data.values()))
        self.report["_summary"] = {
            "total_pairs_loaded": loaded,
            "total_pairs_attempted": attempted,
            "total_rows_loaded": total_rows_loaded,
            "load_timestamp": datetime.now().isoformat(),
            "data_directory": str(self.data_dir),
            "timeframe_seconds": TIMEFRAME_SECONDS,
            "gap_threshold_seconds": GAP_THRESHOLD_SECONDS,
            "required_columns": REQUIRED_COLUMNS,
        }
        return self.data

    def get_report(self) -> Dict[str, Any]:
        return self.report


def _pick_default_data_dir(root: Path) -> Path:
    for d in ("SCALPING_DATA_PARQUET", "SCALPING_DATA_RAW", "SCALPING_DATA"):
        p = root / d
        if p.exists():
            return p
    return root / "SCALPING_DATA"


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Load scalping OHLCV 1m data from *_1m.csv or *_1m.parquet.")
    parser.add_argument("--data_dir", type=str, default=str(_pick_default_data_dir(root)))
    parser.add_argument("--pairs", type=str, nargs="+")
    parser.add_argument("--output", type=str)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    loader = ScalpingDataLoader(Path(args.data_dir))
    loader.load_all(args.pairs)
    report = loader.get_report()

    report_json = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(report_json, encoding="utf-8")
        logger.info(f"Report saved to: {args.output}")
    else:
        print(report_json)

    return 0 if report.get("_summary", {}).get("total_pairs_loaded", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())