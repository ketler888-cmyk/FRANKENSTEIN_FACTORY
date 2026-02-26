from pathlib import Path

p = Path(r"C:\Users\user\Desktop\Франкинштэйн\factory_ga.py")
s = p.read_text(encoding="utf-8", errors="replace")

# Fix only in the header area to avoid touching legitimate '\n' in strings.
head = s[:4000]
tail = s[4000:]

if "\\n" in head:
    head2 = head.replace("\\r\\n", "\n").replace("\\n", "\n")
    if head2 != head:
        s = head2 + tail
        p.write_text(s, encoding="utf-8")
        print("REPAIRED_HEADER_NEWLINES")
    else:
        print("NO_CHANGE")
else:
    print("NO_LITERAL_NEWLINES_IN_HEADER")