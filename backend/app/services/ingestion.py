from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".parquet"}


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                sample = handle.read(65536)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                separator = dialect.delimiter
            except csv.Error:
                separator = ","
            return pd.read_csv(path, encoding=encoding, sep=separator, low_memory=False)
        except (UnicodeDecodeError, pd.errors.ParserError, csv.Error) as exc:
            last_error = exc
    raise ValueError(f"Could not parse CSV file: {last_error}")


def read_dataset(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{suffix}'. Supported: CSV, XLSX, XLS, JSON, JSONL, Parquet.")
    if suffix == ".csv":
        frame = _read_csv(file_path)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(file_path)
    elif suffix == ".jsonl":
        frame = pd.read_json(file_path, lines=True)
    elif suffix in {".json", ".jsonl"}:
        # Accept ordinary JSON records/tables and newline-delimited JSON.
        if suffix == ".jsonl":
            frame = pd.read_json(file_path, lines=True)
        else:
            try:
                frame = pd.read_json(file_path, orient="records")
            except ValueError:
                try:
                    frame = pd.read_json(file_path)
                except ValueError:
                    frame = pd.read_json(file_path, lines=True)
    else:
        frame = pd.read_parquet(file_path)
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("The uploaded file contains no tabular records.")
    if len(frame.columns) == 0:
        raise ValueError("The uploaded file has no columns.")
    frame.columns = [str(column).strip() or f"column_{index + 1}" for index, column in enumerate(frame.columns)]
    # Resolve duplicate names deterministically so every field can be selected by name.
    seen: dict[str, int] = {}
    names: list[str] = []
    for name in frame.columns:
        count = seen.get(name, 0)
        seen[name] = count + 1
        names.append(name if count == 0 else f"{name}_{count + 1}")
    frame.columns = names
    return frame


def clean_numeric(series: pd.Series) -> pd.Series:
    """Parse numeric values and convert non-finite values to missing values."""
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce")
    else:
        text = series.astype("string").str.strip()
        # Handle common Indian and international currency labels, grouping
        # separators, percentage values, Unicode minus signs and accounting negatives.
        text = text.str.replace(r"(?i)(?:^|\s)(?:inr|rs\.?)\s*", "", regex=True)
        text = text.str.replace(r"(?i)\s*(?:inr|rs\.?)$", "", regex=True)
        text = text.str.replace(r"[₹$€£,%\s]", "", regex=True)
        text = text.str.replace("−", "-", regex=False)
        text = text.str.replace(r"^(NA|N/A|null|none|-)$", "", regex=True, case=False)
        text = text.str.replace(r"^\((.*?)\)$", r"-\1", regex=True)
        numeric = pd.to_numeric(text, errors="coerce")
    return numeric.replace([np.inf, -np.inf], np.nan)


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if pd.isna(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
