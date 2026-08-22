#!/usr/bin/env python3
"""Extract Qins/ns distribution per 60s window for rslt files, and compare positions."""
import sys
import numpy as np

FILES = {
    'gps+bds-tc4': '/home/mxl/workplace/ignav-debug/a-cpt/output/rtdtcgps-navsys33-tc4.rslt',
    'gpsonly-tc4': '/home/mxl/workplace/ignav-debug/a-cpt/output/rtktc-gpsonly.rslt',
}

for name, fn in FILES.items():
    rows = []
    with open(fn) as f:
        for ln in f:
            if ln.startswith('%') or not ln.strip():
                continue
            p = ln.split()
            if len(p) < 25:
                continue
            try:
                w, s = float(p[0]), float(p[1])
                q = int(p[5]); qins = int(p[6]); ns = int(p[7])
            except ValueError:
                continue
            rows.append((s, q, qins, ns))
    a = np.array(rows)
    print(f"\n===== {name} =====")
    # Qins distribution overall
    vals, cnts = np.unique(a[:, 2], return_counts=True)
    print("Qins distribution:", dict(zip(vals.astype(int), cnts.astype(int))))
    print("win_start   n  Qins8 Qins11 Qins9 Qins1 Qins2  ns-mean(min/max at Q8)")
    for w0 in np.arange(357460, 359900, 60):
        m = (a[:, 0] >= w0) & (a[:, 0] < w0 + 60)
        if m.sum() == 0:
            continue
        w_ = a[m]
        q8 = (w_[:, 2] == 8).sum(); q11 = (w_[:, 2] == 11).sum()
        q9 = (w_[:, 2] == 9).sum(); q1 = (w_[:, 2] == 1).sum(); q2 = (w_[:, 2] == 2).sum()
        m8 = w_[:, 2] == 8
        if m8.sum():
            nsmean = w_[m8, 3].mean(); nsmin = int(w_[m8, 3].min()); nsmax = int(w_[m8, 3].max())
        else:
            nsmean = nsmin = nsmax = 0
        print(f"{w0:9.0f} {m.sum():4d} {q8:5d} {q11:5d} {q9:5d} {q1:5d} {q2:5d}  {nsmean:5.1f}({nsmin}/{nsmax})")
