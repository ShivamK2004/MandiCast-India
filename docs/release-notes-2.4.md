# MandiCast India 2.4.0 — Release Notes

> Historical release notes for 2.4. The current project version is 1.0.0; this page records the 2.4 changes and validation at that release.

## Evaluation and interpretation

- Separates pooled test metrics from macro-averaged per-series metrics.
- Reports pooled, mean per-series, median per-series, and negative per-series R² diagnostics.
- Adds per-dimension test summaries for every selected grouping field (for example commodity, market, state, and district) in the API result and `group_metrics.csv`.
- Preserves the distinction between the best baseline (naive/moving average only) and the best overall model (including LSTM). Improvement against naive and best baseline is displayed separately.
- Detects common unit columns. Multiple units must be part of the series dimensions or excluded by filtering; absolute errors across different units are flagged as not directly comparable.

## Uncertainty and model training

- Adds indicative 90% forecast and test prediction bands calibrated from validation residuals only.
- Forecast intervals widen by the square root of the forecast step. This is explicitly documented as approximate; it does not guarantee 90% coverage. Held-out test coverage is reported as a diagnostic and is not used to calibrate interval widths.
- The selected checkpoint remains the best validation-Huber-loss checkpoint; the best epoch and validation loss are included in result metadata.
- Negative target values are preserved for generic series; a non-negative floor is applied only when every fitted target series is non-negative.

## Run identity and artifact integrity

- Every run has a unique experiment ID and source dataset SHA-256.
- Every exported CSV includes run ID, dataset ID, and dataset hash columns.
- Each run writes to its own dataset/job directory and emits `run_manifest.json` with the exact experiment configuration, evaluation summary, and SHA-256 checksums for output artifacts.
- API artifact downloads are restricted to the selected job's artifact directory.
- The Model Runs page now keeps a selected queued/running/failed job selected rather than displaying another job's last completed result.

## Validation performed

- Backend tests at the 2.4 release: 15 passed. The current backend suite contains 16 tests and passes.
- Python compilation: passed.
- End-to-end smoke run: passed on the bundled 4,320-row synthetic dataset; 36 series and 252 forecast rows were produced.
- Artifact run IDs and dataset hashes: checked in every generated CSV.
- Run manifest artifact SHA-256 checksums: all verified.
- Frontend type-check and Vite production build: passed in the current project environment.

## Data provenance

The bundled commodity CSV is synthetic demonstration data, not official AGMARKNET history. Forecasting performance on this dataset must not be presented as real-world Indian mandi forecast accuracy.
