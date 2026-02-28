def tp_sl_guard(tp, sl):
    if sl == 0:
        return False
    ratio = tp / sl
    return ratio < 50
