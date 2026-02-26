import re
from pathlib import Path

path = Path("backtest_runner.py")
src  = path.read_text(encoding="utf-8-sig")

# ensure import os exists (already likely)
if re.search(r"^import os\b", src, flags=re.M) is None:
    m = re.search(r"^import time\s*$", src, flags=re.M)
    if m:
        src = src[:m.end()] + "\nimport os\n" + src[m.end():]

# 1) Add self._ind_cache in __init__
m_init = re.search(r"^\s*def __init__\s*\(self.*?\)\s*:\s*$", src, flags=re.M)
if not m_init:
    raise SystemExit("Could not find __init__")

# find end of __init__ signature line
line_end = src.find("\n", m_init.end())
# find next few lines to see if already present
window = src[line_end: line_end+400]
if "_ind_cache" not in window:
    # insert after first line in __init__ body (next line after signature)
    insert_pos = line_end + 1
    src = src[:insert_pos] + "        self._ind_cache = {}\n" + src[insert_pos:]
    added_cache = True
else:
    added_cache = False

# 2) Patch load_indicators to use cache.
# We look for def load_indicators(self, pair...) and then add:
#   if pair in self._ind_cache: return self._ind_cache[pair]
m_li = re.search(r"^\s*def\s+load_indicators\s*\(\s*self\s*,\s*pair\b.*?\)\s*:\s*$", src, flags=re.M)
if not m_li:
    raise SystemExit("Could not find load_indicators(self, pair, ...)")

li_line_end = src.find("\n", m_li.end())
# determine indent level inside function (signature indent + 4 spaces)
sig_line = src[m_li.start():li_line_end]
indent = re.match(r"^(\s*)def\s+load_indicators", sig_line).group(1)
body_indent = indent + "    "

# check if cache guard already present
li_window = src[li_line_end: li_line_end+500]
if "self._ind_cache" not in li_window:
    guard = (
        f"{body_indent}# FR: indicator cache\n"
        f"{body_indent}try:\n"
        f"{body_indent}    if pair in self._ind_cache:\n"
        f"{body_indent}        return self._ind_cache[pair]\n"
        f"{body_indent}except Exception:\n"
        f"{body_indent}    pass\n"
    )
    src = src[:li_line_end+1] + guard + src[li_line_end+1:]
    added_guard = True
else:
    added_guard = False

# 3) At the end of load_indicators, ensure it stores to cache before returning.
# Best-effort: replace "return ind" or "return df" with caching wrapper.
# We'll patch the first plain 'return ' line inside load_indicators block.
# Find load_indicators block end: next def at same indent.
start = m_li.start()
next_def = re.search(r"^\s*def\s+", src[m_li.end():], flags=re.M)
end = (m_li.end() + next_def.start()) if next_def else len(src)
block = src[start:end]

# If already storing, skip
if "self._ind_cache[pair]" not in block:
    # find a return statement likely returning indicators dataframe
    m_ret = re.search(r"^\s*return\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", block, flags=re.M)
    if m_ret:
        var = m_ret.group(1)
        rep = (
            f"{body_indent}# FR: store to cache\n"
            f"{body_indent}try:\n"
            f"{body_indent}    self._ind_cache[pair] = {var}\n"
            f"{body_indent}except Exception:\n"
            f"{body_indent}    pass\n"
            f"{body_indent}return {var}\n"
        )
        block2 = block[:m_ret.start()] + rep + block[m_ret.end():]
        src = src[:start] + block2 + src[end:]
        added_store = True
    else:
        added_store = False
else:
    added_store = False

path.write_text(src, encoding="utf-8")
print("[OK] Patched indicator cache:",
      "init_cache=" + str(added_cache),
      "guard=" + str(added_guard),
      "store=" + str(added_store))
