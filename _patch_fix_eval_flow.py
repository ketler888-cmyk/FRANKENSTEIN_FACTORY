from pathlib import Path
import re

ROOT = Path(r"C:\Users\user\Desktop\Франкинштэйн")
FACTORY = Path(r"C:\Users\user\Desktop\Франкинштэйн\factory_ga.py")
RUNNER  = Path(r"C:\Users\user\Desktop\Франкинштэйн\ga_adapters\runner_bridge.py")

def patch_runner():
    s = RUNNER.read_text(encoding="utf-8", errors="replace")

    # 1) ensure _mk_eval_dir returns d
    # Find def _mk_eval_dir ... and if there's no "return d" inside, add it right before next def or end.
    m = re.search(r"(?ms)^(\\s*def\\s+_mk_eval_dir\\(.*?\\):\\s*\\n)(.*?)(?=^\\s*def\\s+|\\Z)", s)
    if not m:
        raise SystemExit("PATCH_RUNNER: cannot find _mk_eval_dir() block")

    head, body = m.group(1), m.group(2)

    if re.search(r"(?m)^\\s*return\\s+d\\b", body) is None:
        # add return d at end of the function block
        body2 = body.rstrip() + "\\n        return d\\n"
        s = s[:m.start()] + head + body2 + s[m.end():]

    # 2) fix subprocess.run cwd/creationflags bug: "cwd=str(ROOT, creationflags=...)" -> "cwd=str(ROOT), creationflags=..."
    s = re.sub(
        r"subprocess\\.run\\(([^\\)]*?)cwd\\s*=\\s*str\\(ROOT\\s*,\\s*creationflags\\s*=\\s*CREATE_NO_WINDOW\\)([^\\)]*?)\\)",
        r"subprocess.run(\\1cwd=str(ROOT), creationflags=CREATE_NO_WINDOW\\2)",
        s,
        flags=re.S
    )

    # 3) remove trailing '--verbose' arg (safer; your CLI may not support it)
    s = re.sub(r"(?m)^\\s*'--verbose'\\s*,\\s*$", "", s)
    s = re.sub(r"(?m)^\\s*\"--verbose\"\\s*,\\s*$", "", s)

    # also remove a dangling comma line if it became empty list element
    s = re.sub(r"(?m)^\\s*,\\s*$", "", s)

    RUNNER.write_text(s, encoding="utf-8")
    print("PATCH_RUNNER_OK")

def patch_factory():
    s = FACTORY.read_text(encoding="utf-8", errors="replace")

    # A) remove early TRACE SUMMARY placed right after args parse (keep only end summary)
    # If there are multiple, remove those that appear BEFORE "bridge = RunnerBridge"
    idx_bridge = s.find("bridge = RunnerBridge")
    if idx_bridge != -1:
        pre = s[:idx_bridge]
        post = s[idx_bridge:]
        pre = re.sub(r"(?m)^\\s*logging\\.info\\(\\s*\\'\\[TRACE\\]\\s+SUMMARY.*?\\)\\s*$\\n?", "", pre)
        # Remove any early GA FINISHED logs BEFORE bridge init (these are wrong)
        pre = re.sub(r"(?m)^\\s*logging\\.info\\(\\s*[\\'\\\"]GA FINISHED[\\'\\\"]\\s*\\)\\s*$\\n?", "", pre)
        s = pre + post

    # B) ensure counters exist in main (you already have them, but keep safe)
    if "logging.info('[TRACE] ENTER_MAIN" not in s:
        # best-effort: do nothing; not required for correctness
        pass

    # C) ensure we actually count eval calls/fails in the population loop
    # Insert "_trace_eval_calls += 1" right before "rep = call_eval_once(..."
    if "_trace_eval_calls += 1" not in s:
        s = re.sub(
            r"(?m)^(\\s*)rep\\s*=\\s*call_eval_once\\(",
            r"\\1_trace_eval_calls += 1\\n\\1rep = call_eval_once(",
            s,
            count=1
        )

    # Insert "_trace_eval_fail += 1" inside except block before logging.error
    if "_trace_eval_fail += 1" not in s:
        s = re.sub(
            r"(?m)^(\\s*)except\\s+Exception\\s+as\\s+e\\s*:\\s*\\n(\\s*)logging\\.error\\(",
            r"\\1except Exception as e:\\n\\2_trace_eval_fail += 1\\n\\2logging.error(",
            s,
            count=1
        )

    # D) ensure END summary right before the LAST GA FINISHED
    # Add summary if missing near the end (only once)
    if "[TRACE] SUMMARY eval_calls" not in s:
        s = re.sub(
            r"(?m)^(\\s*)logging\\.info\\(\\s*[\\'\\\"]GA FINISHED[\\'\\\"]\\s*\\)\\s*$",
            r"\\1logging.info('[TRACE] SUMMARY eval_calls=%s eval_fail=%s', _trace_eval_calls, _trace_eval_fail)\\n\\1logging.info('GA FINISHED')",
            s,
            count=1
        )
    else:
        # if summary exists but earlier, keep one at end too: ensure last GA FINISHED has summary right above it
        # (cheap approach: do nothing if already present anywhere)
        pass

    # E) Make bridge selection prefer eval_once (your wrapper currently doesn't include it in factory_ga.py)
    # Patch call_eval_once to check eval_once first if present.
    s = re.sub(
        r"for\\s+name\\s+in\\s+\\(\\s*\\\"run_backtest\\\"\\s*,\\s*\\\"run\\\"\\s*,\\s*\\\"__call__\\\"\\s*\\)",
        r'for name in ("eval_once", "run_backtest", "run", "__call__")',
        s,
        count=1
    )

    FACTORY.write_text(s, encoding="utf-8")
    print("PATCH_FACTORY_OK")

if __name__ == "__main__":
    patch_runner()
    patch_factory()