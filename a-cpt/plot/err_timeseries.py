#!/usr/bin/env python3
"""Compare per-integer-second ENU errors of two ignav rslt files vs truth over full span."""
import sys
import numpy as np

sys.path.insert(0, '/home/mxl/workplace/ignav-debug/a-cpt/plot')
from error_rtdtc import (read_ref_csv, read_eval_file, match_ref_to_eval_interp,
                         calculate_enu_errors, integer_second_mask)

TRUTH = '/home/mxl/workplace/gipylib/data/truth.csv'
FILES = {
    'gps+bds-tc4': '/home/mxl/workplace/ignav-debug/a-cpt/output/rtdtcgps-navsys33-tc4.rslt',
    'gpsonly-tc4': '/home/mxl/workplace/ignav-debug/a-cpt/output/rtktc-gpsonly.rslt',
}

ref = read_ref_csv(TRUTH)

for name, fn in FILES.items():
    ev = read_eval_file(fn, pos_type='xyz')
    rm, al = match_ref_to_eval_interp(ref, ev)
    res = calculate_enu_errors(rm, al)
    ts = np.asarray(res['gps_seconds'])
    mask = integer_second_mask(ts)
    e = res['e_error'][mask]; n = res['n_error'][mask]; u = res['u_error'][mask]
    q = np.asarray(res['qins'])[mask]
    ts = ts[mask]
    print(f"\n===== {name}: {mask.sum()} integer-sec pts =====")
    print("win_start   n   E-mean  N-mean  U-mean   H-rms   Q8  Q11")
    for w0 in np.arange(357460, 359900, 60):
        m = (ts >= w0) & (ts < w0 + 60)
        if m.sum() == 0:
            continue
        h = np.sqrt(e[m]**2 + n[m]**2)
        print(f"{w0:9.0f} {m.sum():4d} {e[m].mean():7.3f} {n[m].mean():7.3f} {u[m].mean():7.3f} "
              f"{np.sqrt((h**2).mean()):7.3f} {(q[m]==8).sum():4d} {(q[m]==11).sum():4d}")
