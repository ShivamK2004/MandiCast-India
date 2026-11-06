from __future__ import annotations

import pandas as pd

from app.services.profiling import profile_dataset
from app.services.ingestion import clean_numeric, read_dataset


def test_profiler_detects_time_series_schema():
    frame = pd.DataFrame({
        "Arrival Date": pd.date_range("2025-01-01", periods=30).astype(str),
        "State": ["Gujarat" if i % 2 == 0 else "Maharashtra" for i in range(30)],
        "Commodity": ["Wheat"] * 30,
        "Modal Price": [2400 + i for i in range(30)],
    })
    profile = profile_dataset(frame, "sample.csv")
    assert profile["task_type"] == "time_series_forecasting"
    assert profile["date_column"] == "Arrival Date"
    assert profile["target_column"] == "Modal Price"
    assert "State" in profile["group_columns"]
    assert profile["rows"] == 30
    assert profile["temporal_coverage"]["unique_timestamps"] == 30
    assert profile["numeric_summary"]["Modal Price"]["q1"] is not None
    assert "outlier_count" in profile["numeric_summary"]["Modal Price"]


def test_profiler_handles_iso_and_indian_day_first_dates():
    frame = pd.DataFrame({
        "date": ["2025-01-02", "03/01/2025", "2025-01-04"],
        "price": [100, 102, 101],
    })
    profile = profile_dataset(frame)
    assert profile["date_column"] == "date"
    assert profile["target_column"] == "price"


def test_clean_numeric_handles_currency_and_commas():
    values = clean_numeric(pd.Series(["₹2,450", "1,200.50", "-", "(50)", "Rs. 3,200", "4,500 INR", "12.5%" ]))
    assert values.iloc[0] == 2450
    assert values.iloc[1] == 1200.5
    assert pd.isna(values.iloc[2])
    assert values.iloc[3] == -50
    assert values.iloc[4] == 3200
    assert values.iloc[5] == 4500
    assert values.iloc[6] == 12.5


def test_profiler_detects_non_mandi_business_schema():
    frame = pd.DataFrame({
        "sale_day": pd.date_range("2025-01-01", periods=40).astype(str),
        "product_line": ["Hardware", "Software"] * 20,
        "territory": ["North", "South", "West", "East"] * 10,
        "net_revenue": [1200 + index * 13 for index in range(40)],
        "transaction_reference": [f"T-{index:04d}" for index in range(40)],
        "record_id": list(range(40)),
    })
    profile = profile_dataset(frame, "retail.csv")
    assert profile["task_type"] == "time_series_forecasting"
    assert profile["date_column"] == "sale_day"
    assert profile["target_column"] == "net_revenue"
    assert "product_line" in profile["group_columns"]
    assert len(profile["column_profiles"]) == 6
    assert "record_id" not in profile["numeric_columns"]
    assert "net_revenue" in profile["numeric_summary"]


def test_clean_numeric_treats_infinity_as_missing():
    values = clean_numeric(pd.Series([10.0, float("inf"), float("-inf"), 12.0]))
    assert values.iloc[0] == 10.0
    assert pd.isna(values.iloc[1])
    assert pd.isna(values.iloc[2])
    assert values.iloc[3] == 12.0


def test_profiler_detects_boolean_group_dimension():
    frame = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=25).astype(str),
        "price": [100 + index for index in range(25)],
        "is_organic": [True, False] * 12 + [True],
    })
    profile = profile_dataset(frame)
    assert "is_organic" in profile["group_columns"]


def test_ingestion_supports_newline_delimited_json(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(
        '{"date":"2025-01-01","price":100}\n{"date":"2025-01-02","price":101}\n',
        encoding="utf-8",
    )
    frame = read_dataset(path)
    assert len(frame) == 2
    assert frame["price"].tolist() == [100, 101]


def test_ingestion_supports_jsonl_extension(tmp_path):
    path = tmp_path / "prices.jsonl"
    path.write_text(
        '{"date":"2025-01-01","price":100}\n{"date":"2025-01-02","price":101}\n',
        encoding="utf-8",
    )
    frame = read_dataset(path)
    assert len(frame) == 2
    assert frame["price"].tolist() == [100, 101]
