import io, re, sys

PATH = sys.argv[1]

src = io.open(PATH, "r", encoding="utf-8").read()
orig = src

# Find the exact debug block we inserted earlier in run_backtest_segment:
# It starts after "atr_median = None" and ends before "# ============================================================================
# We will replace it with a safe version that computes atr_median BEFORE using it.

pattern = re.compile(
    r"(atr_median\s*=\s*None\s*\r?\n)"
    r"(\s*# ===== DEBUG ENTRY FILTERS.*?\r?\n)"
    r"(.*?\r?\n)"
    r"(\s*# ============================================================================\s*\r?\n)",
    re.DOTALL
)

m = pattern.search(src)
if not m:
    print("PATCH: debug block not found (nothing changed)")
    sys.exit(0)

indent = re.match(r"^(\s*)", m.group(2)).group(1)

new_block = []
new_block.append(m.group(1))  # atr_median = None

# keep existing logic line below in file: if 'min_atr_multiplier' in params: atr_median = median(...)
# We just ensure debug uses a local safe median when atr_median is None.

new_block.append(indent + "# ===== DEBUG ENTRY FILTERS (diagnostic only; does NOT change trading logic) =====\n")
new_block.append(indent + "if getattr(self, \"debug_signals\", False):\n")
new_block.append(indent + "    try:\n")
new_block.append(indent + "        n = int(len(df))\n")
new_block.append(indent + "        if n > 0:\n")
new_block.append(indent + "            trend = (df[\"ema_9\"] > df[\"ema_21\"]) if (\"ema_9\" in df.columns and \"ema_21\" in df.columns) else None\n")
new_block.append(indent + "            rsi   = (df[\"rsi_14\"] < 35) if (\"rsi_14\" in df.columns) else None\n")
new_block.append(indent + "            bb    = (df[\"close\"] < df[\"bb_middle\"]) if (\"close\" in df.columns and \"bb_middle\" in df.columns) else None\n")
new_block.append(indent + "            mult  = float(params.get(\"min_atr_multiplier\", 1.0)) if isinstance(params, dict) else 1.0\n")
new_block.append(indent + "            # atr_median может быть ещё None здесь; берём локально из df безопасно\n")
new_block.append(indent + "            local_med = None\n")
new_block.append(indent + "            if \"atr_14\" in df.columns:\n")
new_block.append(indent + "                try:\n")
new_block.append(indent + "                    local_med = float(df[\"atr_14\"].median())\n")
new_block.append(indent + "                except Exception:\n")
new_block.append(indent + "                    local_med = None\n")
new_block.append(indent + "            if local_med is not None:\n")
new_block.append(indent + "                atr = (df[\"atr_14\"] >= (local_med * mult))\n")
new_block.append(indent + "            else:\n")
new_block.append(indent + "                atr = None\n")
new_block.append(indent + "            all_ok = None\n")
new_block.append(indent + "            if trend is not None and rsi is not None and bb is not None and atr is not None:\n")
new_block.append(indent + "                all_ok = (trend & rsi & bb & atr)\n")
new_block.append(indent + "            def pct(x):\n")
new_block.append(indent + "                return 100.0 * float(x) / float(n) if n else 0.0\n")
new_block.append(indent + "            logger.info(\n")
new_block.append(indent + "                f\"[DEBUG_SIGNALS] bars={n} \"\n")
new_block.append(indent + "                + (f\"trend={int(trend.sum())}({pct(trend.sum()):.2f}%) \" if trend is not None else \"trend=NA \")\n")
new_block.append(indent + "                + (f\"rsi<35={int(rsi.sum())}({pct(rsi.sum()):.2f}%) \" if rsi is not None else \"rsi<35=NA \")\n")
new_block.append(indent + "                + (f\"close<bbmid={int(bb.sum())}({pct(bb.sum()):.2f}%) \" if bb is not None else \"close<bbmid=NA \")\n")
new_block.append(indent + "                + (f\"atr_gate(mult={mult:.3f})={int(atr.sum())}({pct(atr.sum()):.2f}%) \" if atr is not None else f\"atr_gate(mult={mult:.3f})=NA \")\n")
new_block.append(indent + "                + (f\"ALL={int(all_ok.sum())}({pct(all_ok.sum()):.4f}%)\" if all_ok is not None else \"ALL=NA\")\n")
new_block.append(indent + "            )\n")
new_block.append(indent + "    except Exception as e:\n")
new_block.append(indent + "        try:\n")
new_block.append(indent + "            logger.info(f\"[DEBUG_SIGNALS] error: {e}\")\n")
new_block.append(indent + "        except Exception:\n")
new_block.append(indent + "            pass\n")
new_block.append(indent + "# ============================================================================\n")

new_src = src[:m.start()] + "".join(new_block) + src[m.end():]

io.open(PATH, "w", encoding="utf-8", newline="").write(new_src)
print("PATCH: applied OK")
