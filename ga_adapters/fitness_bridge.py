from typing import Dict, Any

class FitnessBridge:
    """
    Мост: metrics -> fitness score.
    Все веса берём из configs/ga_config.json (секция fitness).
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg or {}
        self.w_ret = float(self.cfg.get("return_weight", 1.0))
        self.w_dd  = float(self.cfg.get("drawdown_weight", 2.0))
        self.w_wr  = float(self.cfg.get("winrate_weight", 0.5))
        self.w_pf  = float(self.cfg.get("profit_factor_weight", 0.3))
        self.w_tc  = float(self.cfg.get("trades_count_weight", 0.02))
        self.min_trades = int(self.cfg.get("min_trades", 10))
        self.min_trades_penalty = float(self.cfg.get("min_trades_penalty", 1.0))

    def calc(self, m: Dict[str, float]) -> float:
        # expected keys: total_return, max_drawdown, winrate, profit_factor, trades_count
        total_return  = float(m.get("total_return", 0.0))
        max_drawdown  = float(m.get("max_drawdown", 0.0))
        winrate       = float(m.get("winrate", 0.0))
        profit_factor = float(m.get("profit_factor", 1.0))
        trades_count  = float(m.get("trades_count", 0.0))

        # простая, устойчивая фитнес-функция
        score = 0.0
        score += total_return * self.w_ret
        score -= max_drawdown * self.w_dd
        score += winrate * self.w_wr
        score += profit_factor * self.w_pf

        # лог-стабилизация количества сделок (чтобы не раздувало)
        if trades_count > 0:
            import math
            score += math.log(1.0 + trades_count) * self.w_tc

        if trades_count < self.min_trades:
            score -= self.min_trades_penalty

        return float(score)
