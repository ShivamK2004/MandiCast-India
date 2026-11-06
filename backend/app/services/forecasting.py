from __future__ import annotations

import hashlib
import json
import math
import random
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from app.services.ingestion import clean_numeric, read_dataset
from app.services.profiling import _date_parse

ProgressCallback = Callable[[int, str], None]


class PriceLSTM(nn.Module):
    """Residual LSTM with learned temporal attention over the lookback window."""

    def __init__(self, hidden_size: int = 48, num_layers: int = 1, dropout: float = 0.10) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, max(4, hidden_size // 2)),
            nn.Tanh(),
            nn.Linear(max(4, hidden_size // 2), 1, bias=False),
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size * 2),
            nn.Linear(hidden_size * 2, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, max(4, hidden_size // 2)),
            nn.GELU(),
            nn.Linear(max(4, hidden_size // 2), 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        sequence, _ = self.lstm(x)
        attention_weights = torch.softmax(self.attention(sequence).squeeze(-1), dim=1)
        context = torch.sum(sequence * attention_weights.unsqueeze(-1), dim=1)
        last_state = sequence[:, -1, :]
        return self.head(torch.cat((last_state, context), dim=-1)).squeeze(-1)


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | None]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = np.isfinite(actual) & np.isfinite(predicted)
    actual, predicted = actual[mask], predicted[mask]
    if not len(actual):
        return {"MAE": None, "RMSE": None, "MAPE_pct": None, "sMAPE_pct": None, "R2": None}
    error = predicted - actual
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error ** 2)))
    nonzero = np.abs(actual) > 1e-9
    mape = float(np.mean(np.abs(error[nonzero] / actual[nonzero])) * 100) if nonzero.any() else None
    denom = np.abs(actual) + np.abs(predicted)
    smape = float(np.mean(2 * np.abs(error[denom > 1e-9] / denom[denom > 1e-9])) * 100) if (denom > 1e-9).any() else None
    ss_total = float(np.sum((actual - actual.mean()) ** 2))
    r2 = float(1 - np.sum(error ** 2) / ss_total) if ss_total > 1e-12 else None
    wape_denom = float(np.sum(np.abs(actual)))
    wape = float(np.sum(np.abs(error)) / wape_denom * 100) if wape_denom > 1e-12 else None
    return {
        "MAE": mae,
        "RMSE": rmse,
        "MAPE_pct": mape,
        "sMAPE_pct": smape,
        "WAPE_pct": wape,
        "R2": r2,
    }


def _group_label(keys: list[str], values: tuple[Any, ...]) -> dict[str, str]:
    return {key: str(value) for key, value in zip(keys, values)}


def _forecast_date_parse(values: pd.Series) -> pd.Series:
    dates, _ = _date_parse(values)
    iso_date_mask = values.astype("string").str.match(
        r"^\s*\d{4}-\d{2}-\d{2}(?:$|[Tt\s])", na=False
    )
    if iso_date_mask.any():
        dates.loc[iso_date_mask] = pd.to_datetime(
            values.loc[iso_date_mask], errors="coerce", format="mixed", dayfirst=False
        )
    return dates


def _json_number(value: Any) -> float | None:
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def run_forecast(
    csv_path: str | Path,
    output_dir: str | Path,
    *,
    target_column: str,
    date_column: str,
    group_columns: list[str] | None = None,
    horizon: int = 7,
    lookback: int = 21,
    epochs: int = 25,
    batch_size: int = 128,
    hidden_size: int = 48,
    patience: int = 6,
    seed: int = 42,
    progress: ProgressCallback | None = None,
    run_id: str | None = None,
    dataset_id: str | None = None,
) -> dict[str, Any]:
    """Train one global residual LSTM across selected dataset series.

    The function never assumes that the uploaded dataset is an AGMARKNET file. The
    user-selected numeric target and time column define the forecasting problem.
    """
    if horizon < 1 or horizon > 90:
        raise ValueError("Forecast horizon must be between 1 and 90 steps.")
    if lookback < 3 or lookback > 180:
        raise ValueError("Lookback must be between 3 and 180 observations.")
    if epochs < 1 or epochs > 200:
        raise ValueError("Epochs must be between 1 and 200.")

    run_id = run_id or str(uuid.uuid4())
    input_path = Path(csv_path)
    dataset_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(min(4, max(1, torch.get_num_threads())))

    frame = read_dataset(csv_path)
    group_columns = group_columns or []
    unit_candidates = [column for column in frame.columns if str(column).strip().lower() in {
        "unit", "units", "price_unit", "currency_unit", "measurement_unit"
    }]
    unit_column = next((column for column in unit_candidates if column != target_column), None)
    unit_values = (
        sorted(frame[unit_column].dropna().astype(str).str.strip().replace("", np.nan).dropna().unique().tolist())
        if unit_column else []
    )
    target_unit = unit_values[0] if len(unit_values) == 1 else (
        f"Mixed units ({len(unit_values)})" if len(unit_values) > 1 else "Unit not specified"
    )
    comparable_absolute_metrics = len(unit_values) == 1
    if len(unit_values) == 1:
        unit_comparability_status = "consistent_declared"
    elif len(unit_values) > 1:
        unit_comparability_status = "mixed_declared"
    else:
        unit_comparability_status = "unit_not_declared"
    if len(unit_values) > 1 and unit_column not in group_columns:
        raise ValueError(
            f"The dataset contains {len(unit_values)} values in '{unit_column}'. "
            f"Include '{unit_column}' in Series dimensions or filter the dataset before forecasting "
            "so values with different measurement units are not combined."
        )
    for column in [target_column, date_column, *group_columns]:
        if column not in frame.columns:
            raise ValueError(f"Selected column '{column}' does not exist in the uploaded dataset.")
    target_values = clean_numeric(frame[target_column])
    if not target_values.notna().any():
        raise ValueError(f"Target column '{target_column}' has no values that can be converted to numbers.")

    dates = _forecast_date_parse(frame[date_column])
    working = pd.DataFrame({
        "_date": dates,
        "_target": clean_numeric(frame[target_column]),
    })
    for index, column in enumerate(group_columns):
        working[f"_group_{index}"] = frame[column].fillna("Unknown").astype(str)
    working = working.dropna(subset=["_date", "_target"])
    if working.empty:
        raise ValueError("No valid rows remain after parsing the selected date and numeric target columns.")
    working = working.sort_values("_date")

    group_keys = [f"_group_{i}" for i in range(len(group_columns))]
    if group_keys:
        grouped = working.groupby(group_keys, sort=False, dropna=False)
    else:
        working["_single_series"] = "All observations"
        group_keys = ["_single_series"]
        grouped = working.groupby(group_keys, sort=False, dropna=False)

    series: list[dict[str, Any]] = []
    all_dates: list[pd.Timestamp] = []
    duplicate_time_keys = 0
    for raw_key, group in grouped:
        if not isinstance(raw_key, tuple):
            raw_key = (raw_key,)
        collapsed = group.groupby("_date", as_index=False)["_target"].mean().sort_values("_date")
        duplicate_time_keys += int(len(group) - len(collapsed))
        prices = collapsed["_target"].to_numpy(dtype=np.float64)
        date_values = pd.to_datetime(collapsed["_date"]).to_numpy()
        if len(prices) < lookback + 8:
            continue
        labels = _group_label(group_columns, raw_key) if group_columns else {"series": "All observations"}
        series.append({"labels": labels, "prices": prices, "dates": date_values})
        all_dates.extend(pd.to_datetime(date_values).tolist())

    if not series:
        raise ValueError(
            f"No series has enough history. Each group needs at least {lookback + 8} distinct dates. "
            "Reduce lookback or upload more observations."
        )

    unique_dates = np.array(sorted(set(all_dates)), dtype="datetime64[ns]")
    if len(unique_dates) < lookback + 8:
        raise ValueError("Not enough distinct dates for a chronological train/validation/test split.")
    train_idx = min(max(int(len(unique_dates) * 0.70) - 1, lookback + 1), len(unique_dates) - 3)
    val_idx = min(max(int(len(unique_dates) * 0.85) - 1, train_idx + 1), len(unique_dates) - 2)
    train_cutoff, val_cutoff = unique_dates[train_idx], unique_dates[val_idx]

    # Fit one change scaler per series using only that series' training-period changes.
    # This prevents large-price markets from dominating the shared model's target scale.
    for item in series:
        changes = np.diff(item["prices"], prepend=item["prices"][0])
        training_mask = item["dates"] <= train_cutoff
        training_changes = changes[training_mask]
        item_mean = float(np.mean(training_changes)) if len(training_changes) else 0.0
        item_std = float(np.std(training_changes)) if len(training_changes) else 1.0
        if not np.isfinite(item_std) or item_std < 1e-8:
            item_std = 1.0
        item["change_mean"] = item_mean
        item["change_std"] = item_std

    samples: dict[str, list[tuple[np.ndarray, float, float, float, dict[str, str], str, float, float]]] = {
        "train": [], "validation": [], "test": []
    }
    for item in series:
        prices, date_values = item["prices"], item["dates"]
        changes = np.diff(prices, prepend=prices[0])
        for index in range(lookback, len(prices)):
            target_date = date_values[index]
            split = "train" if target_date <= train_cutoff else ("validation" if target_date <= val_cutoff else "test")
            window = (changes[index - lookback:index] - item["change_mean"]) / item["change_std"]
            target_scaled = (changes[index] - item["change_mean"]) / item["change_std"]
            baseline = float(prices[index - 1])
            samples[split].append((window.astype(np.float32), float(target_scaled), float(prices[index]), baseline, item["labels"], pd.Timestamp(target_date).isoformat(), item["change_mean"], item["change_std"]))

    for split_name in ("train", "validation", "test"):
        if not samples[split_name]:
            raise ValueError(f"The {split_name} split has no usable sequences. Add history or reduce lookback.")

    train_x = np.stack([row[0] for row in samples["train"]])[:, :, None]
    train_y = np.array([row[1] for row in samples["train"]], dtype=np.float32)
    val_x = np.stack([row[0] for row in samples["validation"]])[:, :, None]
    val_y = np.array([row[1] for row in samples["validation"]], dtype=np.float32)
    test_x = np.stack([row[0] for row in samples["test"]])[:, :, None]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PriceLSTM(hidden_size=hidden_size).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.HuberLoss()
    loader = DataLoader(
        TensorDataset(torch.from_numpy(train_x), torch.from_numpy(train_y)),
        batch_size=batch_size,
        shuffle=True,
        drop_last=False,
    )

    best_state = None
    best_val = float("inf")
    stale_epochs = 0
    history: list[dict[str, float]] = []
    if progress:
        progress(10, f"Prepared {len(series)} time series; training on {device.type.upper()}")

    for epoch in range(epochs):
        model.train()
        running: list[float] = []
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(batch_x)
            loss = loss_fn(prediction, batch_y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            running.append(float(loss.detach().cpu()))
        model.eval()
        with torch.no_grad():
            val_prediction = model(torch.from_numpy(val_x).to(device)).cpu().numpy()
        val_tensor = torch.from_numpy(val_prediction)
        target_tensor = torch.from_numpy(val_y)
        val_loss = float(loss_fn(val_tensor, target_tensor).item())
        val_mse = float(np.mean((val_prediction - val_y) ** 2))
        history.append({
            "epoch": epoch + 1,
            "train_loss": float(np.mean(running)),
            "validation_loss": val_loss,
            "validation_mse": val_mse,
        })
        if val_loss < best_val - 1e-7:
            best_val = val_loss
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            stale_epochs = 0
        else:
            stale_epochs += 1
        if progress:
            progress(10 + int((epoch + 1) / epochs * 55), f"Training epoch {epoch + 1}/{epochs}")
        if stale_epochs >= patience:
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        val_scaled_prediction = model(torch.from_numpy(val_x).to(device)).cpu().numpy()
        test_scaled_prediction = model(torch.from_numpy(test_x).to(device)).cpu().numpy()

    # Calibrate indicative prediction bands from validation residuals only. The held-out
    # test split is never used to choose interval widths.
    val_actual = np.array([row[2] for row in samples["validation"]], dtype=float)
    val_baseline = np.array([row[3] for row in samples["validation"]], dtype=float)
    val_means = np.array([row[6] for row in samples["validation"]], dtype=float)
    val_stds = np.array([row[7] for row in samples["validation"]], dtype=float)
    val_prediction = val_baseline + val_scaled_prediction * val_stds + val_means
    val_labels = [tuple(sorted(row[4].items())) for row in samples["validation"]]
    val_abs_residual = np.abs(val_actual - val_prediction)

    def residual_quantile(values: np.ndarray, coverage: float = 0.90) -> float:
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        if not len(values):
            return 0.0
        # Higher empirical quantile is conservative for finite validation samples.
        return float(np.quantile(values, coverage, method="higher"))

    global_interval_radius = residual_quantile(val_abs_residual)
    interval_radius_by_series: dict[tuple[tuple[str, str], ...], float] = {}
    for label_key in set(val_labels):
        mask = np.array([value == label_key for value in val_labels], dtype=bool)
        values = val_abs_residual[mask]
        interval_radius_by_series[label_key] = (
            residual_quantile(values) if len(values) >= 8 else global_interval_radius
        )

    test_actual = np.array([row[2] for row in samples["test"]], dtype=float)
    test_naive = np.array([row[3] for row in samples["test"]], dtype=float)
    test_means = np.array([row[6] for row in samples["test"]], dtype=float)
    test_stds = np.array([row[7] for row in samples["test"]], dtype=float)
    lstm_prediction = test_naive + test_scaled_prediction * test_stds + test_means
    # Build test baseline predictions from the corresponding per-series test sample.
    moving_map: dict[tuple[tuple[tuple[str, str], ...], str], float] = {}
    for item in series:
        prices, dates = item["prices"], item["dates"]
        label_key = tuple(sorted(item["labels"].items()))
        for index in range(lookback, len(prices)):
            if dates[index] > val_cutoff:
                moving_map[(label_key, pd.Timestamp(dates[index]).isoformat())] = float(np.mean(prices[max(0, index - 7):index]))
    test_moving = np.array([
        moving_map.get((tuple(sorted(row[4].items())), row[5]), row[3])
        for row in samples["test"]
    ], dtype=float)

    metric_lstm = _metrics(test_actual, lstm_prediction)
    metric_naive = _metrics(test_actual, test_naive)
    metric_moving = _metrics(test_actual, test_moving)

    test_label_keys = [tuple(sorted(row[4].items())) for row in samples["test"]]
    test_interval_radii = np.array([
        interval_radius_by_series.get(key, global_interval_radius) for key in test_label_keys
    ], dtype=float)
    nonnegative_target = all(float(np.min(item["prices"])) >= 0 for item in series)
    test_lower_90 = lstm_prediction - test_interval_radii
    if nonnegative_target:
        test_lower_90 = np.maximum(0.0, test_lower_90)
    test_upper_90 = lstm_prediction + test_interval_radii
    test_interval_coverage_pct = float(
        np.mean((test_actual >= test_lower_90) & (test_actual <= test_upper_90)) * 100
    )

    test_series_labels = [
        " | ".join(f"{k}={v}" for k, v in sorted(row[4].items()))
        for row in samples["test"]
    ]
    series_metrics: list[dict[str, Any]] = []
    for series_name in sorted(set(test_series_labels)):
        indices = np.array([label == series_name for label in test_series_labels], dtype=bool)
        series_metrics.append({
            "series": series_name,
            "observations": int(indices.sum()),
            "LSTM": _metrics(test_actual[indices], lstm_prediction[indices]),
            "Naive last value": _metrics(test_actual[indices], test_naive[indices]),
            "Moving average (7)": _metrics(test_actual[indices], test_moving[indices]),
        })

    # Dimension-level rollups (for example commodity and market) make the result
    # useful to analysts without hiding poor-performing individual series.
    test_by_group: dict[str, list[dict[str, Any]]] = {}
    test_group_values = [row[4] for row in samples["test"]]
    for dimension in group_columns:
        values = sorted({labels.get(dimension, "Unknown") for labels in test_group_values})
        dimension_rows: list[dict[str, Any]] = []
        for value in values:
            mask = np.array([labels.get(dimension, "Unknown") == value for labels in test_group_values], dtype=bool)
            selected_series = {test_series_labels[index] for index in np.where(mask)[0]}
            dimension_rows.append({
                "value": value,
                "series_count": len(selected_series),
                "observations": int(mask.sum()),
                "LSTM": _metrics(test_actual[mask], lstm_prediction[mask]),
                "Naive last value": _metrics(test_actual[mask], test_naive[mask]),
                "Moving average (7)": _metrics(test_actual[mask], test_moving[mask]),
            })
        test_by_group[dimension] = dimension_rows

    def macro_average(model_key: str) -> dict[str, float | None]:
        keys = ("MAE", "RMSE", "MAPE_pct", "sMAPE_pct", "WAPE_pct", "R2")
        values: dict[str, float | None] = {}
        for key in keys:
            usable = [row[model_key][key] for row in series_metrics if row[model_key][key] is not None]
            values[key] = float(np.mean(usable)) if usable else None
        return values

    macro_metrics = {
        "LSTM": macro_average("LSTM"),
        "Naive last value": macro_average("Naive last value"),
        "Moving average (7)": macro_average("Moving average (7)"),
    }

    if progress:
        progress(75, "Evaluating benchmarks and generating future forecasts")

    forecast_rows: list[dict[str, Any]] = []
    preview_by_series: list[dict[str, Any]] = []
    for item in series:
        prices, dates = item["prices"], item["dates"]
        changes = np.diff(prices, prepend=prices[0]).astype(np.float64).tolist()
        current_price = float(prices[-1])
        forecast_points: list[dict[str, Any]] = []
        for step in range(1, horizon + 1):
            window = np.asarray(changes[-lookback:], dtype=np.float32)
            if len(window) < lookback:
                window = np.pad(window, (lookback - len(window), 0))
            scaled_window = ((window - item["change_mean"]) / item["change_std"])[None, :, None]
            with torch.no_grad():
                predicted_scaled = float(model(torch.from_numpy(scaled_window).to(device)).cpu().item())
            predicted_change = predicted_scaled * item["change_std"] + item["change_mean"]
            current_price = current_price + predicted_change
            if nonnegative_target:
                current_price = max(0.0, current_price)
            changes.append(predicted_change)
            label_key = tuple(sorted(item["labels"].items()))
            interval_radius = interval_radius_by_series.get(label_key, global_interval_radius) * math.sqrt(step)
            forecast_point = {
                "step": step,
                "forecast_price": round(current_price, 4),
                "lower_90": round(max(0.0, current_price - interval_radius) if nonnegative_target else current_price - interval_radius, 4),
                "upper_90": round(current_price + interval_radius, 4),
            }
            forecast_points.append(forecast_point)
            forecast_rows.append({
                "run_id": run_id, "dataset_id": dataset_id, "dataset_sha256": dataset_sha256, **item["labels"], "step": step,
                "forecast_price": round(current_price, 4),
                "lower_90": round(max(0.0, current_price - interval_radius) if nonnegative_target else current_price - interval_radius, 4),
                "upper_90": round(current_price + interval_radius, 4),
                "interval_method": "validation_abs_residual_q90_sqrt_step_widening_approximate",
                "target_unit": target_unit,
                "nonnegative_target_constraint": nonnegative_target,
                "last_observed_price": float(prices[-1]),
                "last_observed_date": pd.Timestamp(dates[-1]).date().isoformat(),
            })
        history_start = max(0, len(prices) - min(60, len(prices)))
        preview_by_series.append({
            "series": item["labels"],
            "history": [{"date": pd.Timestamp(dates[i]).date().isoformat(), "actual": round(float(prices[i]), 4)} for i in range(history_start, len(prices))],
            "forecast": forecast_points,
        })

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    predictions_df = pd.DataFrame({
        "run_id": run_id,
        "dataset_id": dataset_id,
        "dataset_sha256": dataset_sha256,
        "date": [row[5] for row in samples["test"]],
        "actual": test_actual,
        "lstm_prediction": lstm_prediction,
        "lstm_lower_90": test_lower_90,
        "lstm_upper_90": test_upper_90,
        "naive_last_value": test_naive,
        "moving_average_7": test_moving,
        "target_unit": target_unit,
        "unit_comparability_status": unit_comparability_status,
        "series": test_series_labels,
        **{dimension: [row[4].get(dimension, "Unknown") for row in samples["test"]] for dimension in group_columns},
    })
    predictions_df.to_csv(output / "test_predictions.csv", index=False)
    pd.DataFrame(forecast_rows).to_csv(output / "forecasts.csv", index=False)
    history_frame = pd.DataFrame(history)
    history_frame.insert(0, "dataset_sha256", dataset_sha256)
    history_frame.insert(0, "dataset_id", dataset_id or "")
    history_frame.insert(0, "run_id", run_id)
    history_frame.to_csv(output / "training_history.csv", index=False)
    pd.DataFrame([
        {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "dataset_sha256": dataset_sha256,
            "target_unit": target_unit,
            "unit_comparability_status": unit_comparability_status,
            "series": row["series"],
            "observations": row["observations"],
            **{f"{model}__{metric_name}": value
               for model, metrics in row.items() if isinstance(metrics, dict)
               for metric_name, value in metrics.items()},
        }
        for row in series_metrics
    ]).to_csv(output / "series_metrics.csv", index=False)
    group_metric_rows: list[dict[str, Any]] = []
    for dimension, dimension_rows in test_by_group.items():
        for row in dimension_rows:
            group_metric_rows.append({
                "run_id": run_id, "dataset_id": dataset_id, "dataset_sha256": dataset_sha256,
                "target_unit": target_unit, "unit_comparability_status": unit_comparability_status,
                "dimension": dimension, "value": row["value"],
                "series_count": row["series_count"], "observations": row["observations"],
                **{f"{model}__{metric_name}": value
                   for model, metrics in row.items() if isinstance(metrics, dict)
                   for metric_name, value in metrics.items()},
            })
    pd.DataFrame(group_metric_rows).to_csv(output / "group_metrics.csv", index=False)
    torch.save({
        "state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
        "lookback": lookback,
        "hidden_size": hidden_size,
        "target_scaling": "per_series_train_only_change_standardisation",
        "series_scalers": [
            {"series": item["labels"], "change_mean": item["change_mean"], "change_std": item["change_std"]}
            for item in series
        ],
        "target_column": target_column,
        "date_column": date_column,
        "group_columns": group_columns,
        "run_id": run_id,
        "dataset_id": dataset_id,
        "dataset_sha256": dataset_sha256,
        "best_validation_loss": best_val,
        "best_epoch": min(history, key=lambda row: row["validation_loss"])["epoch"],
    }, output / "model.pt")

    def improvement_pct(reference: float | None, candidate: float | None) -> float | None:
        if reference is None or candidate is None or not np.isfinite(reference) or reference <= 1e-12:
            return None
        return float((reference - candidate) / reference * 100)

    improvement_vs_naive = improvement_pct(metric_naive["MAE"], metric_lstm["MAE"])
    benchmark_candidates = {
        "Naive last value": metric_naive,
        "Moving average (7)": metric_moving,
    }
    valid_benchmarks = {
        name: metrics["MAE"] for name, metrics in benchmark_candidates.items()
        if metrics["MAE"] is not None and np.isfinite(metrics["MAE"])
    }
    best_benchmark = min(valid_benchmarks, key=valid_benchmarks.get) if valid_benchmarks else "Unavailable"
    best_benchmark_mae = valid_benchmarks.get(best_benchmark)
    improvement_vs_best = improvement_pct(best_benchmark_mae, metric_lstm["MAE"])

    candidate_metrics = {"LSTM": metric_lstm, **benchmark_candidates}
    valid_candidates = {
        name: metrics["MAE"] for name, metrics in candidate_metrics.items()
        if metrics["MAE"] is not None and np.isfinite(metrics["MAE"])
    }
    best_model = min(valid_candidates, key=valid_candidates.get) if valid_candidates else "Unavailable"
    result = {
        "experiment_id": run_id,
        "dataset_id": dataset_id,
        "dataset_sha256": dataset_sha256,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_column": target_column,
        "target_unit": target_unit,
        "nonnegative_target_constraint": nonnegative_target,
        "unit_column": unit_column,
        "absolute_metrics_comparable_across_series": comparable_absolute_metrics,
        "unit_comparability_status": unit_comparability_status,
        "date_column": date_column,
        "group_columns": group_columns,
        "horizon": horizon,
        "lookback": lookback,
        "target_scaling": "per_series_train_only_change_standardisation",
        "series_count": len(series),
        "rows_used": int(sum(len(item["prices"]) for item in series)),
        "input_rows": int(len(frame)),
        "rows_dropped_or_invalid": int(len(frame) - sum(len(item["prices"]) for item in series)),
        "duplicate_time_keys_collapsed": duplicate_time_keys,
        "train_cutoff": pd.Timestamp(train_cutoff).date().isoformat(),
        "validation_cutoff": pd.Timestamp(val_cutoff).date().isoformat(),
        "epochs_trained": len(history),
        "best_epoch": int(min(history, key=lambda row: row["validation_loss"])["epoch"]),
        "best_validation_loss": float(best_val),
        "device": str(device),
        "test_lstm": metric_lstm,
        "test_naive": metric_naive,
        "test_moving_average": metric_moving,
        "test_pooled": {"LSTM": metric_lstm, "Naive last value": metric_naive, "Moving average (7)": metric_moving},
        "test_macro": macro_metrics,
        "test_by_series": series_metrics,
        "test_by_group": test_by_group,
        "r2_diagnostics": {
            "pooled_lstm_r2": metric_lstm["R2"],
            "macro_lstm_r2": macro_metrics["LSTM"]["R2"],
            "median_series_lstm_r2": float(np.median([row["LSTM"]["R2"] for row in series_metrics if row["LSTM"]["R2"] is not None])) if any(row["LSTM"]["R2"] is not None for row in series_metrics) else None,
            "negative_series_r2_count": int(sum(1 for row in series_metrics if row["LSTM"]["R2"] is not None and row["LSTM"]["R2"] < 0)),
            "series_r2_count": int(sum(1 for row in series_metrics if row["LSTM"]["R2"] is not None)),
        },
        "interval_calibration": {
            "nominal_level_pct": 90,
            "method": "absolute validation residual empirical quantile; forecast bands widened by sqrt(step)",
            "global_radius": global_interval_radius,
            "test_empirical_coverage_pct": test_interval_coverage_pct,
            "warning": "Indicative intervals only; one-step validation calibration with square-root horizon widening does not guarantee future coverage.",
        },
        "lstm_mae_improvement_vs_naive_pct": improvement_vs_naive,
        "lstm_mae_improvement_vs_best_benchmark_pct": improvement_vs_best,
        "best_benchmark": best_benchmark,
        "best_benchmark_mae": best_benchmark_mae,
        "best_model": best_model,
        "baseline_winner": best_model,
        "training_history": history,
        "forecast_preview": preview_by_series[:12],
        "forecast_rows": len(forecast_rows),
        "artifacts": ["model.pt", "test_predictions.csv", "forecasts.csv", "training_history.csv", "series_metrics.csv", "group_metrics.csv", "result.json", "run_manifest.json"],
        "notes": [
            "Forecast horizon is measured in observed steps, not assumed calendar days.",
            "The target is modelled as the change from the previous observation to support differently scaled series.",
            "The LSTM is compared with both persistence and moving-average baselines; the best benchmark excludes the LSTM.",
            "Macro metrics average per-series metrics so large series do not dominate the macro summary.",
            "WAPE is reported alongside MAPE because it is more stable when some actual values are near zero.",
            "Pooled R2 can be inflated by between-series level differences; inspect macro and per-series R2 before interpreting fit.",
            ("The declared target unit is consistent across the dataset." if unit_comparability_status == "consistent_declared" else ("Multiple measurement units are present; interpret absolute error aggregates only within a unit." if unit_comparability_status == "mixed_declared" else "No unit column was detected; verify measurement-unit consistency before comparing absolute errors across series.")),
            (f"Detected target unit: {target_unit}." if target_unit != "Unit not specified" else "No target measurement unit was detected; interpret error magnitudes in the source data's native unit."),
            "Forecast intervals are indicative validation-residual bands, not guaranteed probabilistic coverage intervals.",
        ],
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    artifact_manifest = []
    for artifact_path in sorted(output.iterdir()):
        if artifact_path.is_file() and artifact_path.name != "run_manifest.json":
            payload = artifact_path.read_bytes()
            artifact_manifest.append({
                "name": artifact_path.name,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
    manifest = {
        "experiment_id": run_id,
        "dataset_id": dataset_id,
        "dataset_sha256": dataset_sha256,
        "created_at": result["created_at"],
        "config": {
            "target_column": target_column, "date_column": date_column,
            "group_columns": group_columns, "horizon": horizon, "lookback": lookback,
            "epochs_requested": epochs, "batch_size": batch_size, "hidden_size": hidden_size, "seed": seed,
        },
        "evaluation_summary": {
            "target_unit": target_unit, "unit_column": unit_column,
            "unit_comparability_status": unit_comparability_status,
            "best_epoch": result["best_epoch"], "best_model_by_mae": best_model,
            "best_baseline_by_mae": best_benchmark,
            "pooled_lstm_metrics": metric_lstm,
            "macro_lstm_metrics": macro_metrics["LSTM"],
            "interval_test_coverage_pct": test_interval_coverage_pct,
        },
        "artifacts": artifact_manifest,
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    if progress:
        progress(100, "Forecast job completed")
    return result
