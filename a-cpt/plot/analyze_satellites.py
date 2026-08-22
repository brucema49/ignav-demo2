"""Correct satellite/quality analysis. Cols(0-idx): 0=week,1=sow,2-4=xyz,5=Q,6=Qins,7=ns."""
import numpy as np

rows = []
with open('a-cpt/output/rtdtcgps-navsys33-tc4.rslt') as f:
    for ln in f:
        if ln.startswith('%') or not ln.strip():
            continue
        p = ln.split()
        try:
            sow = float(p[1]); Q=int(float(p[5])); qins=int(float(p[6])); ns=int(float(p[7]))
        except (ValueError, IndexError):
            continue
        if 358850 <= sow <= 359010:
            rows.append((sow, Q, qins, ns))
rows.sort()

print("SOW   | Q@upd  | ns@q8 | ns all | n11")
for s0 in range(358850, 359010, 5):
    seg = [r for r in rows if s0 <= r[0] < s0+5]
    if not seg: continue
    upd = [r for r in seg if r[2]==8]
    n11 = sum(1 for r in seg if r[2]==11)
    ns_all = [r[3] for r in seg]
    nsall = f"{min(ns_all)}/{max(ns_all)}"
    Qset = {r[1] for r in upd} if upd else set()
    nsu = f"{min(r[3] for r in upd):2d}/{max(r[3] for r in upd):2d}" if upd else "  "
    print(f"{s0:6d}| Q@upd={sorted(Qset)} |  {nsu}  | {nsall:>5} | {n11:2d}")

# Within default window what Q values occur at integer seconds?
print("\n== default window Q occurrence (col5) ==")
qcnt={}
for s0 in range(359000,359100,10):
    seg=[r for r in rows if s0<=r[0]<s0+10]
    from collections import Counter
    c=Counter(r[1] for r in seg)
    qcnt[s0]=c
    print(f"SOW {s0}: Q={dict(c)}  ns(all min/max)={min(r[3] for r in seg)}/{max(r[3] for r in seg)}")