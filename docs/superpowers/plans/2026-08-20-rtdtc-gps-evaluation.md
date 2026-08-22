# RTDTC-GPS Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and run a reproducible RTDTC-GPS baseline evaluation with four-way comparison and precision-diagnosis guidance.

**Architecture:** Keep navigation configuration and generated results unchanged except for the requested baseline run. Build the evaluator around shared parsing/alignment/statistics helpers in `error_rtdtc.py`; keep `tra_neu.py` as a focused trajectory renderer that imports those helpers only when practical.

**Tech Stack:** Python 3, NumPy, SciPy, Matplotlib, pytest, existing C++ `bin/navapp`.

---

### Task 1: Establish evaluator behavior with tests

**Files:**
- Create: `tests/test_rtdtc_evaluation.py`
- Modify: `a-cpt/plot/error_rtdtc.py`

- [ ] **Step 1: Write failing tests** for GPS-time conversion, `Qins=3` primary mask, ENU residual calculation, and CSV/JSON summary fields.
- [ ] **Step 2: Run `pytest -q tests/test_rtdtc_evaluation.py`** and confirm failure because the public helpers are not yet defined.
- [ ] **Step 3: Implement the smallest helpers and evaluator behavior needed by the tests.**
- [ ] **Step 4: Run the focused tests and then the complete test command.**

### Task 2: Implement four-way error evaluation and diagnostics

**Files:**
- Modify: `a-cpt/plot/error_rtdtc.py`

- [ ] **Step 1:** Add CLI arguments for eval path, time window, and output directory while preserving workspace defaults.
- [ ] **Step 2:** Parse truth, ECEF ignav, and LLH gipylib files with explicit column/Qins handling and clear missing/empty errors.
- [ ] **Step 3:** Align truth by interpolation, calculate ENU/E/N/U/horizontal/3D residuals, and emit all-epoch plus Qins=3 statistics.
- [ ] **Step 4:** Serialize summary CSV/JSON and include Qins counts, update rate, valid epochs, and candidate tuning recommendations.

### Task 3: Implement trajectory comparison

**Files:**
- Modify: `a-cpt/plot/tra_neu.py`

- [ ] **Step 1:** Add CLI-configurable input paths/window/output and robustly skip unavailable optional references.
- [ ] **Step 2:** Plot truth, ignav RTDTC, ignav RTKTC, and gipylib RTDTC in a common truth-origin ENU frame, marking Qins=3 updates.
- [ ] **Step 3:** Run a smoke test and verify the PNG is non-empty and the selected window is represented.

### Task 4: Run baseline and verify artifacts

**Files:**
- Existing: `a-cpt/cpt-rtdtc_gps.conf`, `.vscode/settings.json`
- Generated: `a-cpt/output/rtdtcgps.rslt`, `a-cpt/plot/*`

- [ ] **Step 1:** Run `./bin/navapp -s -o /home/mxl/workplace/ignav-debug/a-cpt/cpt-rtdtc_gps.conf -t 3 -m 52030` from the repository root and record exit status/output metadata.
- [ ] **Step 2:** Run `python3 a-cpt/plot/error_rtdtc.py` and `python3 a-cpt/plot/tra_neu.py`.
- [ ] **Step 3:** Inspect summary metrics and Qins distribution; classify accuracy problems before making any tuning change.
- [ ] **Step 4:** Create only evidence-based candidate config copies if a first adjustment is justified, and do not replace the baseline config.
