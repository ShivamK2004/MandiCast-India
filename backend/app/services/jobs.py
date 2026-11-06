from __future__ import annotations

import json
from pathlib import Path

from app.core.config import ARTIFACT_DIR
from app.db.database import SessionLocal
from app.db.models import Dataset, Job
from app.services.forecasting import run_forecast


def _set_job(job_id: str, **values) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        for key, value in values.items():
            if key == "result":
                job.result_json = json.dumps(value, allow_nan=False)
            else:
                setattr(job, key, value)
        db.commit()


def execute_forecast_job(job_id: str, dataset_id: str, config: dict) -> None:
    with SessionLocal() as db:
        dataset = db.get(Dataset, dataset_id)
        if not dataset:
            _set_job(job_id, status="failed", stage="Dataset missing", error="The uploaded dataset no longer exists.")
            return
        input_path = dataset.stored_path

    job_output = ARTIFACT_DIR / dataset_id / job_id
    _set_job(job_id, status="running", progress=2, stage="Loading selected dataset", error=None)

    def report(progress: int, stage: str) -> None:
        _set_job(job_id, progress=progress, stage=stage)

    try:
        result = run_forecast(
            input_path, job_output, progress=report, run_id=job_id, dataset_id=dataset_id, **config
        )
        result["output_directory"] = str(job_output)
        _set_job(job_id, status="completed", progress=100, stage="Completed", result=result)
    except Exception as exc:  # surfaced to the workspace as an actionable job error
        _set_job(job_id, status="failed", stage="Forecast failed", error=f"{type(exc).__name__}: {exc}")
