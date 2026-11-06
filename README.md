# MandiCast India 1.0

**A full-stack commodity intelligence and time-series forecasting workspace.** Upload a structured dataset, let the platform inspect its schema, review data quality, map the time-series fields, and launch a reproducible LSTM experiment with baseline comparisons.

> **Data transparency:** The included India mandi dataset is synthetic demo data. It is intended only to demonstrate ingestion, profiling, charts, and modelling. It is not official AGMARKNET history and must not be used for market, procurement, investment, or policy decisions. Upload verified source data before interpreting results.

## Evaluation and reproducibility

- Corrected the misleading benchmark summary: the best benchmark is selected only from the two baseline models, while the best overall model is reported separately.
- Added `lstm_mae_improvement_vs_best_benchmark_pct` alongside the naive-baseline comparison.
- Added macro-averaged per-series metrics, per-dimension commodity/market rollups, and `group_metrics.csv`.
- Added WAPE to the evaluation metrics and explicit pooled-vs-macro R² diagnostics, including negative per-series R² counts.
- Added validation-residual calibrated indicative 90% forecast/test bands. They are labelled as approximate and do not claim guaranteed coverage.
- Added a run manifest with run ID, dataset ID, dataset SHA-256, configuration and SHA-256 checksums for each generated artifact. All exported CSVs carry the experiment run ID.
- Fixed selected-run display so a queued/running/failed selected job cannot fall back to another completed run's result.
- Detects a common unit column and blocks accidentally merging multiple units unless the unit is selected as a series dimension.
- Validation loss now uses the same Huber objective used for training and early stopping; both training and validation loss are returned for the diagnostics chart.
- Added a training-vs-validation loss chart and a per-series metrics download to Model Runs.

## Product scope

- **Modern frontend:** React 19 + TypeScript + Vite 8 + Tailwind CSS 4 + Recharts. No Streamlit.
- **API backend:** FastAPI with typed request validation, OpenAPI docs, upload endpoints, dataset catalog, and background forecast jobs.
- **Dataset intelligence:** CSV, XLSX, XLS, JSON, JSONL, and Parquet ingestion; delimiter/encoding detection for CSV; duplicate-header normalisation; inferred data types; date parseability; numeric/categorical candidates; missingness; duplicate rows; column statistics, quartiles, IQR outliers, skewness and observed time gaps; dataset quality score; likely date, target, and grouping fields.
- **Forecasting:** Global residual LSTM with temporal attention in PyTorch; chronological 70/15/15 time split; per-series train-only target-change scaling; next-observation-step forecasting; configurable horizon/lookback/epochs.
- **Honest benchmarks:** Compare test-set LSTM predictions with last-observation persistence and seven-observation moving-average predictions. The UI reports LSTM improvement against the naive baseline separately from LSTM performance against the best baseline.
- **Evaluation:** pooled test metrics, macro-averaged per-series metrics, per-series benchmark comparisons, commodity/market dimension rollups, WAPE, pooled and per-series R² diagnostics, and separate best-benchmark/best-model selection.
- **Uncertainty:** validation-residual empirical intervals with square-root horizon widening; these are informative approximate bands, not guaranteed probabilistic coverage.
- **Reproducibility:** each job has a unique run ID, dataset hash, result metadata and a checksum manifest; each CSV export carries its run ID.
- **Artifacts:** model checkpoint, test predictions and interval bands, forecast CSV, training history, per-series metrics CSV, dimension-level metrics CSV, `result.json`, and `run_manifest.json`, all saved per job.
- **Storage:** SQLite by default for local development; PostgreSQL supported in Docker Compose. Uploaded files and model artifacts remain on the local storage volume.
- **Quality and engineering:** backend tests, typed frontend, Dockerfiles, Compose, API documentation, data guide, architecture notes, and deployment guidance.

## Architecture

