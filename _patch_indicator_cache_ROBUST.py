import re
from pathlib import Path

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

# 1) Find BacktestRunner.__init__
m_init = re.search(r"(?m)^\s*def\s+__init__\s*\(self[^)]*\)\s*:\s*$", src)
if not m_init:
    raise SystemExit("Could not find __init__(self, ...)")

# determine __init__ indent
line_start = src.rfind("\n", 0, m_init.start()) + 1
init_indent = re.match(r"(\s*)def", src[line_start:m_init.start()+10]).group(1)
body_indent = init_indent + (" " * 4)

# find end of __init__ by next def at same indent
pat_next_def = r"(?m)^\s*def\s+\w+\s*\("
m_next = re.search(pat_next_def, src[m_init.end():])
init_end = (m_init.end() + m_next.start()) if m_next else len(src)
init_block = src[line_start:init_end]

# add cache init if missing
if "_ind_cache" not in init_block:
    # insert after first line of __init__ signature
    sig_end = src.find("\n", m_init.end())
    if sig_end == -1:
        raise SystemExit("Bad __init__ block (no newline)")
    inject = f"{body_indent}# Frankenstein: indicator cache\n{body_indent}self._ind_cache = {{}}\n"
    src = src[:sig_end+1] + inject + src[sig_end+1:]
    print("[OK] Injected self._ind_cache into __init__")
else:
    print("[OK] __init__ already has _ind_cache")

# 2) Find load_indicators
m_li = re.search(r"(?m)^\s*def\s+load_indicators\s*\(\s*self\s*,\s*pair\b[^)]*\)\s*:\s*$", src)
if not m_li:
    # fallback: any load_indicators(self, pair...) signature
    m_li = re.search(r"(?m)^\s*def\s+load_indicators\s*\(\s*self[^)]*\)\s*:\s*$", src)
if not m_li:
    raise SystemExit("Could not find def load_indicators(...)")

li_line_start = src.rfind("\n", 0, m_li.start()) + 1
li_indent = re.match(r"(\s*)def", src[li_line_start:m_li.start()+10]).group(1)
li_body_indent = li_indent + (" " * 4)

# find end of load_indicators by next def at same indent
m_next2 = re.search(r"(?m)^" + re.escape(li_indent) + r"def\s+\w+\s*\(", src[m_li.end():])
li_end = (m_li.end() + m_next2.start()) if m_next2 else len(src)
li_block = src[li_line_start:li_end]

# add guard at top of function body if missing
guard = (
    f"{li_body_indent}# Frankenstein: cached indicators\n"
    f"{li_body_indent}if hasattr(self, '_ind_cache') and (pair in self._ind_cache):\n"
    f"{li_body_indent}    return self._ind_cache[pair]\n"
)
if "pair in self._ind_cache" not in li_block:
    sig_end = src.find("\n", m_li.end())
    if sig_end == -1:
        raise SystemExit("Bad load_indicators block (no newline)")
    src = src[:sig_end+1] + guard + src[sig_end+1:]
    print("[OK] Inserted cache-guard into load_indicators")
else:
    print("[OK] load_indicators already has cache-guard")

# refresh li_block positions after possible insert
src2 = src
m_li2 = re.search(r"(?m)^\s*def\s+load_indicators\s*\(\s*self\s*,\s*pair\b[^)]*\)\s*:\s*$", src2) or \
        re.search(r"(?m)^\s*def\s+load_indicators\s*\(\s*self[^)]*\)\s*:\s*$", src2)
li_line_start2 = src2.rfind("\n", 0, m_li2.start()) + 1
li_indent2 = re.match(r"(\s*)def", src2[li_line_start2:m_li2.start()+10]).group(1)
m_next3 = re.search(r"(?m)^" + re.escape(li_indent2) + r"def\s+\w+\s*\(", src2[m_li2.end():])
li_end2 = (m_li2.end() + m_next3.start()) if m_next3 else len(src2)
li_block2 = src2[li_line_start2:li_end2]
li_body_indent2 = li_indent2 + (" " * 4)

# add store right before first "return <expr>" (and avoid duplicating)
if "self._ind_cache[pair]" not in li_block2.splitlines()[-30:]:
    m_ret = re.search(r"(?m)^" + re.escape(li_body_indent2) + r"return\s+(.+?)\s*$", li_block2)
    if m_ret:
        ret_expr = m_ret.group(1).strip()
        store = f"{li_body_indent2}# Frankenstein: store to cache\n{li_body_indent2}self._ind_cache[pair] = {ret_expr}\n"
        # insert store right before that return
        abs_ret_start = li_line_start2 + m_ret.start()
        src2 = src2[:abs_ret_start] + store + src2[abs_ret_start:]
        print("[OK] Inserted cache-store before return in load_indicators")
    else:
        print("[WARN] No simple 'return X' found in load_indicators; store not inserted.")
else:
    print("[OK] load_indicators already has cache-store")

path.write_text(src2, encoding="utf-8")
print("[OK] ROBUST indicator cache patch applied.")
