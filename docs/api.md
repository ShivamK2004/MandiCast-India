# API usage

Start the API from `backend/` with `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`. Open `http://127.0.0.1:8000/docs` for the generated OpenAPI schema. The health endpoint is `GET /api/v1/health`; a healthy response reports `"status":"ok"` and `"service":"MandiCast API"`.

The local frontend proxies `/api` to `http://127.0.0.1:8000` by default. To run the API on a different port, set `MANDICAST_API_TARGET` in the frontend terminal before starting or restarting Vite. For example, with the API on port 8010 in Windows PowerShell:

```powershell
$env:MANDICAST_API_TARGET = "http://127.0.0.1:8010"
npm run dev
```

You can check the complete frontend-to-API route at `http://localhost:5173/api/v1/health`.

## Upload and profile

```powershell
curl.exe -F "file=@prices.csv" http://127.0.0.1:8000/api/v1/datasets/upload
```

The response contains `id` and a `profile` object with rows, columns, detected date/target/group candidates, date range, column profiles, numeric summaries, warnings and recommendations.

## Launch a forecast

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/datasets/DATASET_ID/forecast `
  -H "Content-Type: application/json" `
  -d '{
    "target_column":"modal_price",
    "date_column":"arrival_date",
    "group_columns":["state","market","commodity"],
    "horizon":7,
    "lookback":21,
    "epochs":25,
    "batch_size":128,
    "hidden_size":48
  }'
```

The response returns a job ID. Poll `GET /api/v1/jobs/JOB_ID` until its status is `completed` or `failed`.

## Error handling

- 413: upload exceeds `MAX_UPLOAD_MB`.
- 415: unsupported file extension.
- 422: file could not be parsed, fields are invalid, or not enough usable history exists.
- 404: dataset/job ID does not exist.

Detailed model artifacts are saved in the backend storage volume under `artifacts/{dataset_id}/{job_id}/`.


## Download a run-specific artifact

```text
GET /api/v1/jobs/{job_id}/artifacts/{filename}
```

Allowed files include `forecasts.csv`, `test_predictions.csv`, `training_history.csv`, `series_metrics.csv`, `group_metrics.csv`, `result.json`, `run_manifest.json`, and `model.pt`. Downloads are resolved beneath that exact job's `{dataset_id}/{job_id}` artifact directory. Every generated CSV includes the run ID, dataset ID, and source dataset SHA-256. `run_manifest.json` records checksums for the other artifacts so exports can be checked against the selected experiment.
