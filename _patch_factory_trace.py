from __future__ import annotations
from pathlib import Path
import re

p = Path(r"C:\Users\user\Desktop\Франкинштэйн\factory_ga.py")
src = p.read_text(encoding="utf-8", errors="replace")

def ensure_import(mod: str) -> None:
    global src
    if re.search(r"(?m)^\\s*import\\s+%s\\b" % re.escape(mod), src):
        return
    # insert after last import line in header (best effort)
    m = list(re.finditer(r"(?m)^\\s*(import\\s+.+|from\\s+.+\\s+import\\s+.+)\\s*$", src))
    if m:
        last = m[-1]
        src = src[: last.end()] + f"\\nimport {mod}" + src[last.end():]
    else:
        src = f"import {mod}\\n" + src

ensure_import("sys")
ensure_import("time")
ensure_import("traceback")

# 1) Trace at main() entry
if "[TRACE] ENTER_MAIN" not in src:
    src = re.sub(
        r"(?m)^(def\\s+main\\([^\\)]*\\)\\s*:\\s*)$",
        r"\\1\\n    import sys, time\\n    import logging\\n    logging.info('[TRACE] ENTER_MAIN ts=%s argv=%s', int(time.time()), sys.argv)\\n    _trace_eval_calls = 0\\n    _trace_eval_fail = 0",
        src,
        count=1
    )

# 2) After parse_args()
if "[TRACE] ARGS=" not in src:
    src = re.sub(
        r"(?m)^(\\s*args\\s*=\\s*parser\\.parse_args\\(\\)\\s*)$",
        r"\\1\\n\\g<0>\\n",
        src,
        count=0
    )
    # safer targeted insert: find first args=parse_args and inject right after
    m = re.search(r"(?m)^(\\s*args\\s*=\\s*parser\\.parse_args\\(\\)\\s*)$", src)
    if m:
        indent = re.match(r"^\\s*", m.group(1)).group(0)
        inject = f"{indent}import logging\\n{indent}logging.info('[TRACE] ARGS=%s', vars(args))"
        src = src[:m.end()] + "\\n" + inject + src[m.end():]

# 3) Summary before GA FINISHED marker (covers both logging.info('GA FINISHED') and "GA FINISHED")
if "[TRACE] SUMMARY" not in src:
    # try to locate the GA FINISHED log call
    m = re.search(r"(?m)^(\\s*logging\\.(info|warning|error)\\(\\s*['\\\"]GA FINISHED['\\\"]\\s*\\)\\s*)$", src)
    if m:
        indent = re.match(r"^\\s*", m.group(1)).group(0)
        inject = f"{indent}logging.info('[TRACE] SUMMARY eval_calls=%s eval_fail=%s', _trace_eval_calls, _trace_eval_fail)"
        src = src[:m.start()] + inject + "\\n" + src[m.start():]

# 4) Patch common EVAL_FAIL indentation issue: ensure "logging.error(f\"EVAL_FAIL: {e}\")" aligned to its block
# (we don't know exact block, but we can remove accidental leading extra spaces in that exact line)
src = re.sub(r"(?m)^\\s+logging\\.error\\(f\\\"EVAL_FAIL: \\{e\\}\\\"\\)\\s*$", "            logging.error(f\"EVAL_FAIL: {e}\")", src)

p.write_text(src, encoding="utf-8")
print("PATCH_OK", p)