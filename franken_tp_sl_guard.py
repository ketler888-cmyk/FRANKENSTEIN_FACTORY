import json
import os

DEFAULTS = {
    "tp_min": 0.001,
    "tp_max": 0.020,
    "sl_min": 0.001,
    "sl_max": 0.030,
    "sl_over_tp_min": 0.8,
    "sl_over_tp_max": 4.0,
}

def _load_cfg():
    # 1) env override
    p = os.getenv("FRANK_TP_SL_CFG", "")
    # 2) project default
    if not p:
        p = os.path.join(os.path.dirname(__file__), "config", "tp_sl_constraints.json")
    cfg = dict(DEFAULTS)
    try:
        with open(p, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg

def _clamp(x, lo, hi):
    if x is None:
        return None
    try:
        v = float(x)
    except Exception:
        return None
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def _pick_keys(d):
    # поддержка разных названий параметров
    # tp
    tp_keys = ["k_tp","tp","tp_pct","take_profit","take_profit_pct","tp_percent","tpPrc","tp_prc"]
    sl_keys = ["k_sl","sl","sl_pct","stop_loss","stop_loss_pct","sl_percent","slPrc","sl_prc"]

    tp_k = next((k for k in tp_keys if k in d), None)
    sl_k = next((k for k in sl_keys if k in d), None)
    return tp_k, sl_k

def apply_tp_sl_guard(params: dict) -> dict:
    if not isinstance(params, dict):
        return params
    cfg = _load_cfg()

    tp_k, sl_k = _pick_keys(params)
    if not tp_k or not sl_k:
        return params

    tp = _clamp(params.get(tp_k), cfg["tp_min"], cfg["tp_max"])
    sl = _clamp(params.get(sl_k), cfg["sl_min"], cfg["sl_max"])
    if tp is None or sl is None:
        return params

    # enforce ratio corridor: sl/tp in [min..max]
    r = sl / tp if tp != 0 else cfg["sl_over_tp_max"]
    rmin = float(cfg["sl_over_tp_min"])
    rmax = float(cfg["sl_over_tp_max"])
    if r < rmin:
        sl = tp * rmin
    elif r > rmax:
        sl = tp * rmax

    # clamp again after ratio
    tp = _clamp(tp, cfg["tp_min"], cfg["tp_max"])
    sl = _clamp(sl, cfg["sl_min"], cfg["sl_max"])

    params[tp_k] = float(tp)
    params[sl_k] = float(sl)
    return params
