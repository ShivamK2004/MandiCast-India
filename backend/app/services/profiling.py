from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from app.services.ingestion import clean_numeric, json_safe

DATE_HINTS = ("date", "time", "timestamp", "day", "arrival", "period", "month")
TARGET_HINTS = (
    "modal_price", "modal price", "price", "close", "target", "sales", "revenue",
    "amount", "value", "cost", "rate", "demand", "quantity", "volume", "units",
    "profit", "yield", "production", "inventory", "temperature", "humidity",
    "consumption", "orders", "traffic", "load", "balance", "count",
)
ID_PARTS = {"id", "identifier", "code", "sno", "serial", "index", "unnamed"}
GROUP_HINTS = (
    "state", "district", "market", "mandi", "commodity", "product", "category",
    "region", "city", "store", "symbol", "ticker", "variety", "country",
    "province", "branch", "exchange", "supplier", "warehouse", "grade", "unit",
)


def _normalise_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _is_identifier_name(name: str) -> bool:
    """Avoid ranking common ID/code fields as predictive measures or dimensions."""
    parts = _normalise_name(name).split("_")
    return bool(set(parts) & ID_PARTS)


def _date_parse(series: pd.Series) -> tuple[pd.Series, float]:
    """Parse mixed date columns while preferring Indian day-first dates on ties.

    ISO year-first values are handled correctly by pandas under either setting;
    the alternate parse is used when it materially increases parse coverage.
    """
    non_null = series.dropna().head(5000)
    if non_null.empty:
        return pd.to_datetime(series, errors="coerce"), 0.0

    day_first = pd.to_datetime(
        non_null, errors="coerce", dayfirst=True, format="mixed"
    )
    month_first = pd.to_datetime(
        non_null, errors="coerce", dayfirst=False, format="mixed"
    )
    day_ratio = float(day_first.notna().mean())
    month_ratio = float(month_first.notna().mean())
    use_day_first = day_ratio >= month_ratio
    ratio = max(day_ratio, month_ratio)

    full = pd.to_datetime(
        series, errors="coerce", dayfirst=use_day_first, format="mixed"
    )
    return full, ratio


def _column_profile(name: str, series: pd.Series) -> dict[str, Any]:
    non_null = series.dropna()
    unique_count = int(series.nunique(dropna=True))
    missing_count = int(series.isna().sum())
    n = max(len(series), 1)
    normalized = _normalise_name(name)
    numeric = clean_numeric(series)
    numeric_ratio = float(numeric.notna().mean()) if len(series) else 0.0
    _, date_ratio = _date_parse(series) if not pd.api.types.is_numeric_dtype(series) else (None, 0.0)
    if any(hint in normalized for hint in DATE_HINTS) and date_ratio >= 0.4:
        inferred = "datetime"
    elif pd.api.types.is_bool_dtype(series):
        inferred = "boolean"
    elif pd.api.types.is_numeric_dtype(series) or numeric_ratio >= 0.90:
        inferred = "numeric"
    elif date_ratio >= 0.90:
        inferred = "datetime"
    else:
        inferred = "categorical" if unique_count <= min(1000, max(20, int(n * 0.5))) else "text"
    examples = [json_safe(v) for v in non_null.head(4).tolist()]
    return {
        "name": name,
        "normalized_name": normalized,
        "dtype": str(series.dtype),
        "inferred_type": inferred,
        "missing_count": missing_count,
        "missing_pct": round(missing_count / n * 100, 2),
        "unique_count": unique_count,
        "unique_pct": round(unique_count / n * 100, 2),
        "numeric_parse_pct": round(numeric_ratio * 100, 2),
        "date_parse_pct": round(date_ratio * 100, 2),
        "examples": examples,
        "is_constant": unique_count <= 1,
    }


