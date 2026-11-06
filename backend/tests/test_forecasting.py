from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.forecasting import PriceLSTM, run_forecast
import torch


def test_generic_lstm_forecast_pipeline(tmp_path):
    rng = np.random.default_rng(7)
    rows = []
    for market, base in [("A", 100.0), ("B", 400.0)]:
        value = base
        for index, date in enumerate(pd.date_range("2025-01-01", periods=95)):
            value = max(1, value + 0.4 + rng.normal(0, 0.8))
            rows.append({"date": date.strftime("%Y-%m-%d"), "market": market, "price": value})
    path = tmp_path / "prices.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    result = run_forecast(
        path,
        tmp_path / "artifacts",
        run_id="test-run-001",
        dataset_id="test-dataset-001",
        target_column="price",
        date_column="date",
        group_columns=["market"],
        horizon=3,
        lookback=10,
        epochs=2,
        batch_size=64,
        hidden_size=16,
        patience=2,
    )
    assert result["series_count"] == 2
    assert result["forecast_rows"] == 6
    assert (tmp_path / "artifacts" / "forecasts.csv").exists()
    assert result["test_lstm"]["MAE"] is not None
    candidates = {
        "LSTM": result["test_lstm"]["MAE"],
        "Naive last value": result["test_naive"]["MAE"],
        "Moving average (7)": result["test_moving_average"]["MAE"],
    }
    assert result["baseline_winner"] == min(candidates, key=candidates.get)
    assert result["best_model"] == result["baseline_winner"]
    assert result["best_benchmark"] in {"Naive last value", "Moving average (7)"}
    assert result["lstm_mae_improvement_vs_naive_pct"] is not None
    assert result["lstm_mae_improvement_vs_best_benchmark_pct"] is not None
    assert len(result["test_by_series"]) == 2
    assert set(result["test_macro"]) == {"LSTM", "Naive last value", "Moving average (7)"}
    assert (tmp_path / "artifacts" / "series_metrics.csv").exists()
    assert (tmp_path / "artifacts" / "group_metrics.csv").exists()
    assert (tmp_path / "artifacts" / "run_manifest.json").exists()
    assert len(result["training_history"]) == result["epochs_trained"]
    assert "validation_loss" in result["training_history"][0]
    assert result["experiment_id"] == "test-run-001"
    assert result["dataset_id"] == "test-dataset-001"
    assert result["unit_comparability_status"] == "unit_not_declared"
    assert result["absolute_metrics_comparable_across_series"] is False
    assert "market" in result["test_by_group"]
    assert result["interval_calibration"]["nominal_level_pct"] == 90
    assert 0 <= result["interval_calibration"]["test_empirical_coverage_pct"] <= 100
    import json
    import hashlib
    manifest = json.loads((tmp_path / "artifacts" / "run_manifest.json").read_text())
    assert manifest["experiment_id"] == "test-run-001"
    assert manifest["dataset_sha256"] == result["dataset_sha256"]
    for artifact in manifest["artifacts"]:
        payload = (tmp_path / "artifacts" / artifact["name"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
    prediction_rows = pd.read_csv(tmp_path / "artifacts" / "test_predictions.csv")
    assert prediction_rows["run_id"].nunique() == 1
    assert prediction_rows["run_id"].iloc[0] == "test-run-001"
    assert {"lstm_lower_90", "lstm_upper_90"}.issubset(prediction_rows.columns)
    assert (prediction_rows["lstm_lower_90"] <= prediction_rows["lstm_prediction"]).all()
    assert (prediction_rows["lstm_upper_90"] >= prediction_rows["lstm_prediction"]).all()
    assert (prediction_rows["lstm_lower_90"] >= 0).all()
    assert len(result["test_by_group"]["market"]) == 2
    assert set(result["test_by_group"]["market"][0]) >= {"value", "series_count", "observations", "LSTM"}


def test_attention_lstm_returns_one_value_per_sequence():
    model = PriceLSTM(hidden_size=16)
    inputs = torch.randn(4, 12, 1)
    output = model(inputs)
    assert output.shape == (4,)
    assert torch.isfinite(output).all()


def test_mixed_units_require_unit_dimension_or_filter(tmp_path):
    rows = []
    for unit, scale in [("Rs/Quintal", 1.0), ("Rs/Kg", 0.01)]:
        for index, date in enumerate(pd.date_range("2025-01-01", periods=45)):
            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "commodity": "Wheat",
                "unit": unit,
                "price": (2400 + index * 2) * scale,
            })
    path = tmp_path / "mixed_units.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    import pytest
    with pytest.raises(ValueError, match="Include 'unit' in Series dimensions"):
        run_forecast(
            path, tmp_path / "artifacts", target_column="price", date_column="date",
            group_columns=["commodity"], horizon=2, lookback=8, epochs=1, hidden_size=8,
        )


