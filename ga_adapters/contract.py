from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

# --- UTF-8 safety (Windows console / Cyrillic paths) ---
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

def normalize_pair(p: Any) -> str:
    if p is None:
        return ""
    s = str(p).strip().upper()
    s = s.replace("/", "").replace("-", "").replace("_", "")
    return s

def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}

def load_factory_config(root: Path) -> Dict[str, Any]:
    return read_json(root / "configs" / "factory_config.json")

def _corridor(cfg: Dict[str, Any]) -> Dict[str, float]:
    c = (cfg or {}).get("tp_sl_corridor") or {}
    # defaults (safe)
    d = {
        "tp_pct_min": 0.30, "tp_pct_max": 1.20,
        "sl_pct_min": 0.35, "sl_pct_max": 2.50,
        "min_rr": 0.50, "max_rr": 4.00,
    }
    for k, v in d.items():
        try:
            c[k] = float(c.get(k, v))
        except Exception:
            c[k] = float(v)
    return c

def enforce_tp_sl_corridor(params: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforces corridor only if tp/sl-like fields exist.
    Recognizes:
      tp_pct + sl_pct
      tp + sl
      take_pct + stop_pct
      take + stop
    RR = tp/sl is clamped into [min_rr, max_rr] by adjusting tp (preferred) else sl.
    """
    if not isinstance(params, dict):
        return params

    c = _corridor(cfg)
    tp_keys = [("tp_pct", "sl_pct"), ("tp", "sl"), ("take_pct", "stop_pct"), ("take", "stop")]
    found: Optional[Tuple[str, str]] = None
    for a, b in tp_keys:
        if a in params and b in params:
            found = (a, b)
            break
    if not found:
        return params

    tp_k, sl_k = found
    try:
        tp = float(params.get(tp_k))
        sl = float(params.get(sl_k))
    except Exception:
        return params

    # clamp absolute corridors
    if "pct" in tp_k or tp_k.endswith("_pct"):
        tp = max(c["tp_pct_min"], min(c["tp_pct_max"], tp))
        sl = max(c["sl_pct_min"], min(c["sl_pct_max"], sl))

    # RR clamp
    if sl <= 0:
        sl = max(c["sl_pct_min"], 0.01)
    rr = tp / sl
    if rr < c["min_rr"]:
        tp = c["min_rr"] * sl
    elif rr > c["max_rr"]:
        tp = c["max_rr"] * sl

    params[tp_k] = float(tp)
    params[sl_k] = float(sl)
    params["_rr"] = float(tp / sl) if sl > 0 else 0.0
    return params

def env_utf8() -> Dict[str, str]:
    e = dict(os.environ)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    e["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    return e