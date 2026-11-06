from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = Path(os.getenv("MANDICAST_STORAGE_DIR", BASE_DIR / "storage")).resolve()
UPLOAD_DIR = STORAGE_DIR / "uploads"
ARTIFACT_DIR = STORAGE_DIR / "artifacts"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(STORAGE_DIR / 'mandicast.db').as_posix()}")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
API_PREFIX = "/api/v1"

for directory in (STORAGE_DIR, UPLOAD_DIR, ARTIFACT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
