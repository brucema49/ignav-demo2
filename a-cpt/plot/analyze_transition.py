"""Zoom into transition 358880-359010 where N error becomes permanent, correlate with updates."""
import importlib.util
import numpy as np

spec = importlib.util.spec_from_file_location("E", "a-cpt/plot/error_rtdtc.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

truth = E.read_ref_csv(str(E.TRUTH_FILE))
evalu = E.read_eval_file('a-cpt/output/rtdtcgps-navsys33-tc4.rslt',
                         pos_type='xyz', ref_datetime=truth['datetime'], qins_col=6)

ew, es, ed, ex = 2046, 358880, 2046, 359010
rt = E.filter_data_by_gps_time(truth, ew, es, ed, ex)
ev = E.filter_data_by_gps_time(evalu, ew, es, ed, ex)
refm, align = E.match_ref_to_eval_interp(rt, ev)
res = E.calculate_enu_errors(refm, align)

n = np.asarray(res['n_error'])
e = np.asarray(res['e_error'])
u = np.asarray(res['u_error'])
gs = np.asarray(res['gps_seconds'])
q = np.asarray(res['qins'])

# find exact point where |N| first exceeds 2.0 AND stays above ~1.5 for next 2s (permanent)
thr = 2.0
idxs = np.where(np.abs(n) >= thr)[0]
for i in idxs:
    # check sustained: mean |N| over next 100 samples (1s)
    if i + 100 < len(n):
        window = np.abs(n[i:i + 100])
        if np.mean(window) > 1.5 and np.max(np.abs(n[i:i+100])) > 2.0:
            print(f"PERMANENT onset candidate: SOW={gs[i]:.3f} N={n[i]:.2f} E={e[i]:.2f} U={u[i]:.2f} qins={q[i]}")
            break

# segment every 2s showing N at Qins==8 update points (the actual correction epochs)
print("\nSOW   | N@updates(q8)      | n11 | note")
prev_n = None
for s0 in range(358880, 359010, 2):
    m = (gs >= s0) & (gs < s0 + 2)
    if not m.any():
        continue
    upd = m & np.isin(q, [8])
    n11 = int(np.count_nonzero(q[m] == 11))
    if upd.any():
        nu = n[upd]
        nn = f"N@q8 mean={np.mean(nu):6.2f} min={np.min(nu):6.2f} max={np.max(nu):6.2f}"
    else:
        nn = "  (no q8 update)"
    # mean N over propagation only (tells if drifting within the 2s)
    pr = m & (q == 2)
    mp = np.mean(n[pr]) if pr.any() else float('nan')
    print(f"{s0:6d}| {nn}  | {n11:2d} | propMeanN={mp:6.2f}")

# overall: what's the ratio of q8 updates in this window vs near-zero? and their N values
upd = q == 8
print(f"\nq8 update points in 358880-359010: {int(upd.sum())}, meanN at q8 = {np.mean(n[upd]):.2f}")
print(f"q8 update N: {np.round(n[upd],2)}")