import io, re, sys

PATH = sys.argv[1]
src = io.open(PATH, "r", encoding="utf-8").read().splitlines(True)
orig = "".join(src)

# 1) remove any existing debug_signals add_argument lines anywhere
out = []
removed = 0
for line in src:
    if 'parser.add_argument("--debug_signals"' in line or "parser.add_argument('--debug_signals'" in line:
        removed += 1
        continue
    out.append(line)

src = out

# 2) find main() block
main_start = None
for i, line in enumerate(src):
    if re.match(r'^\s*def\s+main\s*\(', line):
        main_start = i
        break
if main_start is None:
    print("FIX: main() not found; no changes")
    sys.exit(0)

base_indent = re.match(r'^(\s*)', src[main_start]).group(1)
base_len = len(base_indent)

# main end = next top-level def/class with indent <= base
main_end = len(src)
for j in range(main_start+1, len(src)):
    if re.match(r'^\s*(def|class)\s+\w+\s*\(', src[j]) and len(re.match(r'^(\s*)', src[j]).group(1)) <= base_len:
        main_end = j
        break

main_block = src[main_start:main_end]

# 3) find parser creation inside main: parser = argparse.ArgumentParser(...)
insert_at = None
insert_indent = None

for k, line in enumerate(main_block):
    if re.search(r'^\s*parser\s*=\s*argparse\.ArgumentParser\s*\(', line):
        insert_at = k + 1
        insert_indent = re.match(r'^(\s*)', line).group(1)
        break

if insert_at is None:
    # fallback: first "parser =" line
    for k, line in enumerate(main_block):
        if re.search(r'^\s*parser\s*=', line):
            insert_at = k + 1
            insert_indent = re.match(r'^(\s*)', line).group(1)
            break

if insert_at is None:
    print("FIX: parser creation not found in main(); no changes")
    sys.exit(0)

# ensure not duplicated (we removed globally above, so safe)
ins = insert_indent + 'parser.add_argument("--debug_signals", action="store_true", help="Print entry filter pass statistics (diagnostic)")\n'

main_block[insert_at:insert_at] = [ins]
new_src = src[:main_start] + main_block + src[main_end:]

new_text = "".join(new_src)
if new_text == orig:
    print("FIX: no changes")
else:
    io.open(PATH, "w", encoding="utf-8", newline="").write(new_text)
    print(f"FIX: applied (removed={removed}, inserted=1)")
