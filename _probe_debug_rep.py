import sys, json

p = sys.argv[1]
j = json.load(open(p, "r", encoding="utf-8"))

def dig(obj, path=""):
    out = []
    if isinstance(obj, dict):
        for k,v in obj.items():
            np = f"{path}.{k}" if path else k
            if k in ("metrics","summary") and isinstance(v, dict):
                out.append((np, v))
            out.extend(dig(v, np))
    elif isinstance(obj, list):
        for i,v in enumerate(obj):
            out.extend(dig(v, f"{path}[{i}]"))
    return out

meta = j.get("_bridge_meta") or {}
print("REP=", p)
print("META.pair=", meta.get("pair"))
print("META.bars=", meta.get("bars"))

hits = dig(j)
print("FOUND metrics/summary blocks =", len(hits))
for i,(k,v) in enumerate(hits[:8], 1):
    print(f"--- HIT {i} @ {k}")
    for kk in ("pair","bars","trades","net_pnl","fees","max_dd","error","error_code"):
        if kk in v:
            print(" ", kk, "=", v.get(kk))

# Hard verdict if ANY hit has bars>10
ok = False
for _,v in hits:
    try:
        b = int(v.get("bars", 0))
        if b > 10:
            ok = True
            break
    except Exception:
        pass

if not ok:
    raise SystemExit("FAIL: Did not find any metrics block with bars>10 (still loading only 1 bar?)")

print("OK: At least one metrics block has bars>10")