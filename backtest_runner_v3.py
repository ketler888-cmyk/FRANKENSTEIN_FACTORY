# -*- coding: utf-8 -*-
"""
backtest_runner_v3.py — stable CLI wrapper.

Why:
- The previous file was an import-only shim and did not execute main().
- RunnerBridge executes this file as a script, so it MUST call patched main().
"""
from __future__ import annotations
from backtest_runner_v3_patched import main as _main

if __name__ == "__main__":
    raise SystemExit(_main())