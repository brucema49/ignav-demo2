#!/usr/bin/env python3
"""Per-60s-window ENU errors of gipylib rtdtc-gps-bds.rslt (llh) vs truth."""
import sys
import numpy as np

sys.path.insert(0, '/home/mxl/workplace/ignav-debug/a-cpt/plot')
from error_rtdtc import read_ref_csv, match_ref_to_eval_interp, calculate_enu_errors, integer_second_mask

TRUTH = '/home/mxl/workplace/gipylib/data/truth.csv'
GIPY = '/home/mxl/workplace/gipylib/data/output/rtdtc-gps-bds.rslt'


def read_gipylib(fn):
    rows = []
    with open(fn) as f:
        for ln in f:
            if ln.startswith('%') or not ln.strip():
                continue
            p = ln.split()
            if len(p) < 8:
                continue
            try:
                tow = float(p[1])
                lat, lon, h = float(p[2]), float(p[3]), float(p[4])
                q, qins, ns = int(p[5]), int(p[6]), int(p[7])
            except ValueError:
                continue
            rows.append((tow, lat, lon, h, q, qins, ns))
    return rows


def llh2xyz(lat_deg, lon_deg, h):
    from math import radians, sin, cos, sqrt
    WGS84_A, WGS84_F = 6378137.0, 1.0 / 298.257223563
    e2 = WGS84_F * (2 - WGS84_F)
    lat, lon = radians(lat_deg), radians(lon_deg)
    N = WGS84_A / sqrt(1 - e2 * sin(lat) ** 2)
    return np.array([(N + h) * cos(lat) * cos(lon),
                     (N + h) * cos(lat) * sin(lon),
                     (N * (1 - e2) + h) * sin(lat)])


from error_rtdtc import read_eval_file

ev = read_eval_file(GIPY, pos_type='llh')
tow = np.asarray(ev['gps_seconds'])
vals, cnts = np.unique(ev['qins'], return_counts=True)
print("Qins distribution:", dict(zip(vals.astype(int), cnts.astype(int))))

ref = read_ref_csv(TRUTH)
rm, al = match_ref_to_eval_interp(ref, ev)
res = calculate_enu_errors(rm, al)
ts = np.asarray(res['gps_seconds'])
mask = integer_second_mask(ts)
e = res['e_error'][mask]; n = res['n_error'][mask]; u = res['u_error'][mask]
q = np.asarray(res['qins'])[mask] if 'qins' in res else None
ts = ts[mask]
h = np.sqrt(e ** 2 + n ** 2)
print(f"\n===== gipylib rtdtc-gps-bds: {mask.sum()} integer-sec pts =====")
print(f"overall: H-rms={np.sqrt((h**2).mean()):.3f} 3D-rms={np.sqrt((e**2+n**2+u**2).mean()):.3f}")
print("win_start   n   E-mean  N-mean  U-mean   H-rms")
for w0 in np.arange(357460, 359900, 60):
    m = (ts >= w0) & (ts < w0 + 60)
    if m.sum() == 0:
        continue
    print(f"{w0:9.0f} {m.sum():4d} {e[m].mean():7.3f} {n[m].mean():7.3f} {u[m].mean():7.3f} {np.sqrt((h[m]**2).mean()):7.3f}")
