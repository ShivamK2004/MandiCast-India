from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import ARTIFACT_DIR, MAX_UPLOAD_MB, UPLOAD_DIR
from app.db.database import get_db
from app.schemas import ForecastRequest
from app.services.catalog import create_dataset, create_job, dataset_payload, get_dataset, job_payload, list_datasets
from app.services.ingestion import SUPPORTED_EXTENSIONS, json_safe, read_dataset
from app.services.jobs import execute_forecast_job
from app.services.profiling import profile_dataset
from app.db.models import Job

router = APIRouter()


def _require_dataset(db: Session, dataset_id: str):
    item = get_dataset(db, dataset_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return item


@router.get("/health")
def health():
    return {"status": "ok", "service": "MandiCast API", "version": "1.0.0"}


@router.get("/dashboard/overview")
def dashboard_overview(db: Session = Depends(get_db)):
    datasets = list_datasets(db)
    total_rows = sum(item.row_count for item in datasets)
    total_columns = sum(item.column_count for item in datasets)
    return {
        "datasets": len(datasets),
        "total_rows": total_rows,
        "total_columns": total_columns,
        "latest_upload": datasets[0].created_at.isoformat() if datasets and datasets[0].created_at else None,
        "recent_datasets": [dataset_payload(item) for item in datasets[:5]],
    }


@router.post("/datasets/upload", status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    original_name = Path(file.filename or "dataset").name
    extension = Path(original_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Upload CSV, XLSX, XLS, JSON, JSONL, or Parquet files.")
    dataset_id = str(uuid.uuid4())
    destination_dir = UPLOAD_DIR / dataset_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"source{extension}"
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_MB} MB upload limit.")
                output.write(chunk)
        frame = read_dataset(destination)
        profile = profile_dataset(frame, original_name)
        item = create_dataset(
            db,
            filename=original_name,
            stored_path=str(destination),
            file_type=extension.lstrip("."),
            size_bytes=size,
            profile=profile,
        )
        return dataset_payload(item)
    except HTTPException:
        shutil.rmtree(destination_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(destination_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Could not inspect this dataset: {exc}") from exc
    finally:
        await file.close()


@router.post("/datasets/demo", status_code=status.HTTP_201_CREATED)
def load_demo_dataset(db: Session = Depends(get_db)):
    demo_path = Path(__file__).resolve().parents[2] / "demo_data" / "india_commodity_demo.csv"
    if not demo_path.exists():
        raise HTTPException(status_code=404, detail="Demo dataset is missing from this installation.")
    frame = read_dataset(demo_path)
    profile = profile_dataset(frame, "india_commodity_demo.csv (synthetic demo)")
    destination_dir = UPLOAD_DIR / str(uuid.uuid4())
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / "source.csv"
    shutil.copy2(demo_path, destination)
    item = create_dataset(
        db, filename="india_commodity_demo.csv (synthetic)", stored_path=str(destination),
        file_type="csv", size_bytes=destination.stat().st_size, profile=profile,
    )
    return dataset_payload(item)


@router.get("/datasets")
def get_datasets(db: Session = Depends(get_db)):
    return [dataset_payload(item) for item in list_datasets(db)]


@router.get("/datasets/{dataset_id}")
def get_dataset_detail(dataset_id: str, db: Session = Depends(get_db)):
    return dataset_payload(_require_dataset(db, dataset_id))


@router.get("/datasets/{dataset_id}/preview")
def dataset_preview(dataset_id: str, limit: int = 25, db: Session = Depends(get_db)):
    item = _require_dataset(db, dataset_id)
    frame = read_dataset(item.stored_path).head(max(1, min(limit, 100)))
    records = [
        {str(key): json_safe(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    return {"columns": list(frame.columns), "rows": records, "total_rows": item.row_count}


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)):
    item = _require_dataset(db, dataset_id)
    storage_path = Path(item.stored_path).parent
    artifact_path = ARTIFACT_DIR / dataset_id
    db.delete(item)
    db.commit()
    shutil.rmtree(storage_path, ignore_errors=True)
    shutil.rmtree(artifact_path, ignore_errors=True)
    return {"deleted": True, "id": dataset_id}


@router.post("/datasets/{dataset_id}/forecast", status_code=status.HTTP_202_ACCEPTED)
def create_forecast(
    dataset_id: str,
    request: ForecastRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    dataset = _require_dataset(db, dataset_id)
    profile = json.loads(dataset.profile_json)
    columns = {item["name"] for item in profile["column_profiles"]}
    requested = {request.target_column, request.date_column, *request.group_columns}
    missing = requested - columns
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown selected columns: {', '.join(sorted(missing))}")
    if request.target_column == request.date_column:
        raise HTTPException(status_code=422, detail="Target and date columns must be different.")
    config = request.model_dump()
    job = create_job(db, dataset_id, config)
    background_tasks.add_task(execute_forecast_job, job.id, dataset_id, config)
    return job_payload(job)


@router.get("/jobs")
def get_jobs(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(Job).order_by(Job.created_at.desc()).limit(max(1, min(limit, 100))).all()
    return [job_payload(row) for row in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job_payload(job)


@router.get("/jobs/{job_id}/artifacts/{filename}")
def download_job_artifact(job_id: str, filename: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    allowed = {
        "model.pt", "test_predictions.csv", "forecasts.csv", "training_history.csv",
        "series_metrics.csv", "group_metrics.csv", "result.json", "run_manifest.json",
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    artifact_path = ARTIFACT_DIR / job.dataset_id / job.id / filename
    if not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact is not available yet.")
    return FileResponse(artifact_path, filename=filename)
