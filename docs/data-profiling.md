# Dataset profiling and automatic schema detection

## Supported input formats

CSV, XLSX, XLS, JSON, JSONL and Parquet. CSV parsing tries UTF-8 with BOM, UTF-8, CP1252 and Latin-1 and sniffs common comma/semicolon/tab/pipe delimiters. Excel currently reads the first worksheet. JSON supports records, tabular JSON and JSON Lines; `.jsonl` files are read explicitly as newline-delimited records.

## Profiling outputs

For every column the profiler returns:

- original name and a normalised name;
- original pandas dtype and inferred type (`datetime`, `numeric`, `categorical`, `text`, or `boolean`);
- missing count and percentage;
- unique count and percentage;
- numeric/date parse success percentages;
- representative values and a constant-column flag.

Dataset-level outputs include memory footprint, duplicate rows, missing cells, a heuristic 0–100 quality score, numeric summary statistics (quartiles, IQR outlier counts and skewness), top categorical values, date range and observed-interval coverage, and a small trend preview.

## Semantic role inference

Date and target candidates are ranked using both column names and parseable values. Common date hints include date, time, timestamp, arrival and period. Common numeric measure hints include price, modal price, close, sales, revenue, amount, value, cost, rate, demand and quantity. Grouping dimensions may include state, district, market, mandi, commodity, product, category, region, city, store and symbol.

Column-name heuristics are not a semantic guarantee. A column named `value` might be an ID; a `date` column might use an unexpected calendar; a price may be quoted per kg, quintal, tonne or another unit. If automatic date inference is uncertain, the UI still allows manual selection of any source column; the forecast service then validates whether the selected values can be parsed. The user should validate every selection.

## Generic vs domain-specific datasets

MandiCast is no longer hard-coded to one Indian mandi CSV schema. A generic dataset can be profiled when it has arbitrary column names and tabular values. The forecasting engine then operates on the user's selected date, numeric target and optional group columns.

For AGMARKNET-like data, an initial recommendation commonly maps:

- `arrival_date` → time field;
- `modal_price` → target;
- `state`, `district`, `market`, `commodity` → series dimensions.

If multiple varieties or duplicate observations share the same group/date key, the generic forecasting engine currently uses a mean target aggregation. For production mandi analysis, choose an aggregation consistent with data semantics (for example, arrivals-weighted modal price where valid arrivals are available). The current generic forecaster does not silently infer this business rule.

## Data-quality score

The score is a heuristic quality indicator that subtracts weighted missingness, duplicate percentage and a penalty for columns with at least 30% missingness. It is not a statistical data-quality certification. Review the detailed warnings and column profile rather than relying on the score alone.