def profile_dataset(frame: pd.DataFrame, filename: str = "dataset") -> dict[str, Any]:
    row_count, column_count = frame.shape
    columns = [_column_profile(str(name), frame[name]) for name in frame.columns]
    by_name = {item["name"]: item for item in columns}

    date_candidates = [c["name"] for c in columns if c["inferred_type"] == "datetime"]
    numeric_candidates = [c["name"] for c in columns if c["inferred_type"] == "numeric" and not _is_identifier_name(c["name"])]
    categorical_candidates = [
        c["name"] for c in columns
        if c["inferred_type"] in {"categorical", "text", "boolean"}
        and c["unique_count"] > 1
        and c["unique_count"] <= min(1000, max(50, int(row_count * 0.35)))
        and not _is_identifier_name(c["name"])
    ]

    def date_score(name: str) -> tuple[int, float]:
        normalized = by_name[name]["normalized_name"]
        hint = sum(2 for token in DATE_HINTS if token in normalized)
        return hint, by_name[name]["date_parse_pct"]

    def target_score(name: str) -> tuple[int, float, float]:
        normalized = by_name[name]["normalized_name"]
        hint = max((len(token) for token in TARGET_HINTS if token in normalized), default=0)
        numeric = clean_numeric(frame[name]).dropna()
        variance = float(numeric.std()) if len(numeric) > 1 else 0.0
        return hint, float(len(numeric) / max(row_count, 1)), variance

    date_column = max(date_candidates, key=date_score) if date_candidates else None
    target_column = max(numeric_candidates, key=target_score) if numeric_candidates else None
    group_columns = sorted(
        categorical_candidates,
        key=lambda name: (
            any(token in by_name[name]["normalized_name"] for token in GROUP_HINTS),
            -by_name[name]["unique_count"],
        ),
        reverse=True,
    )[:6]

    task_type = "time_series_forecasting" if date_column and target_column else "tabular_analytics"
    warnings: list[str] = []
    if not date_column:
        warnings.append("No reliable date/time column was detected. Forecasting requires a time axis.")
    if not target_column:
        warnings.append("No suitable numeric target column was detected. Select or create a numeric measure.")
    missing_heavy = [c["name"] for c in columns if c["missing_pct"] >= 30]
    if missing_heavy:
        warnings.append(f"High missingness (30% or more) detected in: {', '.join(missing_heavy[:8])}.")
    constants = [c["name"] for c in columns if c["is_constant"]]
    if constants:
        warnings.append(f"Constant columns can be removed: {', '.join(constants[:8])}.")
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_rows:
        warnings.append(f"{duplicate_rows:,} duplicate rows were detected; review before modelling.")

    numeric_summary: dict[str, Any] = {}
    for name in numeric_candidates:
        values = clean_numeric(frame[name]).dropna()
        if values.empty:
            continue
        q1 = float(values.quantile(0.25))
        q3 = float(values.quantile(0.75))
        iqr = q3 - q1
        outlier_count = (
            int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())
            if iqr > 0 else 0
        )
        skewness = float(values.skew()) if len(values) >= 3 else None
        numeric_summary[name] = {
            "count": int(values.count()),
            "mean": round(float(values.mean()), 4),
            "median": round(float(values.median()), 4),
            "std": round(float(values.std(ddof=0)), 4),
            "q1": round(q1, 4),
            "q3": round(q3, 4),
            "iqr": round(iqr, 4),
            "outlier_count": outlier_count,
            "outlier_pct": round(outlier_count / max(len(values), 1) * 100, 2),
            "skewness": round(skewness, 4) if skewness is not None and np.isfinite(skewness) else None,
            "min": round(float(values.min()), 4),
            "max": round(float(values.max()), 4),
        }

    categorical_summary: dict[str, Any] = {}
    for name in group_columns[:8]:
        categorical_summary[name] = [
            {"value": json_safe(k), "count": int(v)}
            for k, v in frame[name].fillna("Unknown").astype(str).value_counts().head(8).items()
        ]

    time_series_preview: list[dict[str, Any]] = []
    time_series_label: str | None = None
    date_range = None
    if date_column:
        parsed_dates, _ = _date_parse(frame[date_column])
        valid_dates = parsed_dates.dropna()
        if not valid_dates.empty:
            date_range = {"start": valid_dates.min().date().isoformat(), "end": valid_dates.max().date().isoformat()}
            if target_column:
                chart = pd.DataFrame({"date": parsed_dates, "value": clean_numeric(frame[target_column])})
                # Never average unlike commodities/markets into a misleading combined price line.
                if group_columns:
                    group_values = frame[group_columns].fillna("Unknown").astype(str)
                    for group_name in group_columns:
                        chart[group_name] = group_values[group_name].to_numpy()
                chart = chart.dropna(subset=["date", "value"])
                if group_columns:
                    group_counts = chart.groupby(group_columns, dropna=False).size().sort_values(ascending=False)
                    if not group_counts.empty:
                        top_key = group_counts.index[0]
                        if not isinstance(top_key, tuple):
                            top_key = (top_key,)
                        mask = pd.Series(True, index=chart.index)
                        for group_name, group_value in zip(group_columns, top_key):
                            mask &= chart[group_name].eq(str(group_value))
                        chart = chart.loc[mask]
                        time_series_label = " · ".join(f"{name}: {value}" for name, value in zip(group_columns, top_key))
                else:
                    time_series_label = "All observations"
                chart = chart.groupby("date", as_index=False)["value"].mean().sort_values("date").tail(120)
                time_series_preview = [
                    {"date": pd.Timestamp(row.date).strftime("%Y-%m-%d"), "value": round(float(row.value), 4)}
                    for row in chart.itertuples(index=False)
                ]

    temporal_coverage = None
    if date_column:
        parsed_dates, _ = _date_parse(frame[date_column])
        unique_timestamps = parsed_dates.dropna().drop_duplicates().sort_values()
        intervals = unique_timestamps.diff().dropna().dt.total_seconds() / 86400.0
        temporal_coverage = {
            "unique_timestamps": int(len(unique_timestamps)),
            "median_interval_days": round(float(intervals.median()), 4) if not intervals.empty else None,
            "min_interval_days": round(float(intervals.min()), 4) if not intervals.empty else None,
            "max_interval_days": round(float(intervals.max()), 4) if not intervals.empty else None,
        }

    memory_bytes = int(frame.memory_usage(index=True, deep=True).sum())
    missing_cells = int(frame.isna().sum().sum())
    total_cells = max(row_count * column_count, 1)
    duplicate_pct = round(duplicate_rows / max(row_count, 1) * 100, 2)
    missing_pct = round(missing_cells / total_cells * 100, 2)
    quality_score = max(0, round(100 - missing_pct * 0.65 - duplicate_pct * 0.8 - (len(missing_heavy) * 3), 1))

    return {
        "filename": filename,
        "task_type": task_type,
        "rows": int(row_count),
        "columns_count": int(column_count),
        "memory_bytes": memory_bytes,
        "memory_human": f"{memory_bytes / (1024 * 1024):.2f} MB",
        "duplicate_rows": duplicate_rows,
        "missing_cells": missing_cells,
        "missing_pct": missing_pct,
        "quality_score": quality_score,
        "date_column": date_column,
        "date_candidates": [c["name"] for c in columns if c["date_parse_pct"] >= 70.0],
        "target_column": target_column,
        "group_columns": group_columns,
        "date_range": date_range,
        "temporal_coverage": temporal_coverage,
        "numeric_columns": numeric_candidates,
        "categorical_columns": categorical_candidates,
        "column_profiles": columns,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "time_series_preview": time_series_preview,
        "time_series_label": time_series_label,
        "warnings": warnings,
        "recommendations": [
            "Use chronological train/validation/test splits for forecasting.",
            "Check the target column's unit before comparing different commodities.",
            "Review missing values and duplicate time keys before modelling.",
            "Compare every trained model against a naive last-observation baseline.",
        ] if task_type == "time_series_forecasting" else [
            "Choose a target and problem statement before training a predictive model.",
            "Review high-cardinality identifiers and missing values before analysis.",
            "Use stratified validation for classification or chronological validation for time series.",
        ],
    }
