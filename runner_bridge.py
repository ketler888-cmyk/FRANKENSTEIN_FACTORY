# -*- coding: utf-8 -*-
"""
runner_bridge.py (compat wrapper)

Some modules/tools may import RunnerBridge from project root.
The canonical implementation lives in ga_adapters/runner_bridge.py.
"""
from __future__ import annotations

from ga_adapters.runner_bridge import RunnerBridge

__all__ = ["RunnerBridge"]