import re
from pathlib import Path

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

# Find load_indicators in ANY signature form (allows -> return annotation)
m_li = re.search(
    r"(?m)^(?P<indent>\s*)def\s+load_indicators\s*\(.*?\)\s*(?:->\s*[^:]+)?\s*:\s*$",
    src
)
if not m_li:
    # show nearby hints to help debugging (prints only in tool output)
    hints = []
    for pat in [r"def\s+load_", r"load_ind", r"indicat", r"rsi_14", r"bb_middle"]:
        if re.search(pat, src, flags=re.I):
            hints.append(pat)
    raise SystemExit("Could not find def load_indicators(...) with flexible regex. HintsFound=" + ",".join(hints))

indent = m_li.group("indent")
body_indent = indent + " " * 4

# Find end of function by next def at same indent
start_line = src.rfind("\n", 0, m_li.start()) + 1
pat_next = r"(?m)^" + re.escape(indent) + r"def\s+\w+\s*\("
m_next = re.search(pat_next, src[m_li.end():])
end = (m_li.end() + m_next.start()) if m_next else len(src)

block = src[start_line:end]

# 1) Insert guard after signature line (if missing)
if "pair in self._ind_cache" not in block:
    sig_end = src.find("\n", m_li.end())
    if sig_end == -1:
        raise SystemExit("Bad load_indicators block (no newline after signature)")

    guard = (
        f"{body_indent}# Frankenstein: cached indicators\n"
        f"{body_indent}if hasattr(self, '_ind_cache') and (pair in self._ind_cache):\n"
        f"{body_indent}    return self._ind_cache[pair]\n"
    )
    src = src[:sig_end+1] + guard + src[sig_end+1:]
    print("[OK] Inserted cache-guard into load_indicators")
else:
    print("[OK] cache-guard already present")

# Recompute block after insert
src2 = src
m_li2 = re.search(
    r"(?m)^(?P<indent>\s*)def\s+load_indicators\s*\(.*?\)\s*(?:->\s*[^:]+)?\s*:\s*$",
    src2
)
indent2 = m_li2.group("indent")
body_indent2 = indent2 + " " * 4
start_line2 = src2.rfind("\n", 0, m_li2.start()) + 1
pat_next2 = r"(?m)^" + re.escape(indent2) + r"def\s+\w+\s*\("
m_next2 = re.search(pat_next2, src2[m_li2.end():])
end2 = (m_li2.end() + m_next2.start()) if m_next2 else len(src2)
block2 = src2[start_line2:end2]

# 2) Insert store right before first "return X" at function-body indent (if missing)
if "self._ind_cache[pair]" not in block2:
    m_ret = re.search(r"(?m)^" + re.escape(body_indent2) + r"return\s+(.+?)\s*$", block2)
    if not m_ret:
        print("[WARN] No simple 'return X' found at base indent; store not inserted.")
    else:
        ret_expr = m_ret.group(1).strip()
        store = (
            f"{body_indent2}# Frankenstein: store to cache\n"
            f"{body_indent2}self._ind_cache[pair] = {ret_expr}\n"
        )
        abs_ret_start = start_line2 + m_ret.start()
        src2 = src2[:abs_ret_start] + store + src2[abs_ret_start:]
        print("[OK] Inserted cache-store before return in load_indicators")
else:
    print("[OK] cache-store already present")

path.write_text(src2, encoding="utf-8")
print("[OK] load_indicators cache patch v2 applied.")