```text
                  ┌──────────────────────────────┐
                  │ React + TypeScript Web App   │
                  │ Upload · Profile · Forecast  │
                  └──────────────┬───────────────┘
                                 │ REST / JSON / multipart
                  ┌──────────────▼───────────────┐
                  │ FastAPI application         │
                  │ API routes · validation     │
                  └───────┬───────────────┬──────┘
                          │               │
              ┌───────────▼────┐  ┌───────▼────────────────┐
              │ Dataset store  │  │ Background job runner │
              │ SQLite / PG    │  │ PyTorch residual LSTM  │
              └────────────────┘  └──────────┬─────────────┘
                                             │
                             ┌───────────────▼──────────────┐
                             │ Uploads + model artifacts   │
                             │ CSV / XLSX / JSONL / Parquet│
                             └──────────────────────────────┘
```

See the [historical 2.4 release notes](docs/release-notes-2.4.md), [architecture](docs/architecture.md), [data profiling](docs/data-profiling.md), [data dictionary](docs/data-dictionary.md), [forecasting methodology](docs/forecasting.md), [API guide](docs/api.md), [deployment guide](docs/deployment.md), and [security notes](SECURITY.md). SQL practice templates are in `sql/analytics_queries.sql`.

## Requirements

- Python **3.13 recommended** (3.11+ supported by the project configuration).
- Node.js **22.12+** and npm **10.8+** for the Vite 8 toolchain.
- Windows 10/11, macOS, or Linux.
- PyTorch CPU is sufficient for the demo. CUDA can be used when a compatible PyTorch/CUDA installation is available.

## Run locally on Windows PowerShell

Open two terminals in the extracted project.

### Terminal 1 — backend

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/generate_demo_dataset.py --days 120
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks environment activation, run this once in that terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Backend endpoints:

- API: http://127.0.0.1:8000
- Interactive OpenAPI docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/v1/health

### Terminal 2 — frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

The Vite development server proxies `/api` requests to the backend on port 8000 by default. The API client uses this same-origin proxy, so do not set a separate API URL in the frontend.

If you run the backend on another port, set the proxy target in the frontend terminal **before** starting Vite. For example, for a backend on port 8010:

```powershell
$env:MANDICAST_API_TARGET = "http://127.0.0.1:8010"
npm run dev
```

If Vite is already running, stop it with `Ctrl+C` and restart it after setting the variable; Vite reads this setting at startup. Verify the connection by opening http://localhost:5173/api/v1/health. A healthy response contains `"status":"ok"` and `"service":"MandiCast API"`. The app is not a static mock: uploads, profile results, database metadata, job status, and forecasting results come from the FastAPI service.

## First run

1. Start the backend and frontend.
2. Open the web app.
3. Select **Try demo data** to load the clearly labelled synthetic Indian mandi dataset, or choose **Import dataset** to upload your own file.
4. Open **Datasets** and inspect the inferred date, target, grouping fields, quality score, warnings, and preview.
5. Open **Forecast lab**. Verify/change the target and date mapping; choose grouping dimensions such as state, district, market, and commodity.
6. Set horizon/lookback and run the experiment.
7. Follow progress under **Model runs**. Review LSTM vs. naive and moving-average metrics and inspect the forecast preview. Downloaded artifacts are served by the API for the selected run.

## Dataset intelligence: what it detects

The profiler is schema-aware but source-agnostic. It does not assume a specific set of column names. It inspects names, parsed values, data types, uniqueness, missingness, and numeric/date parse rates.

Typical AGMARKNET columns it recognises include `arrival_date`, `state`, `district`, `market`, `commodity`, `min_price`, `max_price`, `modal_price`, and `arrivals`. For generic datasets it can recommend other date-like columns (`date`, `timestamp`, `period`) and numeric measures (`close`, `sales`, `revenue`, `amount`, `value`, `price`, `quantity`, etc.).

A detected `unit`, `units`, `price_unit`, `currency_unit`, or `measurement_unit` column is retained as measurement metadata. If more than one unit is present, include that field in the series dimensions or filter to one unit before forecasting. The initial mapping is a recommendation. Before training, verify:

- the correct date/time column and date interpretation;
- that the selected target is truly a numeric measure, not an identifier or encoded category;
- that target units are consistent within each series;
- that each selected group combination has enough chronological observations;
- the meaning of duplicate time keys and whether mean aggregation is appropriate.