def test_negative_numeric_target_is_not_clamped(tmp_path):
    rows = []
    for index, date in enumerate(pd.date_range("2025-01-01", periods=70)):
        rows.append({"date": date.strftime("%Y-%m-%d"), "value": -50.0 - index * 1.5})
    path = tmp_path / "negative_series.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    result = run_forecast(
        path, tmp_path / "negative_artifacts", target_column="value", date_column="date",
        horizon=3, lookback=8, epochs=1, batch_size=32, hidden_size=8, patience=1,
    )
    assert result["nonnegative_target_constraint"] is False
    assert all(
        point["forecast_price"] < 0
        for series in result["forecast_preview"]
        for point in series["forecast"]
    )


def test_iso_dates_preserve_test_prediction_and_forecast_source_alignment(tmp_path):
    rows = []
    dates = pd.date_range("2024-07-01", periods=90, freq="D")
    for variety, base in [("Desi", 1000.0), ("Kabuli", 5000.0)]:
        for index, date in enumerate(dates):
            rows.append({
                "arrival_date": date.strftime("%Y-%m-%d"),
                "state": "Gujarat",
                "district": "Rajkot",
                "market": "Rajkot APMC",
                "commodity": "Chickpea",
                "variety": variety,
                "modal_price": base + index * 2 + (index % 5),
            })
    source = pd.DataFrame(rows)
    path = tmp_path / "iso_dates.csv"
    source.to_csv(path, index=False)
    output = tmp_path / "artifacts"

    result = run_forecast(
        path,
        output,
        target_column="modal_price",
        date_column="arrival_date",
        group_columns=["state", "district", "market", "commodity", "variety"],
        horizon=7,
        lookback=10,
        epochs=2,
        batch_size=32,
        hidden_size=8,
        patience=2,
    )

    predictions = pd.read_csv(output / "test_predictions.csv")
    forecast = pd.read_csv(output / "forecasts.csv")
    source["arrival_date"] = pd.to_datetime(source["arrival_date"]).dt.strftime("%Y-%m-%d")
    predictions["date"] = pd.to_datetime(predictions["date"]).dt.strftime("%Y-%m-%d")
    expected = source.rename(columns={"arrival_date": "date", "modal_price": "source_actual"})
    aligned = predictions.merge(
        expected[["date", "state", "district", "market", "commodity", "variety", "source_actual"]],
        on=["date", "state", "district", "market", "commodity", "variety"],
        how="left",
        validate="one_to_one",
    )

    assert result["series_count"] == 2
    assert len(predictions) == 2 * (len(dates) - int(len(dates) * 0.85))
    assert aligned["source_actual"].notna().all()
    np.testing.assert_allclose(aligned["actual"], aligned["source_actual"])

    for _, series_rows in forecast.groupby("variety"):
        variety = series_rows["variety"].iloc[0]
        source_series = source[source["variety"] == variety]
        latest = source_series.sort_values("arrival_date").iloc[-1]
        assert len(series_rows) == 7
        assert series_rows["step"].tolist() == list(range(1, 8))
        assert series_rows["last_observed_date"].eq(latest["arrival_date"]).all()
        np.testing.assert_allclose(series_rows["last_observed_price"], latest["modal_price"])

    from app.services.forecasting import _metrics
    for model_key, prediction_column in [
        ("test_lstm", "lstm_prediction"),
        ("test_naive", "naive_last_value"),
        ("test_moving_average", "moving_average_7"),
    ]:
        recomputed = _metrics(predictions["actual"].to_numpy(), predictions[prediction_column].to_numpy())
        assert result[model_key] == recomputed
