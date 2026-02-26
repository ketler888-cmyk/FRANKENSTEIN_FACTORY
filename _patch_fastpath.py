import re, textwrap
from pathlib import Path

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

if "def run_pair_fast" in src and "FR_FAST" in src:
    print("[OK] Already patched (run_pair_fast + FR_FAST found).")
    raise SystemExit(0)

# ensure import os exists
if re.search(r"^import os\b", src, flags=re.M) is None:
    m = re.search(r"^import time\s*$", src, flags=re.M)
    if not m:
        raise SystemExit("Could not locate 'import time' to insert import os")
    src = src[:m.end()] + "\nimport os\n" + src[m.end():]

method = textwrap.dedent(r"""
def run_pair_fast(self, pair: str, ohlc: pd.DataFrame) -> Tuple[List[Trade], Metrics, pd.Series, Dict[str, Any]]:
    \"\"\"Fast path: avoids pandas iloc/Series in hot loop.
    Enabled by env FR_FAST=1.
    Optional dev/profiling: FR_TAIL_ALIGN=1 to tail-align indicators if ohlc is trimmed.
    \"\"\"
    ind = self.load_indicators(pair)

    if len(ohlc) != len(ind) and os.getenv("FR_TAIL_ALIGN","0") == "1":
        if len(ohlc) < len(ind):
            ind_tail = ind.iloc[-len(ohlc):].reset_index(drop=True)
            if ("timestamp" in ohlc.columns) and ("timestamp" in ind_tail.columns):
                if (ohlc["timestamp"].to_numpy() == ind_tail["timestamp"].to_numpy()).all():
                    ind = ind_tail

    self.validate_alignment(ohlc, ind, pair)

    ts = ohlc["timestamp"].to_numpy()
    o = ohlc["open"].to_numpy(dtype=np.float64)
    h = ohlc["high"].to_numpy(dtype=np.float64)
    l = ohlc["low"].to_numpy(dtype=np.float64)
    c = ohlc["close"].to_numpy(dtype=np.float64)

    rsi = ind["rsi_14"].to_numpy(dtype=np.float64)
    ema9 = ind["ema_9"].to_numpy(dtype=np.float64)
    ema21 = ind["ema_21"].to_numpy(dtype=np.float64)
    bbm = ind["bb_middle"].to_numpy(dtype=np.float64)

    pos = Position()
    trades: List[Trade] = []

    equity = float(self.starting_equity)
    eq_list = []
    bars_in_trade = 0
    total_bars = int(len(c))
    fee_rate = self._fee_rate()

    def isnan(x: float) -> bool:
        return x != x

    for i in range(total_bars - 1):
        eq_list.append(equity)

        if pos.is_open:
            bars_in_trade += 1
            hit_sl = (pos.sl > 0.0 and l[i] <= pos.sl)
            hit_tp = (pos.tp > 0.0 and h[i] >= pos.tp)

            ex = False
            e9 = ema9[i]; e21 = ema21[i]
            if (not isnan(e9)) and (not isnan(e21)):
                ex = (e9 < e21)

            if hit_sl or hit_tp or ex:
                reason = ExitReason.STOP_LOSS if hit_sl else (ExitReason.TAKE_PROFIT if hit_tp else ExitReason.EXIT_SIGNAL)

                exit_price = float(o[i + 1])
                exit_time = pd.to_datetime(ts[i + 1], utc=True)

                entry_value = pos.qty * pos.entry_price
                exit_value = pos.qty * exit_price

                gross = exit_value - entry_value
                exit_fee = float(exit_value) * fee_rate
                total_fee = pos.entry_fee + exit_fee
                net = gross - total_fee

                equity += net

                trades.append(Trade(
                    pair=pair,
                    entry_time=pd.to_datetime(pos.entry_time, utc=True).isoformat(),
                    entry_price=float(pos.entry_price),
                    exit_time=exit_time.isoformat(),
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

        if not pos.is_open:
            e9 = ema9[i]; e21 = ema21[i]; rr = rsi[i]; cc = c[i]; mid = bbm[i]
            if (not isnan(e9)) and (not isnan(e21)) and (not isnan(rr)) and (not isnan(cc)) and (not isnan(mid)):
                if (e9 > e21) and (rr < 35.0) and (cc < mid):
                    entry_price = float(o[i + 1])
                    if entry_price > 0.0:
                        entry_time = pd.to_datetime(ts[i + 1], utc=True)
                        qty = float(self.notional_usdt) / entry_price
                        entry_value = qty * entry_price
                        entry_fee = float(entry_value) * fee_rate
                        equity -= entry_fee

                        tp = entry_price * (1.0 + float(self.tp_pct))
                        sl = entry_price * (1.0 - float(self.sl_pct))

                        pos.open(entry_time, entry_price, qty, i + 1, tp, sl, entry_fee)
                        bars_in_trade = 0

    if pos.is_open:
        exit_price = float(c[-1])
        exit_time = pd.to_datetime(ts[-1], utc=True)

        entry_value = pos.qty * pos.entry_price
        exit_value = pos.qty * exit_price

        gross = exit_value - entry_value
        exit_fee = float(exit_value) * fee_rate
        total_fee = pos.entry_fee + exit_fee
        net = gross - total_fee

        equity += net

        trades.append(Trade(
            pair=pair,
            entry_time=pd.to_datetime(pos.entry_time, utc=True).isoformat(),
            entry_price=float(pos.entry_price),
            exit_time=exit_time.isoformat(),
            exit_price=float(exit_price),
            quantity=float(pos.qty),
            gross_pnl=float(gross),
            entry_fee=float(pos.entry_fee),
            exit_fee=float(exit_fee),
            total_fee=float(total_fee),
            net_pnl=float(net),
            exit_reason=str(ExitReason.END_OF_DATA.value),
            entry_bar_index=int(pos.entry_index),
            exit_bar_index=int(total_bars - 1),
            tp_price=float(pos.tp),
            sl_price=float(pos.sl),
        ))
        pos.close()

    eq = pd.Series(eq_list, dtype="float64")

    m = self.compute_metrics(pair, trades, eq, total_bars, bars_in_trade)

    pair_report = {
        "status": "completed",
        "total_trades": int(len(trades)),
        "total_bars": int(total_bars),
        "bars_in_trade": int(bars_in_trade),
        "time_in_market": (bars_in_trade / total_bars) if total_bars else 0.0,
        "final_equity": float(equity),
        "net_pnl": float(getattr(m, "net_pnl", 0.0)),
        "fee_rate_used": fee_rate,
        "fast_path": True,
    }
    return trades, m, eq, pair_report
""").strip("\n")

m = re.search(r"\n    def run_pair\(", src)
if not m:
    raise SystemExit("Could not find 'def run_pair' to insert fast method before it")

insert_pos = m.start() + 1
src = src[:insert_pos] + textwrap.indent(method, "    ") + "\n\n" + src[insert_pos:]

m2 = re.search(r"^    def run_pair\(self, pair: str, ohlc: pd\.DataFrame\).*?:\s*$", src, flags=re.M)
if not m2:
    raise SystemExit("run_pair signature not found for switch injection")

line_end = src.find("\n", m2.end())
inject = '        if os.getenv("FR_FAST","0") == "1":\n            return self.run_pair_fast(pair, ohlc)\n'
window = src[m2.start(): line_end + 400]
if "FR_FAST" not in window:
    src = src[:line_end+1] + inject + src[line_end+1:]

path.write_text(src, encoding="utf-8")
print("[OK] Patched backtest_runner.py (run_pair_fast + FR_FAST).")
