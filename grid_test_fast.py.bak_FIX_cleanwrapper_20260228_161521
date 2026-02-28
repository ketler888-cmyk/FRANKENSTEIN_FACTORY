# -*- coding: utf-8 -*-
\""\"FRANKEN grid_test_fast
This file is a SAFE wrapper around grid_test_v2.py.
Reason: previous patches broke indentation and made this file uncompilable.
Usage: python .\grid_test_fast.py [same args as grid_test_v2]
\""\""

from __future__ import annotations
import sys

def _run() -> int:
    from grid_test_v2 import main as _main
    return int(_main() or 0)

if __name__ == "__main__":
    raise SystemExit(_run())