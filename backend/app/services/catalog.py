from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Dataset, Job


def create_dataset(
    db: Session,
    *,
    filename: str,
    stored_path: str,
    file_type: str,
    size_bytes: int,
    profile: dict[str, Any],
) -> Dataset:
    item = Dataset(
        id=str(uuid.uuid4()),
        filename=filename,
        stored_path=stored_path,
        file_type=file_type,
        size_bytes=size_bytes,
        row_count=int(profile["rows"]),
        column_count=int(profile["columns_count"]),
        profile_json=json.dumps(profile),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def dataset_payload(item: Dataset) -> dict[str, Any]:
    return {
        "id": item.id,
        "filename": item.filename,
        "file_type": item.file_type,
        "size_bytes": item.size_bytes,
        "row_count": item.row_count,
        "column_count": item.column_count,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "profile": json.loads(item.profile_json),
    }


def get_dataset(db: Session, dataset_id: str) -> Dataset | None:
    return db.get(Dataset, dataset_id)


def list_datasets(db: Session) -> list[Dataset]:
    return list(db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all())


def create_job(db: Session, dataset_id: str, config: dict[str, Any]) -> Job:
    item = Job(
        id=str(uuid.uuid4()),
        dataset_id=dataset_id,
        kind="forecast",
        status="queued",
        progress=0,
        stage="Queued",
        config_json=json.dumps(config),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def job_payload(item: Job) -> dict[str, Any]:
    return {
        "id": item.id,
        "dataset_id": item.dataset_id,
        "kind": item.kind,
        "status": item.status,
        "progress": item.progress,
        "stage": item.stage,
        "config": json.loads(item.config_json),
        "result": json.loads(item.result_json) if item.result_json else None,
        "error": item.error,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
