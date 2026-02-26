import io, re, sys

PATH = sys.argv[1]
lines = io.open(PATH, "r", encoding="utf-8").read().splitlines(True)
orig = "".join(lines)

# -------- locate main() block --------
main_start = None
for i, ln in enumerate(lines):
    if re.match(r'^\s*def\s+main\s*\(', ln):
        main_start = i
        break
if main_start is None:
    print("FIX: main() not found")
    sys.exit(0)

base_indent = re.match(r'^(\s*)', lines[main_start]).group(1)
base_len = len(base_indent)

main_end = len(lines)
for j in range(main_start+1, len(lines)):
    if re.match(r'^\s*(def|class)\s+\w+', lines[j]) and len(re.match(r'^(\s*)', lines[j]).group(1)) <= base_len:
        main_end = j
        break

pre = lines[:main_start]
blk = lines[main_start:main_end]
post = lines[main_end:]

# -------- remove ANY existing debug_signals add_argument lines (any var) --------
removed = 0
new_blk = []
for ln in blk:
    if re.search(r'\.add_argument\(\s*[\'"]--debug_signals[\'"]', ln):
        removed += 1
        continue
    new_blk.append(ln)
blk = new_blk

# -------- find parser var name: X = argparse.ArgumentParser(...) --------
parser_var = None
parser_line_idx = None
for k, ln in enumerate(blk):
    m = re.search(r'^\s*(\w+)\s*=\s*argparse\.ArgumentParser\s*\(', ln)
    if m:
        parser_var = m.group(1)
        parser_line_idx = k
        break

if parser_var is None:
    print("FIX: argparse.ArgumentParser assignment not found inside main()")
    sys.exit(0)

indent = re.match(r'^(\s*)', blk[parser_line_idx]).group(1)

# insert debug_signals immediately after parser creation line
ins_flag = indent + f'{parser_var}.add_argument("--debug_signals", action="store_true", help="Print entry filter pass statistics (diagnostic)")\n'
blk[parser_line_idx+1:parser_line_idx+1] = [ins_flag]
inserted_flag = 1

# -------- ensure runner.debug_signals assignment AFTER runner creation --------
# Remove previous runner.debug_signals lines (to avoid duplicates / wrong placement)
tmp = []
removed_runner = 0
for ln in blk:
    if re.search(r'^\s*runner\.debug_signals\s*=', ln):
        removed_runner += 1
        continue
    tmp.append(ln)
blk = tmp

# Find runner construction "runner = BacktestRunnerV3(" and its closing ")"
runner_start = None
for k, ln in enumerate(blk):
    if re.match(r'^\s*runner\s*=\s*BacktestRunnerV3\s*\(', ln):
        runner_start = k
        break

inserted_runner = 0
if runner_start is not None:
    # walk forward until we hit a line that starts with the same indent and is just ")" or ends the call
    runner_indent = re.match(r'^(\s*)', blk[runner_start]).group(1)
    depth = 0
    end_idx = None
    for t in range(runner_start, len(blk)):
        # naive paren depth tracking
        depth += blk[t].count("(")
        depth -= blk[t].count(")")
        if depth <= 0 and t > runner_start:
            end_idx = t
            break
    if end_idx is None:
        end_idx = runner_start

    # insert AFTER the call block (end_idx+1)
    ins_runner = runner_indent + 'runner.debug_signals = bool(getattr(args, "debug_signals", False))\n'
    blk[end_idx+1:end_idx+1] = [ins_runner]
    inserted_runner = 1

new_text = "".join(pre + blk + post)

if new_text == orig:
    print("FIX: no changes")
else:
    io.open(PATH, "w", encoding="utf-8", newline="").write(new_text)
    print(f"FIX: applied (removed_flag_lines={removed}, inserted_flag={inserted_flag}, removed_runner_lines={removed_runner}, inserted_runner={inserted_runner}, parser_var={parser_var})")
