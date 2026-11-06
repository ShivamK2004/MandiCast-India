# Data dictionary

MandiCast profiles the uploaded file dynamically. It does not require the following exact columns. This dictionary describes a common AGMARKNET-style market-price file and clarifies how to use its fields.

| Field | Typical meaning | Typical role | Notes |
|---|---|---|---|
| `arrival_date` | Date of market observation | Date/time | Verify the source's date format and time zone. |
| `state` | Indian state | Group dimension | Use as a grouping field when comparing states. |
| `district` | District | Group dimension | Check spelling and naming consistency. |
| `market` | APMC/mandi market | Group dimension | Market names may need normalisation. |
| `commodity` | Commodity name | Group dimension | Do not combine different commodities without a clear unit/business definition. |
| `variety` | Commodity variety | Optional grouping dimension | Aggregation across varieties is a modelling choice. |
| `min_price` | Reported minimum price | Numeric measure | Check unit and missing-value conventions. |
| `max_price` | Reported maximum price | Numeric measure | Check for invalid ranges where min exceeds max. |
| `modal_price` | Reported modal price | Common forecast target | This is the most frequently traded/reported price field in typical mandi data. |
| `arrivals` | Reported arrivals/quantity | Numeric measure or covariate | Verify its unit and whether it is consistently reported. |
| `unit` | Price/quantity unit | Grouping or validation dimension | Do not compare price levels across different units without conversion. |

## Internal metadata database

The default SQLite/PostgreSQL database stores platform metadata only:

- `datasets`: dataset UUID, original filename, storage path, format, file size, row/column counts, profile JSON, creation time;
- `jobs`: job UUID, dataset reference, job kind/status/progress, configuration, JSON result/error, timestamps.

Uploaded source files and forecast artifacts are stored in the configured storage directory (or Docker volume), not in database BLOB columns. The SQL templates in `sql/analytics_queries.sql` assume the source CSV has been separately loaded into an analytical table named `mandi_prices`.
