import pandas as pd
from pathlib import Path

class ParquetLoader:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parent.parent / "SCALPING_DATA_PARQUET"

    def load(self, symbol: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol}_1m.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")
        print(f"DEBUG: loading {path}")
        df = pd.read_parquet(path).head(1000)
        df.columns = [c.lower() for c in df.columns]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        df.set_index("timestamp", inplace=True)
        return df


