from common import crossover, crossunder

def entry(data, cfg):
    """
    cfg:
      - atr_period
      - supertrend_mult
      - cci_period
      - cci_entry_threshold
    """
    closes = data["close"]
    highs = data["high"]
    lows = data["low"]

    atr = closes.rolling(cfg["atr_period"]).apply(lambda s: s.max() - s.min(), raw=True)
    hl2 = (highs + lows) / 2
    supertrend = hl2 - (atr * cfg["supertrend_mult"])

    cci = (hl2 - hl2.rolling(cfg["cci_period"]).mean()) / (0.015 * hl2.rolling(cfg["cci_period"]).std())

    entries = crossover(cci, cfg["cci_entry_threshold"])  # покупка
    exits   = crossunder(cci, -cfg["cci_entry_threshold"])  # продажа

    return entries, exits
