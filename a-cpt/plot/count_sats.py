#!/usr/bin/env python3
"""Count GPS/BDS satellites per epoch in RINEX 3 obs file for a time window."""
import sys
from datetime import datetime, timedelta

fn = sys.argv[1] if len(sys.argv) > 1 else 'a-cpt/cpt0870.19o'
start = float(sys.argv[2]) if len(sys.argv) > 2 else 358850.0
end = float(sys.argv[3]) if len(sys.argv) > 3 else 359100.0

GPS_WK = 2046
GPS_EPOCH = datetime(1980, 1, 6)

def tow_of(yy, mo, dd, hh, mi, ss):
    dt = datetime(yy if yy > 1980 else 2000 + yy, mo, dd) - GPS_EPOCH
    return (dt.days % 7) * 86400 + hh * 3600 + mi * 60 + ss

cur = None
rows = []
with open(fn) as f:
    for line in f:
        if line.startswith('END OF HEADER'):
            continue
        if line.startswith('>'):
            if cur:
                rows.append(cur)
            p = line.split()
            try:
                yy, mo, dd, hh, mi = int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5])
                ss = float(p[6])
            except (ValueError, IndexError):
                cur = None
                continue
            tow = tow_of(yy, mo, dd, hh, mi, ss)
            cur = {'tow': tow, 'G': [], 'C': []}
        elif cur is not None and line.strip():
            sysid = line[0]
            if sysid == 'G' or sysid == 'C':
                prn = line[1:3]
                cur[sysid].append(prn)
if cur:
    rows.append(cur)

print(f"total epochs: {len(rows)}, tow range {rows[0]['tow']:.0f}-{rows[-1]['tow']:.0f}")
# print window stats every 10 s
last_t = None
for r in rows:
    if not (start <= r['tow'] <= end):
        continue
    t = r['tow']
    if last_t is None or t - last_t >= 10.0:
        last_t = t
        print(f"SOW {t:.0f}: GPS={len(r['G'])} {' '.join(r['G'])} | BDS={len(r['C'])} {' '.join(r['C'])}")
