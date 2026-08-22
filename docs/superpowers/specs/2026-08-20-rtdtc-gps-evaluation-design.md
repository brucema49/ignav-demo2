# RTDTC-GPS Evaluation Design

## Goal

Run `a-cpt/cpt-rtdtc_gps.conf` through the debug configuration and produce a reproducible evaluation of ignav RTDTC-GPS against truth, ignav RTKTC, and gipylib RTDTC-GPS+BDS.

## Design

`a-cpt/plot/error_rtdtc.py` is the primary evaluator. It reads ECEF ignav outputs and LLH gipylib output, aligns each solution to the truth trajectory by GPS week/seconds, interpolates truth to solution epochs, converts residuals to ENU, and writes per-dataset statistics plus a combined summary. It reports all epochs for diagnostics but computes the primary RMSE on `Qins=3` GNSS-update epochs; `Qins=2` is retained as propagation-only context.

`a-cpt/plot/tra_neu.py` reads the same four datasets and produces one ENU trajectory comparison. Both scripts use command-line paths and time windows, validate missing/empty inputs, and default to the files in this workspace.

## Outputs

- `a-cpt/output/rtdtcgps.rslt`: baseline navapp result.
- `a-cpt/plot/error-*.png`: E/N/U residual plots for each solution.
- `a-cpt/plot/tra-neu-rtdtcgps.png`: ENU trajectory comparison.
- `a-cpt/plot/evaluation-summary.csv`: machine-readable E/N/U/horizontal/3D statistics and Qins counts.
- `a-cpt/plot/evaluation-summary.json`: same statistics plus run metadata.

## Accuracy diagnosis

The summary records update rate and Qins counts so a large error can be classified as missing GNSS updates, initialization/propagation drift, or noisy updates. Recommended adjustments are isolated in candidate configuration copies: first verify time/coordinate/lever-arm/IMU-unit consistency; then test satellite/model settings; then measurement weights; then INS initial uncertainties and process noise. Each candidate changes one parameter family and is evaluated with the same window and truth alignment.

## Verification

Unit tests cover GPS-time parsing, Qins selection, ECEF-to-ENU residuals, and summary serialization. A smoke run executes both plotting scripts against the generated baseline and checks all declared output files.
