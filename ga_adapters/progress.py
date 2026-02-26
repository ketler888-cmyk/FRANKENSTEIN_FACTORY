from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

def _now() -> float:
    return time.time()

def append_jsonl(path: str | Path, obj: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    o = dict(obj or {})
    o.setdefault("ts", _now())
    # stable host hint
    try:
        o.setdefault("host", os.environ.get("COMPUTERNAME") or "")
    except Exception:
        pass
    line = json.dumps(o, ensure_ascii=False)
    with p.open("a", encoding="utf-8", errors="backslashreplace") as f:
        f.write(line + "\n")