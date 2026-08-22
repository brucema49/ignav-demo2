"""Locate divergence onset of candidate B (navsys33-tc4) across time, filtering propagation-only epochs."""
import importlib.util
import numpy as np

spec = importlib.util.spec_from_file_location("E", "a-cpt/plot/error_rtdtc.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

truth = E.read_ref_csv(str(E.TRUTH_FILE))
evalu = E.read_eval_file('a-cpt/output/rtdtcgps-navsys33-tc4.rslt',
                         pos_type='xyz', ref_datetime=truth['datetime'], qins_col=6)

# evaluate a wide window: 357900 - 359100
ew, es, ed, ex = 2046, 357900, 2046, 359100
rt = E.filter_data_by_gps_time(truth, ew, es, ed, ex)
ev = E.filter_data_by_gps_time(evalu, ew, es, ed, ex)
ev = E.downsample_to_freq(ev, 100.0)
refm, align = E.match_ref_to_eval_interp(rt, ev)
res = E.calculate_enu_errors(refm, align)

n = np.asarray(res['n_error'])
e = np.asarray(res['e_error'])
u = np.asarray(res['u_error'])
gs = np.asarray(res['gps_seconds'])
q = np.asarray(res['qins'])

print("== North/East error overview win 357900-359100 ==")
print(f"total points={len(n)}")

# Print every 10s segment with Qins-update count and mean N (propagation Qins=2 only to see drift)
print("\nSOW   | meanN(all) | meanN(q2) | nQins8 | nQins11 | max|N|")
prev_bad = None
for s0 in range(357900, 359100, 10):
    m = (gs >= s0) & (gs < s0 + 10)
    if not m.any():
        continue
    m2 = m & (q == 2)
    meanN_all = np.mean(n[m])
    meanN_q2 = np.mean(n[m2]) if m2.any() else float('nan')
    n8 = int(np.count_nonzero(q[m] == 8))
    n11 = int(np.count_nonzero(q[m] == 11))
    mx = np.max(np.abs(n[m]))
    # classify bad: |meanN| > 1.0
    bad = abs(meanN_all) > 1.0
    print(f"{s0:6d}| {meanN_all:7.2f}   | {meanN_q2:7.2f} |  {n8:5d}  |  {n11:5d}   | {mx:6.2f} {'<==BAD' if bad else ''}")

# where does |N| first stay above 1.0 for a sustained period?
idxs = np.where(np.abs(n) > 1.0)[0]
if len(idxs):
    print(f"\nfirst point |N|>1.0 at SOW={gs[idxs[0]]:.3f} (N={n[idxs[0]]:.2f})")
# find earliest 10s window where sustained
for s0 in range(357900, 359100, 10):
    m = (gs >= s0) & (gs < s0 + 10)
    q2 = m & (q == 2)
    if q2.any() and abs(np.mean(n[q2])) > 1.0:
        print(f"first 10s window (propagation-only) mean|N|>1.0 at SOW {s0} (meanN={np.mean(n[q2]):.2f})")
        break