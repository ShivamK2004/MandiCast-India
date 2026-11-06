export type Page = 'overview' | 'datasets' | 'forecast' | 'runs' | 'guide'

export type ColumnProfile = {
  name: string
  normalized_name: string
  dtype: string
  inferred_type: string
  missing_count: number
  missing_pct: number
  unique_count: number
  unique_pct: number
  numeric_parse_pct: number
  date_parse_pct: number
  examples: unknown[]
  is_constant: boolean
}

export type DatasetProfile = {
  filename: string
  task_type: string
  rows: number
  columns_count: number
  memory_bytes: number
  memory_human: string
  duplicate_rows: number
  missing_cells: number
  missing_pct: number
  quality_score: number
  date_column: string | null
  date_candidates: string[]
  target_column: string | null
  group_columns: string[]
  date_range: { start: string; end: string } | null
  temporal_coverage: { unique_timestamps: number; median_interval_days: number | null; min_interval_days: number | null; max_interval_days: number | null } | null
  numeric_columns: string[]
  categorical_columns: string[]
  column_profiles: ColumnProfile[]
  numeric_summary: Record<string, { count: number; mean: number; median: number; std: number; q1: number; q3: number; iqr: number; outlier_count: number; outlier_pct: number; skewness: number | null; min: number; max: number }>
  categorical_summary: Record<string, { value: string; count: number }[]>
  time_series_preview: { date: string; value: number }[]
  time_series_label?: string | null
  warnings: string[]
  recommendations: string[]
}

export type Dataset = {
  id: string
  filename: string
  file_type: string
  size_bytes: number
  row_count: number
  column_count: number
  created_at: string | null
  profile: DatasetProfile
}

export type ForecastMetrics = {
  MAE: number | null
  RMSE: number | null
  MAPE_pct: number | null
  sMAPE_pct: number | null
  WAPE_pct?: number | null
  R2: number | null
}

export type ForecastSeries = {
  series: Record<string, string>
  history: { date: string; actual: number }[]
  forecast: { step: number; forecast_price: number; lower_90?: number; upper_90?: number }[]
}

export type GroupMetricRow = {
  value: string
  series_count: number
  observations: number
  LSTM: ForecastMetrics
  'Naive last value': ForecastMetrics
  'Moving average (7)': ForecastMetrics
}

export type ForecastResult = {
  experiment_id?: string
  dataset_id?: string | null
  dataset_sha256?: string
  created_at?: string
  target_column: string
  target_unit?: string
  unit_column?: string | null
  absolute_metrics_comparable_across_series?: boolean
  unit_comparability_status?: 'consistent_declared' | 'mixed_declared' | 'unit_not_declared'
  input_rows?: number
  date_column: string
  group_columns: string[]
  horizon: number
  lookback: number
  series_count: number
  rows_used: number
  epochs_trained: number
  best_epoch?: number
  best_validation_loss?: number
  device: string
  train_cutoff?: string
  validation_cutoff?: string
  test_lstm: ForecastMetrics
  test_naive: ForecastMetrics
  test_moving_average: ForecastMetrics
  lstm_mae_improvement_vs_naive_pct: number | null
  lstm_mae_improvement_vs_best_benchmark_pct?: number | null
  best_benchmark?: string
  best_benchmark_mae?: number | null
  best_model?: string
  baseline_winner: string
  test_pooled?: Record<string, ForecastMetrics>
  test_macro?: Record<string, ForecastMetrics>
  test_by_series?: Array<Record<string, unknown>>
  test_by_group?: Record<string, GroupMetricRow[]>
  r2_diagnostics?: { pooled_lstm_r2: number | null; macro_lstm_r2: number | null; median_series_lstm_r2: number | null; negative_series_r2_count: number; series_r2_count: number }
  interval_calibration?: { nominal_level_pct: number; method: string; global_radius: number; test_empirical_coverage_pct: number; series_calibrated_count?: number; warning: string }
  training_history?: Array<{ epoch: number; train_loss: number; validation_loss?: number; validation_mse?: number }>
  forecast_preview: ForecastSeries[]
  forecast_rows: number
  output_directory: string
  artifacts?: string[]
  notes: string[]
}

export type Job = {
  id: string
  dataset_id: string
  kind: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  stage: string
  config: Record<string, unknown>
  result: ForecastResult | null
  error: string | null
  created_at: string | null
  updated_at: string | null
}

export type DashboardOverview = {
  datasets: number
  total_rows: number
  total_columns: number
  latest_upload: string | null
  recent_datasets: Dataset[]
}
