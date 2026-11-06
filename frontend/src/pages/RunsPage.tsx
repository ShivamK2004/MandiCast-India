import { useMemo } from 'react'
import { Activity, AlertCircle, BrainCircuit, CheckCircle2, ChevronRight, Download, FileCheck2 } from 'lucide-react'
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { artifactUrl } from '../api/client'
import { PageHeading } from '../components/PageHeading'
import { formatDate, formatNumber, metric } from '../lib/format'
import type { ForecastMetrics, GroupMetricRow, Job } from '../types'

export function RunsPage({ jobs, currentJob, onSelectJob }: {
  jobs: Job[]
  currentJob: Job | null
  onSelectJob: (job: Job) => void
}) {
  const allJobs = useMemo(() => {
    const rows = [...jobs]
    if (currentJob && !rows.some((job) => job.id === currentJob.id)) rows.unshift(currentJob)
    return rows
  }, [jobs, currentJob])

  // Keep the selected run selected even while queued/running/failed. Never show a
  // different run's completed result as a fallback for the selected run.
  const active = currentJob ?? allJobs.find((job) => job.result) ?? null
  const result = active?.result
  const series = result?.forecast_preview?.[0]
  const chartData = series ? [
    ...series.history.slice(-35).map((point) => ({
      label: point.date, actual: point.actual, forecast: null as number | null,
      lower_90: null as number | null, upper_90: null as number | null,
    })),
    ...series.forecast.map((point) => ({
      label: `+${point.step}`, actual: null as number | null, forecast: point.forecast_price,
      lower_90: point.lower_90 ?? null, upper_90: point.upper_90 ?? null,
    })),
  ] : []
  const history = result?.training_history ?? []
  const bestBenchmark = result?.best_benchmark ?? 'Unavailable'
  const improvementVsNaive = result?.lstm_mae_improvement_vs_naive_pct
  const improvementVsBest = result?.lstm_mae_improvement_vs_best_benchmark_pct
  const r2 = result?.r2_diagnostics
  const targetUnit = result?.target_unit && result.target_unit !== 'Unit not specified'
    ? ` · ${result.target_unit}` : ''
  const pctLabel = (value: number | null | undefined) =>
    value == null ? 'Unavailable' : `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  const groupRows = result?.test_by_group ?? {}
  const fmtMetric = (metrics: ForecastMetrics | undefined, key: keyof ForecastMetrics) =>
    metric(metrics?.[key] as number | null | undefined)

  return <>
    <PageHeading
      eyebrow="EXPERIMENT TRACKING"
      title="Model runs"
      subtitle="Follow training jobs, compare held-out metrics and inspect run-specific forecast artifacts."
      actions={<span className="tag tag-blue"><Activity size={13} />{allJobs.length} total runs</span>}
    />

    {active && !result && <section className="panel selected-run-state">
      {active.status === 'failed' ? <AlertCircle size={20} /> : <Activity size={20} />}
      <div>
        <strong>{active.status === 'failed' ? 'Selected experiment failed' : `Experiment ${active.status}`}</strong>
        <p>{active.error ?? active.stage}. {active.status === 'running' || active.status === 'queued' ? `${active.progress}% complete.` : 'Select another completed run to inspect its results.'}</p>
      </div>
    </section>}

    {active && result && <>
      <section className="run-result-header">
        <div>
          <div className="run-complete"><CheckCircle2 size={15} /> Completed experiment</div>
          <h2>Forecast evaluation</h2>
          <p>{result.target_column}{targetUnit} · {formatNumber(result.rows_used)} observations · {result.series_count} series · {result.device.toUpperCase()}</p>
          <p className="run-id-line">Run ID: {result.experiment_id ?? active.id} · Dataset: {active.dataset_id.slice(0, 8)}</p>
        </div>
        <div className="baseline-winner">
          <span>Best benchmark (excluding LSTM)</span>
          <strong>{bestBenchmark}</strong>
          <small>LSTM vs naive: {pctLabel(improvementVsNaive)}</small>
          <small>LSTM vs best benchmark: {pctLabel(improvementVsBest)}</small>
          <small>Best overall by MAE: {result.best_model ?? 'Unavailable'}</small>
        </div>
      </section>

      <section className="metric-result-grid">
        <MetricResult label="LSTM · Pooled MAE" value={metric(result.test_lstm.MAE)} helper={`Across all test rows${targetUnit}`} />
        <MetricResult label="Naive · Pooled MAE" value={metric(result.test_naive.MAE)} helper={`Last observed value${targetUnit}`} />
        <MetricResult label="Moving average · Pooled MAE" value={metric(result.test_moving_average.MAE)} helper={`Seven-observation mean${targetUnit}`} />
        <MetricResult label="LSTM · Pooled RMSE" value={metric(result.test_lstm.RMSE)} helper={`Across all test rows${targetUnit}`} />
        <MetricResult label="LSTM · Macro R²" value={metric(result.test_macro?.LSTM?.R2)} helper="Unweighted average across series" />
      </section>

      <section className="run-visual-grid">
        <div className="panel run-chart-panel">
          <div className="panel-header">
            <div><div className="panel-kicker">FORECAST VISUALISATION</div><h3>Recent history + projected steps</h3><p>Illustrative first series · bounds are indicative validation-residual intervals.</p></div>
            <span className="tag tag-purple">{result.horizon}-step horizon</span>
          </div>
          {chartData.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#E9EDF3" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: '#929BAB' }} minTickGap={25} />
              <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#929BAB' }} />
              <Tooltip contentStyle={{ border: '1px solid #E7EBF1', borderRadius: 12, fontSize: 12 }} />
              <ReferenceLine x={series?.history.at(-1)?.date} stroke="#ADB7C7" strokeDasharray="4 4" label={{ value: 'Forecast starts', position: 'insideTopRight', fontSize: 10, fill: '#8A94A5' }} />
              <Line type="monotone" dataKey="actual" name="Historical actual" stroke="#377CE8" strokeWidth={2.1} dot={false} connectNulls />
              <Line type="monotone" dataKey="forecast" name="LSTM forecast" stroke="#13A58B" strokeWidth={2.4} strokeDasharray="6 4" dot={{ r: 3, fill: '#13A58B' }} connectNulls />
              <Line type="monotone" dataKey="lower_90" name="Indicative lower 90% bound" stroke="#98A5B7" strokeWidth={1.2} strokeDasharray="3 4" dot={false} connectNulls />
              <Line type="monotone" dataKey="upper_90" name="Indicative upper 90% bound" stroke="#98A5B7" strokeWidth={1.2} strokeDasharray="3 4" dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer></div> : <div className="list-empty">No forecast series available.</div>}
          <div className="chart-legend"><span><i className="legend-dot" />Historical observations</span><span><i className="legend-dot forecast-dot" />Model forecast</span><span><i className="legend-dot interval-dot" />Indicative interval</span></div>
        </div>
        <div className="panel run-details-panel">
          <div className="panel-kicker">RUN DETAILS</div><h3>Experiment summary</h3>
          <div className="run-detail-lines">
            <div><span>Target</span><strong>{result.target_column}</strong></div>
            <div><span>Target unit</span><strong>{result.target_unit ?? 'Not specified'}</strong></div>
            <div><span>Date field</span><strong>{result.date_column}</strong></div>
            <div><span>Series count</span><strong>{result.series_count}</strong></div>
            <div><span>Lookback</span><strong>{result.lookback} steps</strong></div>
            <div><span>Epochs trained</span><strong>{result.epochs_trained}</strong></div>
            <div><span>Best validation epoch</span><strong>{result.best_epoch ?? (history.length ? history.reduce((best, row) => (row.validation_loss ?? Number.POSITIVE_INFINITY) < (best.validation_loss ?? Number.POSITIVE_INFINITY) ? row : best).epoch : '—')}</strong></div>
            <div><span>Training device</span><strong>{result.device}</strong></div>
            <div><span>Train cutoff</span><strong>{formatDate(result.train_cutoff)}</strong></div>
          </div>
          <div className="run-note"><AlertCircle size={15} /><span>Forecast steps represent next observed records, not guaranteed calendar days.</span></div>
          {result.dataset_sha256 && <div className="hash-note"><FileCheck2 size={14} /><span>Dataset SHA-256: {result.dataset_sha256.slice(0, 18)}…</span></div>}
        </div>
      </section>

      {history.length > 0 && <section className="panel run-chart-panel" style={{ marginBottom: 14 }}>
        <div className="panel-header"><div><div className="panel-kicker">TRAINING DIAGNOSTICS</div><h3>Training vs validation loss</h3><p>Best checkpoint is selected using validation Huber loss.</p></div><span className="subtle-count">{history.length} epochs</span></div>
        <div className="chart-wrap"><ResponsiveContainer width="100%" height={230}><LineChart data={history} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#E9EDF3" />
          <XAxis dataKey="epoch" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: '#929BAB' }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#929BAB' }} />
          <Tooltip contentStyle={{ border: '1px solid #E7EBF1', borderRadius: 12, fontSize: 12 }} />
          <Line type="monotone" dataKey="train_loss" name="Training loss" stroke="#377CE8" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="validation_loss" name="Validation loss" stroke="#13A58B" strokeWidth={2} dot={false} />
        </LineChart></ResponsiveContainer></div>
      </section>}


      {result.test_macro && <section className="panel group-metrics-panel">
        <div className="panel-header"><div><div className="panel-kicker">MACRO-AVERAGED MODEL COMPARISON</div><h3>Average performance per series</h3><p>Each series receives equal weight, regardless of its number of test observations. MAE/RMSE retain the dataset's native target unit.</p></div></div>
        <div className="dataset-table-wrap"><table className="data-table"><thead><tr><th>MODEL</th><th>MACRO MAE</th><th>MACRO RMSE</th><th>MACRO MAPE</th><th>MACRO R²</th></tr></thead><tbody>
          {(['LSTM', 'Naive last value', 'Moving average (7)'] as const).map((modelName) => {
            const values = result.test_macro?.[modelName]
            return <tr key={modelName}><td>{modelName}</td><td>{fmtMetric(values, 'MAE')}</td><td>{fmtMetric(values, 'RMSE')}</td><td>{values?.MAPE_pct == null ? '—' : `${metric(values.MAPE_pct)}%`}</td><td>{fmtMetric(values, 'R2')}</td></tr>
          })}
        </tbody></table></div>
      </section>}

      {r2 && <section className="panel evaluation-note-panel">
        <div className="panel-header"><div><div className="panel-kicker">R² INTERPRETATION</div><h3>Pooled vs per-series fit</h3><p>Pooled R² can be inflated by differences in price levels between markets and commodities.</p></div></div>
        <div className="r2-diagnostic-grid">
          <MetricResult label="Pooled LSTM R²" value={metric(r2.pooled_lstm_r2)} helper="All test observations pooled" />
          <MetricResult label="Mean per-series R²" value={metric(r2.macro_lstm_r2)} helper="Unweighted series average" />
          <MetricResult label="Median per-series R²" value={metric(r2.median_series_lstm_r2)} helper="Middle series result" />
          <MetricResult label="Negative per-series R²" value={`${r2.negative_series_r2_count}/${r2.series_r2_count}`} helper="Series where mean baseline wins on SSE" />
        </div>
        <p className="evaluation-caveat">Interpret pooled R² together with the macro and per-series metrics. Negative per-series R² is possible when a series is difficult to predict or has little variation; it is not hidden by the pooled score.</p>
      </section>}

      {Object.keys(groupRows).length > 0 && <section className="panel group-metrics-panel">
        <div className="panel-header"><div><div className="panel-kicker">BUSINESS-LEVEL EVALUATION</div><h3>Performance by commodity and market dimensions</h3><p>Metrics are computed on held-out test observations within each category value.</p></div></div>
        {Object.entries(groupRows).map(([dimension, rows]) => <div className="group-metric-block" key={dimension}>
          <h4>{dimension}</h4>
          <div className="dataset-table-wrap"><table className="data-table"><thead><tr><th>VALUE</th><th>SERIES</th><th>TEST ROWS</th><th>LSTM MAE</th><th>NAIVE MAE</th><th>MA(7) MAE</th><th>Pooled LSTM R²</th></tr></thead>
            <tbody>{(rows as GroupMetricRow[]).map((row) => <tr key={`${dimension}-${row.value}`}>
              <td>{row.value}</td><td>{row.series_count}</td><td>{row.observations}</td>
              <td>{fmtMetric(row.LSTM, 'MAE')}</td><td>{fmtMetric(row['Naive last value'], 'MAE')}</td><td>{fmtMetric(row['Moving average (7)'], 'MAE')}</td><td>{fmtMetric(row.LSTM, 'R2')}</td>
            </tr>)}</tbody></table></div>
        </div>)}
        {result.unit_comparability_status !== 'consistent_declared' && <p className="evaluation-caveat">{result.unit_comparability_status === 'mixed_declared' ? 'The dataset contains multiple measurement units. Do not rank cross-unit absolute MAE values; compare within a consistent unit.' : 'No measurement unit was declared in the dataset. Verify unit consistency before comparing absolute error values across series.'}</p>}
      </section>}

      {result.interval_calibration && <section className="panel interval-panel">
        <div className="panel-kicker">FORECAST UNCERTAINTY</div><h3>Indicative 90% prediction intervals</h3>
        <p>Test empirical coverage: <strong>{metric(result.interval_calibration.test_empirical_coverage_pct, '%')}</strong> · Validation-calibrated series: <strong>{result.interval_calibration.series_calibrated_count ?? 0}</strong></p>
        <p className="evaluation-caveat">{result.interval_calibration.warning}</p>
      </section>}

      <div className="panel forecast-table-panel">
        <div className="panel-header"><div><div className="panel-kicker">GENERATED OUTPUT</div><h3>Forecast preview</h3><p>First available series. Lower/upper values are indicative bands.</p></div><span className="subtle-count">{formatNumber(result.forecast_rows)} forecast rows</span></div>
        <div className="artifact-actions">
          <a className="button button-secondary button-small" href={artifactUrl(active.id, 'forecasts.csv')} download><Download size={14} />Forecasts CSV</a>
          <a className="button button-secondary button-small" href={artifactUrl(active.id, 'test_predictions.csv')} download><Download size={14} />Test predictions</a>
          <a className="button button-ghost button-small" href={artifactUrl(active.id, 'training_history.csv')} download><Download size={14} />Training history</a>
          <a className="button button-ghost button-small" href={artifactUrl(active.id, 'series_metrics.csv')} download><Download size={14} />Series metrics</a>
          <a className="button button-ghost button-small" href={artifactUrl(active.id, 'group_metrics.csv')} download><Download size={14} />Group metrics</a>
          <a className="button button-ghost button-small" href={artifactUrl(active.id, 'result.json')} download><Download size={14} />Result JSON</a>
          <a className="button button-ghost button-small" href={artifactUrl(active.id, 'run_manifest.json')} download><Download size={14} />Run manifest</a>
        </div>
        <div className="dataset-table-wrap"><table className="data-table"><thead><tr><th>SERIES</th><th>STEP</th><th>FORECAST</th><th>LOWER 90%</th><th>UPPER 90%</th></tr></thead><tbody>{result.forecast_preview.slice(0, 3).flatMap((item, index) => item.forecast.map((point) => <tr key={`${index}-${point.step}`}><td>{Object.values(item.series).join(' · ') || 'All observations'}</td><td>+{point.step}</td><td className="value-cell">{formatNumber(point.forecast_price)}</td><td>{formatNumber(point.lower_90)}</td><td>{formatNumber(point.upper_90)}</td></tr>))}</tbody></table></div>
      </div>
    </>}

    <div className="panel jobs-panel"><div className="panel-header"><div><div className="panel-kicker">JOB QUEUE</div><h3>Recent experiments</h3></div><span className="subtle-count">{allJobs.length} runs</span></div>
      {allJobs.length ? <div className="jobs-list">{allJobs.map((job) => <button className={`job-row ${active?.id === job.id ? 'job-active' : ''}`} key={job.id} onClick={() => onSelectJob(job)}>
        <div className={`job-icon ${job.status}`}><BrainCircuit size={18} /></div>
        <div className="job-info"><strong>{job.config.target_column ? `Forecast · ${String(job.config.target_column)}` : 'Forecast experiment'}</strong><span>{job.id.slice(0, 8)} · {formatDate(job.created_at)} · {job.stage}</span>{job.status === 'running' || job.status === 'queued' ? <div className="job-progress"><span style={{ width: `${job.progress}%` }} /></div> : null}</div>
        <span className={`status-chip ${job.status}`}>{job.status}</span><ChevronRight size={16} className="muted-icon" />
      </button>)}</div> : <div className="compact-empty"><span>No experiments have been run yet.</span><span>Open Forecast lab to launch your first experiment.</span></div>}
    </div>
  </>
}

function MetricResult({ label, value, helper }: { label: string; value: string; helper: string }) {
  return <div className="metric-result"><span>{label}</span><strong>{value}</strong><small>{helper}</small></div>
}
