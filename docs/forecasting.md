# Forecasting methodology

## Problem definition

The selected numeric target is forecast separately for every combination of selected grouping fields. With no grouping fields, all records form one series. Repeated timestamps within one series are aggregated using the mean target value. For a panel containing multiple commodities, stores or markets, keep the relevant dimensions selected; otherwise unlike entities can be averaged together.

The forecast horizon is measured in future observations/steps. The engine does not assert that a step means a day, week or month. This distinction matters for market data with holidays, missing market sessions and irregular observations.

## Sequence construction

For each series, the target change is defined as `delta[t] = y[t] - y[t-1]`. The LSTM receives the preceding `lookback` observed changes and predicts the next standardised change. The predicted change is added to the last observed target level to obtain a level forecast.

## Leakage prevention

- Global timestamp cutoffs: 70% train, 15% validation, 15% test.
- Each sequence is assigned to a split by its target timestamp.
- Target-change mean and standard deviation are fitted separately for each series using only its training-period changes. This keeps the shared model from being dominated by large-price series.
- Validation loss is used to select the model checkpoint and trigger early stopping.
- Test observations are not used for model fitting or feature scaling.

This is a global temporal split across the selected panel. It tests future-time generalisation for the observed groups; it is not a cold-start evaluation for unseen markets or commodities.

## Metrics

- MAE: mean absolute error in target units.
- RMSE: root mean squared error in target units.
- MAPE: mean absolute percentage error where actual values are nonzero.
- sMAPE: symmetric percentage error.
- R²: coefficient of determination when test target variance is nonzero. It is reported both pooled over all test observations and averaged/median across individual series. Pooled R² can be inflated by between-series level differences; do not interpret it as typical per-series accuracy.
- WAPE: total absolute error divided by total absolute actual values; useful when individual actual values approach zero.

Every run reports two transparent alternatives:

1. Persistence / naive: next value equals the last observed value.
2. Moving average: next value equals the mean of the preceding seven observations.

The test metrics are only meaningful when the source data, target units and split are valid. Never make the model appear successful by hiding a baseline that wins. Macro metrics give each series equal weight; pooled metrics give each test observation equal weight. Group rollups aggregate observations within each value of selected grouping dimensions, such as commodity or market. Absolute errors across different measurement units are not directly comparable. If a unit column contains multiple values, the engine requires that it be selected as a series dimension or the dataset be filtered to one unit. If no unit column is present, unit comparability is marked unknown rather than assumed.

## Prediction intervals

The engine computes absolute one-step validation residuals after loading the best validation-loss checkpoint. It uses an empirical 90th-percentile residual radius per series when sufficient validation residuals are available, otherwise it falls back to the global validation residual radius. Forecast bands are widened by the square root of the forecast step. These bands are indicative only: multi-step dependence, non-stationarity and distribution shift mean they do not guarantee 90% future coverage. The result reports observed coverage on the held-out test split for diagnostic purposes; test observations do not calibrate the intervals.

## Run and artifact identity

Every job writes to its own dataset/job directory and records a run ID, dataset ID, SHA-256 of the source dataset, full configuration and checksums for result artifacts in `run_manifest.json`. Generated CSVs also contain the run ID. The UI links to the selected job ID when downloading artifacts so metrics from different runs are not silently mixed.

## Known limitations

- One numeric target per run; no future exogenous covariates are used.
- No automatic daily calendar regularisation or missing-date imputation.
- No unit conversion or cross-commodity unit reconciliation.
- Recursive multi-step LSTM forecasts can drift as predicted changes are fed back.
- The model is an experimental portfolio implementation, not a production trading/procurement recommendation.


## Model architecture

The forecasting model is a shared residual LSTM with a learned temporal-attention pooling layer. The LSTM encodes the lookback sequence of standardized target changes. Attention scores weight the hidden states across the full window; the final hidden state and attention context are concatenated and passed through a LayerNorm/MLP regression head. The predicted residual is de-standardized using that series' training-only scaler and added to the latest observed value.

This is a univariate target-history model shared across selected series. The group columns partition the data into independent series; they are not currently embedded as learned categorical features. External drivers such as weather, arrivals, fuel prices or holidays are not included unless a future model extension explicitly adds exogenous inputs.