See [Data Profiling Guide](docs/data-profiling.md) for details and limitations.

## Supported file formats

| Format | Support | Notes |
|---|---|---|
| CSV | Yes | Sniffs common delimiters and tries common encodings. |
| XLSX | Yes | Reads the first worksheet; requires `openpyxl`. |
| XLS | Yes | Reads the first worksheet; requires `xlrd`. |
| JSON / JSONL | Yes | Record-oriented/tabular JSON and newline-delimited JSON. |
| Parquet | Yes | Requires `pyarrow`. |

Current upload limit: 100 MB by default (`MAX_UPLOAD_MB` environment variable).

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/dashboard/overview` | Workspace totals and recent datasets |
| POST | `/api/v1/datasets/upload` | Upload and automatically profile a dataset |
| POST | `/api/v1/datasets/demo` | Register the bundled synthetic demo |
| GET | `/api/v1/datasets` | List datasets |
| GET | `/api/v1/datasets/{id}` | Dataset profile |
| GET | `/api/v1/datasets/{id}/preview` | Preview records |
| DELETE | `/api/v1/datasets/{id}` | Delete dataset and uploaded source |
| POST | `/api/v1/datasets/{id}/forecast` | Queue a forecast job |
| GET | `/api/v1/jobs` | List recent jobs |
| GET | `/api/v1/jobs/{id}` | Get job status and result |

FastAPI generates `/docs` and `/redoc` automatically.

## Run tests

From `backend/` with the virtual environment active:

```powershell
pytest -q
```

The frontend can be type-checked and production-built from `frontend/`:

```powershell
npm run build
```

The build may report a bundle-size advisory for the main JavaScript chunk; this does not fail the build.

## Docker Compose (PostgreSQL + API + React/Nginx)

From the project root, copy `.env.example` to `.env`, change `POSTGRES_PASSWORD`, and run:

```powershell
docker compose up --build
```

Open http://localhost:8080. PostgreSQL stores dataset/job metadata; the named storage volume stores uploaded data and model artifacts. Docker is optional for local development.

## Project structure

```text
MandiCast-India-Next/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI endpoints
│   │   ├── core/            # Environment/configuration
│   │   ├── db/              # SQLAlchemy models and DB session
│   │   └── services/        # Ingestion, profiling, forecasting, jobs
│   ├── demo_data/           # Explicitly synthetic demo dataset
│   ├── scripts/             # Demo-data generator
│   ├── tests/               # Backend tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/api/             # Typed API client
│   ├── src/components/      # Shared UI components (extend here)
│   ├── src/pages/           # Page modules (extend here)
│   ├── App.tsx              # Workspace shell and pages
│   ├── styles.css           # Product UI system
│   └── Dockerfile
├── docs/
├── sql/                     # Reusable analytics query templates
├── .github/workflows/       # CI checks
├── docker-compose.yml
├── SECURITY.md
└── README.md
```

## Important limitations and next production steps

This is a local-first portfolio project with an end-to-end full-stack workflow. It is not yet a multi-tenant hosted SaaS product. Before public production deployment, add user authentication/authorization, per-user storage isolation, upload malware scanning, rate limiting, a persistent queue (Celery/RQ + Redis), object storage, audit logging, retention controls, and observability. The included FastAPI `BackgroundTasks` runner is appropriate for a local demo and one-process deployment, not high-volume production scheduling.

The profiler cannot infer the business meaning of every arbitrary numeric column. It ranks candidates; the user must confirm the semantic mapping. The forecast engine supports one selected numeric target at a time. It predicts the next *observed step*, not necessarily the next calendar day. It does not automatically reconcile different units, impute missing dates, or forecast exogenous drivers.

For Indian market use, start with the Government of India's [AGMARKNET daily mandi price catalogue](https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi) and verify current access terms, units and metadata. Do not cite synthetic demo results as market findings.

## Current technology references

- [React version documentation](https://react.dev/versions)
- [Vite supported release lines](https://vite.dev/releases)
- [Tailwind CSS Vite integration](https://tailwindcss.com/docs/installation/using-vite)
- [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)
- [AGMARKNET catalogue on data.gov.in](https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi)
