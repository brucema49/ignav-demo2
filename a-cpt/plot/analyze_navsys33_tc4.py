"""Analyze candidate B (navsys33-tc4) North divergence in default window 359000-359100."""
import importlib.util
import sys
import numpy as np

spec = importlib.util.spec_from_file_location("E", "a-cpt/plot/error_rtdtc.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

truth = E.read_ref_csv(str(E.TRUTH_FILE))
evalu = E.read_eval_file('a-cpt/output/rtdtcgps-navsys33-tc4.rslt',
                         pos_type='xyz', ref_datetime=truth['datetime'], qins_col=6)

ew, es, ed, ex = 2046, 359000, 2046, 359100
rt = E.filter_data_by_gps_time(truth, ew, es, ed, ex)
ev = E.filter_data_by_gps_time(evalu, ew, es, ed, ex)
ev = E.downsample_to_freq(ev, 100.0)
refm, align = E.match_ref_to_eval_interp(rt, ev)
res = E.calculate_enu_errors(refm, align)

n = res['n_error']
gs = res['gps_seconds']
q = np.asarray(res['qins'])
hor = res['hor_error']

print("== North error evolution in window 359000-359100 (100Hz) ==")
print(f"points={len(n)}  max|N|={np.max(np.abs(n)):.3f} mean|N|={np.mean(np.abs(n)):.3f} max|H|={np.max(np.abs(hor)):.3f}")

for s0 in range(359000, 359100, 5):
    s1 = s0 + 5
    m = (gs >= s0) & (gs < s1)
    if not m.any():
        continue
    nn = n[m]
    seg = np.max(np.abs(nn))
    idx = np.argmax(np.abs(nn))
    ih = np.argmax(np.abs(hor[m]))
    marker = ' <<<DIVERGE' if seg > 3.0 else ''
    print(f"SOW {s0}-{s1}: max|N|={seg:6.2f} at {gs[m][idx]:.1f}  mean|N|={np.mean(np.abs(nn)):6.2f}  max|H|={np.max(np.abs(hor[m])):6.2f}{marker}")

# first exceed thresholds
for thr in (0.5, 1.0, 2.0):
    idx = np.where(np.abs(n) >= thr)[0]
    if len(idx):
        i = idx[0]
        print(f"first |N|>={thr}: SOW={gs[i]:.3f} N={n[i]:.3f} E={res['e_error'][i]:.3f} U={res['u_error'][i]:.3f} qins={q[i]}")

# where does Qins change - look at qins==8 vs 11 vs 2 distribution per segment
print("\n== Qins distribution per 10s segment (candidate B) ==")
for s0 in range(359000, 359100, 10):
    m = (gs >= s0) & (gs < s0 + 10)
    if not m.any():
        continue
    cnt = {k: int(np.count_nonzero(q[m] == k)) for k in (-1, 0, 2, 8, 11)}
    idx = np.argmax(np.abs(n[m]))
    print(f"SOW {s0}-{s0+10}: {cnt}  max|N|={np.max(np.abs(n[m])):6.2f} at {gs[m][idx]:.1f} q={q[m][idx]}")