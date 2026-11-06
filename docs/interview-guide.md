# Interview guide

## 30-second project explanation

MandiCast India is a full-stack commodity intelligence platform. It accepts structured datasets, automatically profiles their schema and data quality, recommends date/target/group columns, and exposes an interactive React workspace backed by FastAPI. Users can train a global PyTorch residual LSTM, evaluate it on chronological holdout data, and compare its performance with naive and moving-average baselines.

## What demonstrates data analyst skills?

- Data ingestion and schema understanding across multiple tabular formats.
- Missingness, duplicates, type profiling and data quality reporting.
- Exploratory statistics and time-series visualisation.
- Transparent model evaluation and communicating when a baseline wins.
- SQL/database fundamentals through persistent dataset and job metadata.

## What demonstrates software engineering?

- Typed frontend API boundary and reusable React components.
- REST API with Pydantic validation and OpenAPI documentation.
- Separation of routes, ingestion, profiling, modelling and persistence.
- Background job status tracking and artifact management.
- Automated tests, Dockerfiles and PostgreSQL deployment option.

## Questions to prepare for

1. Why use a chronological split instead of random train/test split?
2. What is target leakage, and how is scaling fitted only on training history?
3. Why compare an LSTM with persistence and moving-average baselines?
4. Why does the project forecast next observed step rather than blindly call it tomorrow?
5. Why can an automatic schema profiler recommend a wrong target?
6. How would you make background jobs durable at scale?
7. How would you add authentication, multi-tenancy and secure file isolation?
8. How would you handle different price units across commodities?

## Honest claims

Do not claim that the bundled synthetic dataset is official market data. Do not claim that LSTM outperforms a baseline unless the saved held-out metrics show it. Do not describe a next-observation forecast as a daily forecast unless the data has been explicitly regularised to a daily frequency.
