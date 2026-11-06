from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db.database import Base, get_db
from app.main import app


def test_upload_endpoint_profiles_custom_dataset(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(routes, "UPLOAD_DIR", tmp_path / "uploads")
    app.dependency_overrides[get_db] = override_get_db
    csv_content = "date,market,commodity,modal_price,arrivals\n" + "\n".join(
        f"2025-01-{day:02d},{'Ahmedabad' if day % 2 else 'Surat'},Wheat,{2400 + day},120"
        for day in range(1, 26)
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/datasets/upload",
                files={"file": ("mandi_prices.csv", csv_content, "text/csv")},
            )
        assert response.status_code == 201
        payload = response.json()
        assert payload["row_count"] == 25
        assert payload["profile"]["date_column"] == "date"
        assert payload["profile"]["target_column"] == "modal_price"
        assert "market" in payload["profile"]["group_columns"]
        assert len(payload["profile"]["column_profiles"]) == 5
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_preview_serializes_excel_datetime_values(tmp_path, monkeypatch):
    import pandas as pd

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(routes, "UPLOAD_DIR", tmp_path / "uploads")
    app.dependency_overrides[get_db] = override_get_db
    source = tmp_path / "dates.xlsx"
    pd.DataFrame({
        "date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
        "price": [100.0, 101.5],
    }).to_excel(source, index=False)

    try:
        with TestClient(app) as client:
            with source.open("rb") as handle:
                uploaded = client.post(
                    "/api/v1/datasets/upload",
                    files={"file": ("dates.xlsx", handle, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            assert uploaded.status_code == 201
            dataset_id = uploaded.json()["id"]
            preview = client.get(f"/api/v1/datasets/{dataset_id}/preview")
            assert preview.status_code == 200
            assert preview.json()["rows"][0]["date"].startswith("2025-01-01")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_forecast_job_binds_run_and_dataset_ids_to_artifact_path(tmp_path, monkeypatch):
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.models import Dataset, Job
    from app.services import jobs as job_service

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(job_service, "SessionLocal", testing_session)
    monkeypatch.setattr(job_service, "ARTIFACT_DIR", tmp_path / "artifacts")

    captured = {}

    def fake_run_forecast(input_path, output_dir, *, progress, **config):
        captured.update(config)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "run_manifest.json").write_text('{"experiment_id":"job-123"}', encoding="utf-8")
        return {"experiment_id": config["run_id"], "dataset_id": config["dataset_id"], "artifacts": ["run_manifest.json"]}

    monkeypatch.setattr(job_service, "run_forecast", fake_run_forecast)
    source = tmp_path / "source.csv"
    source.write_text("date,price\n2025-01-01,1\n", encoding="utf-8")
    db = testing_session()
    db.add(Dataset(
        id="dataset-123", filename="source.csv", stored_path=str(source), file_type="csv",
        size_bytes=source.stat().st_size, row_count=1, column_count=2, profile_json="{}",
    ))
    db.add(Job(
        id="job-123", dataset_id="dataset-123", kind="forecast", status="queued", progress=0,
        stage="Queued", config_json=json.dumps({"target_column": "price"}),
    ))
    db.commit()
    db.close()

    try:
        job_service.execute_forecast_job("job-123", "dataset-123", {"target_column": "price"})
        db = testing_session()
        job = db.get(Job, "job-123")
        result = json.loads(job.result_json)
        expected_dir = tmp_path / "artifacts" / "dataset-123" / "job-123"
        assert job.status == "completed"
        assert captured["run_id"] == "job-123"
        assert captured["dataset_id"] == "dataset-123"
        assert Path(result["output_directory"]) == expected_dir
        assert (expected_dir / "run_manifest.json").is_file()
        db.close()
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_job_artifact_download_returns_file_contents(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.models import Dataset, Job

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setattr(routes, "ARTIFACT_DIR", artifact_dir)
    app.dependency_overrides[get_db] = override_get_db
    db = testing_session()
    db.add(Dataset(
        id="dataset-123", filename="source.csv", stored_path="source.csv", file_type="csv",
        size_bytes=0, row_count=0, column_count=0, profile_json="{}",
    ))
    db.add(Job(
        id="job-123", dataset_id="dataset-123", kind="forecast", status="completed",
        progress=100, stage="Completed", config_json="{}",
    ))
    db.commit()
    db.close()

    expected_content = "run_id,step,forecast_price\njob-123,1,2500.5\n"
    output_dir = artifact_dir / "dataset-123" / "job-123"
    output_dir.mkdir(parents=True)
    (output_dir / "forecasts.csv").write_bytes(expected_content.encode("utf-8"))

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/jobs/job-123/artifacts/forecasts.csv")
        assert response.status_code == 200
        assert response.content == expected_content.encode("utf-8")
        assert "attachment" in response.headers["content-disposition"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
