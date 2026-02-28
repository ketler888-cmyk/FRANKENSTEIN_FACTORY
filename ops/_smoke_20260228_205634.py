import sys
mods = ["numpy","pandas","pyarrow","numba","requests"]
bad=[]
for m in mods:
    try:
        __import__(m)
    except Exception as e:
        bad.append((m,str(e)))
print("PY:", sys.executable)
print("OK_IMPORTS:", [m for m in mods if m not in [x[0] for x in bad]])
print("BAD_IMPORTS:", bad)