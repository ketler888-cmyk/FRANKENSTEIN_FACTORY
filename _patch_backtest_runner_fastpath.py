import re, sys

path = r"C:\Users\user\Desktop\Франкинштэйн\backtest_runner.py"
txt = open(path, "r", encoding="utf-8", errors="ignore").read()

# 1) ensure import os exists (needed for env switch)
if re.search(r"^import os\\s*$", txt, flags=re.M) is None:
    # insert after initial imports (after argparse/json/logging/time block)
    # safest: insert after the first occurrence of "import time"
    m = re.search(r"^import time\\s*$", txt, flags=re.M)
    if not m:
        raise SystemExit("Could not locate 'import time' to insert import os")
    ins = m.end()
    txt = txt[:ins] + "\\nimport os\\n" + txt[ins:]

# 2) insert fast method into BacktestRunner class before def run_pair
# find def run_pair indentation
m = re.search(r"^    def run_pair\\(self, pair: str, ohlc: pd\\.DataFrame\\)", txt, flags=re.M)
if not m:
    raise SystemExit("Could not find BacktestRunner.run_pair signature")

insert_at = m.start()

fast_method = r'''
    def run_pair_fast(self, pair: str, ohlc: pd.DataFrame) -> Tuple[List[Trade], Metrics, pd.Series, Dict[str, Any]]:
        """
        FAST PATH: identical logic to run_pair, but avoids pandas in the hot loop.
        Trigger with env FR_FAST=1 (see run_pair switch).
        """
        ind = self.load_indicators(pair)
        self.validate_alignment(ohlc, ind, pair)

        # merge once (still fine), then convert required columns to numpy arrays
        merged = pd.concat([ohlc, ind.drop(columns=["timestamp"])], axis=1)

        required = ["rsi_14","ema_9","ema_21","ema_50","ema_200","macd","macdsignal","macdhist","bb_upper","bb_middle","bb_lower","atr_14"]
        missing = [c for c in required if c not in merged.columns]
        if missing:
            raise ValueError(f"{pair}: missing indicator columns: {missing}")

        # numpy arrays (float64)
        ts = pd.to_datetime(merged["timestamp"], utc=True).to_numpy()
        o_open  = merged["open"].to_numpy(dtype=float)
        o_high  = merged["high"].to_numpy(dtype=float)
        o_low   = merged["low"].to_numpy(dtype=float)
        o_close = merged["close"].to_numpy(dtype=float)

        ema9  = merged["ema_9"].to_numpy(dtype=float)
        ema21 = merged["ema_21"].to_numpy(dtype=float)
        rsi14 = merged["rsi_14"].to_numpy(dtype=float)
        bbm   = merged["bb_middle"].to_numpy(dtype=float)

        pos = Position()
        trades: List[Trade] = []

        equity = float(self.starting_equity)
        total_bars = int(len(o_close))
        bars_in_trade = 0

        # prealloc equity curve
        eq_arr = [0.0] * total_bars

        # local binds (speed)
        calc_fee = self.calc_fee
        notional = float(self.notional_usdt)

        # Iterate until second last bar because execution uses next bar open
        for i in range(total_bars - 1):
            eq_arr[i] = equity

            if pos.is_open:
                bars_in_trade += 1

                lo = o_low[i]
                hi = o_high[i]

                hit_sl = (pos.sl > 0 and lo <= pos.sl)
                hit_tp = (pos.tp > 0 and hi >= pos.tp)

                # exit signal: ema9 < ema21 (same as self.exit_signal)
                hit_exit = (not (ema9[i] != ema9[i] or ema21[i] != ema21[i])) and (ema9[i] < ema21[i])

                if hit_sl or hit_tp or hit_exit:
                    reason = ExitReason.STOP_LOSS if hit_sl else (ExitReason.TAKE_PROFIT if hit_tp else ExitReason.EXIT_SIGNAL)

                    exit_price = float(o_open[i + 1])
                    exit_time = ts[i + 1]

                    entry_value = pos.qty * pos.entry_price
                    exit_value = pos.qty * exit_price

                    gross = exit_value - entry_value
                    exit_fee = calc_fee(exit_value)
                    total_fee = pos.entry_fee + exit_fee
                    net = gross - total_fee

                    equity += net

                    # timestamps to iso only per trade (cheap because few trades)
                    trades.append(Trade(
                        pair=pair,
                        entry_time=pd.Timestamp(pos.entry_time).isoformat(),
                        entry_price=float(pos.entry_price),
                        exit_time=pd.Timestamp(exit_time).isoformat(),
                        exit_price=float(exit_price),
                        quantity=float(pos.qty),
                        gross_pnl=float(gross),
                        entry_fee=float(pos.entry_fee),
                        exit_fee=float(exit_fee),
                        total_fee=float(total_fee),
                        net_pnl=float(net),
                        exit_reason=str(reason.value),
                        entry_bar_index=int(pos.entry_index),
                        exit_bar_index=int(i + 1),
                        tp_price=float(pos.tp),
                        sl_price=float(pos.sl),
                    ))

                    pos.close()
                    continue

            # Entry when flat (same as self.entry_signal)
            if not pos.is_open:
                e9 = ema9[i]
                e21 = ema21[i]
                rsi = rsi14[i]
                clo = o_close[i]
                mid = bbm[i]

                # handle NaNs (same semantics)
                if not (e9 != e9 or e21 != e21 or rsi != rsi or clo != clo or mid != mid):
                    if (e9 > e21) and (rsi < 35.0) and (clo < mid):
                        entry_price = float(o_open[i + 1])
                        if entry_price > 0:
                            qty = notional / entry_price
                            entry_value = qty * entry_price
                            entry_fee = calc_fee(entry_value)
                            equity -= entry_fee

                            tp = entry_price * (1.0 + float(self.tp_pct))
                            sl = entry_price * (1.0 - float(self.sl_pct))

                            pos.open(
                                entry_time=ts[i + 1],
                                entry_price=entry_price,
                                qty=qty,
                                tp=tp,
                                sl=sl,
                                entry_fee=entry_fee,
                                entry_index=i + 1
                            )
                            bars_in_trade = 0

        # last bar equity
        eq_arr[-1] = equity
        eq = pd.Series(eq_arr)

        if len(trades) == 0:
            m = Metrics(
                pair=pair, trades=0, winrate=0.0, gross_pnl=0.0, fees=0.0, net_pnl=0.0,
                max_drawdown=0.0, avg_trade=0.0, profit_factor=0.0,
                total_bars=total_bars, bars_in_trade=0, time_in_market=0.0
            )
        else:
            gross_pnl = float(sum(t.gross_pnl for t in trades))
            fees = float(sum(t.total_fee for t in trades))
            net_pnl = float(sum(t.net_pnl for t in trades))

            wins = [t.net_pnl for t in trades if t.net_pnl > 0]
            losses = [t.net_pnl for t in trades if t.net_pnl <= 0]
            winrate = float(len(wins) / len(trades))

            total_wins = float(sum(wins)) if wins else 0.0
            total_losses = float(abs(sum(losses))) if losses else 0.0
            profit_factor = float(total_wins / total_losses) if total_losses > 0 else float("inf")

            roll_max = eq.cummax()
            dd = (eq - roll_max) / roll_max.replace(0, np.nan)
            max_dd = float(abs(dd.min())) if len(dd) else 0.0

            avg_trade = float(np.mean([t.net_pnl for t in trades]))

            m = Metrics(
                pair=pair, trades=int(len(trades)), winrate=winrate, gross_pnl=gross_pnl, fees=fees, net_pnl=net_pnl,
                max_drawdown=max_dd, avg_trade=avg_trade, profit_factor=profit_factor,
                total_bars=total_bars, bars_in_trade=int(bars_in_trade),
                time_in_market=(bars_in_trade / total_bars) if total_bars else 0.0
            )

        pair_report = {
            "status": "completed",
            "total_trades": int(len(trades)),
            "total_bars": int(total_bars),
            "bars_in_trade": int(bars_in_trade),
            "time_in_market": (bars_in_trade / total_bars) if total_bars else 0.0,
            "final_equity": float(eq.iloc[-1]),
            "net_pnl": float(m.net_pnl),
            "fee_rate_used": self._fee_rate(),
            "fast_path": True,
        }

        return trades, m, eq, pair_report

'''

# Insert fast method
txt2 = txt[:insert_at] + fast_method + txt[insert_at:]

# 3) Add env switch at start of run_pair body (before first line 'ind = ...')
# find the first line inside run_pair (ind = ...)
m2 = re.search(r"^    def run_pair\\(self, pair: str, ohlc: pd\\.DataFrame\\).*?:\\s*\\n(        )ind = self\\.load_indicators", txt2, flags=re.M)
if not m2:
    raise SystemExit("Could not locate insertion point inside run_pair")

indent = m2.group(1)
switch = indent + 'if os.environ.get("FR_FAST","0") == "1":\\n' + indent + "    return self.run_pair_fast(pair, ohlc)\\n\\n"
# insert right before 'ind = ...'
txt2 = txt2[:m2.start(1)] + switch + txt2[m2.start(1):]

open(path, "w", encoding="utf-8").write(txt2)
print("OK patched:", path)
