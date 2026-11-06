# Architecture and design decisions

## System boundaries

MandiCast is organised as a separate browser application, an API application, and a model/data service layer. The browser is not allowed to read local server files directly; it uploads a file through the API. The API stores the source under a generated ID and persists dataset metadata separately from the data file. Model runs are represented as jobs and write their own artifact directory.

## Components

### Frontend

- React + TypeScript single-page application.
- Vite for local development and production bundling.
- Tailwind CSS 4 via the official Vite integration; the bespoke design system is maintained in `src/styles.css`.
- Recharts for time-series and forecast visualisation.
- A typed fetch client in `src/api/client.ts` isolates transport code from UI pages.
- The client sends requests to the same-origin `/api/v1` path. In development, Vite proxies `/api` to `http://127.0.0.1:8000` by default; `MANDICAST_API_TARGET` overrides this backend target and is read when Vite starts.
- The workspace connection indicator is based on the API health endpoint. When health is unavailable, the UI retries periodically; failure of a separate dashboard data request does not by itself mark the API offline.

### Backend

- FastAPI exposes versioned REST endpoints under `/api/v1`.
- Pydantic v2 validates forecast configuration.
- SQLAlchemy stores dataset/job metadata in SQLite for local runs or PostgreSQL when `DATABASE_URL` points to Postgres.
- Pandas-based ingestion and profiling are isolated from route code.
- PyTorch model training is isolated in `services/forecasting.py`.
- FastAPI background tasks update job status and results. This is intentionally simple for local/portfolio use.

### Storage

- Uploaded source: `MANDICAST_STORAGE_DIR/uploads/{dataset_uuid}/source.ext`.
- Model run artifacts: `MANDICAST_STORAGE_DIR/artifacts/{dataset_uuid}/{job_uuid}/`.
- Metadata: SQLAlchemy database. Source bytes are not put into a database blob.

## Upload lifecycle

1. Browser sends multipart upload.
2. API checks extension and upload size.
3. A generated UUID directory is created; the original filename is stored as metadata only.
4. The ingestion layer reads the file and normalises duplicate/blank headers.
5. The profiler infers data types and candidate semantic roles.
6. API stores dataset metadata/profile and returns the profile to the browser.
7. Browser displays warnings, field mapping and a small data preview.

## Forecast lifecycle

1. User selects a target, date field and optional grouping columns.
2. API validates that the requested columns exist and creates a queued job record.
3. A background task loads the stored source and validates selected values.
4. Records are parsed and sorted; repeated dates within each group are aggregated with a mean. This is a transparent generic default, not a universal business rule.
5. A global date cutoff defines chronological train (70%), validation (15%) and test (15%) partitions.
6. Price/target changes are standardised using training changes only.
7. The attention-pooled LSTM is trained using train sequences; validation loss chooses the checkpoint and early stopping.
8. Test metrics and predictions are generated for LSTM, last-value, and moving-average forecasts.
9. Future next-step forecasts are generated recursively and the job record is marked completed.
10. UI polls the job endpoint and renders outputs.

## Why a residual model

The model predicts the difference from the prior observation and adds the predicted change back to the previous value. This is useful as a baseline architecture for persistent price series and can be easier to share across commodities with different absolute scales. It is not guaranteed to outperform a last-value forecast; the benchmark is part of the product, not an optional chart.

## Extension points

- Replace in-process BackgroundTasks with Celery/RQ + Redis for durable distributed execution.
- Replace local file storage with S3-compatible object storage.
- Add authentication, tenant ownership and row-level access before multi-user deployment.
- Add domain-specific validators and aggregation choices for non-mandi datasets.
- Add seasonal naive, ARIMA/SARIMAX, gradient boosting and probabilistic forecast intervals.
- Add dataset versioning, data lineage, experiment registry and model promotion workflows.
