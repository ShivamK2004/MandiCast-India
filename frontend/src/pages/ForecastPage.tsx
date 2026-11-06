import { useEffect, useState } from 'react'
import { AlertCircle, BrainCircuit, Check, CheckCircle2, Database, FileSpreadsheet, LoaderCircle, Plus, Settings2, ShieldCheck, Target, TrendingUp, Upload, Zap } from 'lucide-react'
import { PageHeading } from '../components/PageHeading'
import { formatDate, formatNumber } from '../lib/format'
import type { Dataset, Job } from '../types'

export function ForecastPage({ dataset, currentJob, onStart, onUpload }: { dataset: Dataset | null; currentJob: Job | null; onStart: (config: { target_column: string; date_column: string; group_columns: string[]; horizon: number; lookback: number; epochs: number; batch_size: number; hidden_size: number }) => Promise<void>; onUpload: () => void }) {
  const profile = dataset?.profile
  const [target, setTarget] = useState(profile?.target_column ?? '')
  const [date, setDate] = useState(profile?.date_column ?? '')
  const [groups, setGroups] = useState<string[]>(profile?.group_columns ?? [])
  const [horizon, setHorizon] = useState(7)
  const [lookback, setLookback] = useState(21)
  const [epochs, setEpochs] = useState(25)
  const [submitting, setSubmitting] = useState(false)
  useEffect(() => { setTarget(profile?.target_column ?? ''); setDate(profile?.date_column ?? ''); setGroups(profile?.group_columns ?? []) }, [dataset?.id])
  const numericColumns = profile?.numeric_columns ?? []
  const groupOptions = profile?.categorical_columns ?? []
  const ready = Boolean(dataset && target && date && target !== date)
  const isBusy = currentJob?.status === 'queued' || currentJob?.status === 'running'

  const submit = async () => {
    if (!ready || submitting || isBusy) return
    setSubmitting(true)
    try { await onStart({ target_column: target, date_column: date, group_columns: groups, horizon, lookback, epochs, batch_size: 128, hidden_size: 48 }) }
    finally { setSubmitting(false) }
  }
  return <>
    <PageHeading eyebrow="PREDICTIVE WORKSPACE" title="Forecast lab" subtitle="Configure a time-series experiment from the columns detected in your dataset. Compare deep learning with transparent baselines." actions={<span className="tag tag-purple"><BrainCircuit size={13} />LSTM experiment</span>} />
    {!dataset ? <div className="panel no-dataset-card"><div className="no-dataset-icon"><Database size={26} /></div><h3>Start with a dataset</h3><p>Upload a CSV, Excel, JSON or Parquet file. MandiCast will infer its date, numeric target and group dimensions.</p><button className="button button-primary" onClick={onUpload}><Upload size={16} />Import a dataset</button></div> : <div className="forecast-layout">
      <div className="panel forecast-config-panel"><div className="panel-header"><div><div className="panel-kicker">EXPERIMENT CONFIGURATION</div><h3>Define your forecasting task</h3><p>Auto-detected choices are pre-selected. You can change them before training.</p></div><span className="step-number">01</span></div>
        <div className="source-card"><div className="source-symbol"><FileSpreadsheet size={18} /></div><div><strong>{dataset.filename}</strong><span>{formatNumber(dataset.row_count)} observations · {dataset.column_count} fields</span></div><span className="source-ready"><CheckCircle2 size={13} />Loaded</span></div>
        <div className="form-section"><div className="form-section-heading"><span>01</span><div><strong>Time-series mapping</strong><small>Tell the model what to predict and in what order.</small></div></div>
          <div className="form-grid"><label className="field-label">Target measure<select value={target} onChange={(event) => setTarget(event.target.value)}><option value="">Choose a numeric measure</option>{numericColumns.map((column) => <option key={column} value={column}>{column}</option>)}</select><small>Numeric value to forecast</small></label><label className="field-label">Date / time column<select value={date} onChange={(event) => setDate(event.target.value)}><option value="">Choose a date/time field</option>{(profile?.column_profiles ?? []).map((column) => <option key={column.name} value={column.name}>{column.name} · {column.inferred_type}{column.date_parse_pct > 0 ? ` · ${column.date_parse_pct}% date parse` : ''}</option>)}</select><small>Auto-detected candidates are shown with their type; any field can be selected and validated by the API.</small></label></div>
          <label className="field-label group-select-label">Series dimensions <span className="optional-tag">OPTIONAL</span><small>Separate independent series by market, commodity, region, product or another categorical dimension.</small></label>
          <div className="group-chip-list">{groupOptions.map((column) => <button key={column} className={`group-chip ${groups.includes(column) ? 'selected' : ''}`} onClick={() => setGroups((current) => current.includes(column) ? current.filter((item) => item !== column) : current.length < 8 ? [...current, column] : current)}><span>{groups.includes(column) ? <Check size={12} /> : <Plus size={12} />}</span>{column}</button>)}{!groupOptions.length && <span className="field-hint">No categorical grouping fields were detected.</span>}</div>
          {groupOptions.length > 0 && groups.length === 0 && <div className="inline-warning"><AlertCircle size={14} />No series dimensions are selected. Records on the same date will be averaged into one series; for multi-market or multi-commodity data, keep the relevant dimensions selected.</div>}
        </div>
        <div className="form-divider" />
        <div className="form-section"><div className="form-section-heading"><span>02</span><div><strong>Forecast settings</strong><small>Control the lookback window and forecast length.</small></div></div>
          <div className="range-grid"><label className="range-field"><span>Forecast horizon <strong>{horizon} steps</strong></span><input type="range" min="1" max="30" value={horizon} onChange={(event) => setHorizon(Number(event.target.value))} /><small>Predictions beyond the latest observation</small></label><label className="range-field"><span>Lookback window <strong>{lookback} steps</strong></span><input type="range" min="5" max="60" step="1" value={lookback} onChange={(event) => setLookback(Number(event.target.value))} /><small>Historical observations per sequence</small></label></div>
          <div className="advanced-settings"><div><Settings2 size={15} /><strong>Training controls</strong><span>Advanced</span></div><label className="epochs-control">Epochs <select value={epochs} onChange={(event) => setEpochs(Number(event.target.value))}><option value={10}>10 · quick</option><option value={25}>25 · balanced</option><option value={50}>50 · extended</option><option value={100}>100 · deep</option></select></label></div>
        </div>
        <div className="forecast-action"><div><ShieldCheck size={15} /><span>Chronological split · train-only scaling · benchmark comparison</span></div><button className="button button-primary" onClick={() => void submit()} disabled={!ready || submitting || isBusy}>{submitting || isBusy ? <><LoaderCircle className="spin" size={16} />Running…</> : <><Zap size={16} />Run experiment</>}</button></div>
        {!ready && <div className="inline-warning"><AlertCircle size={14} />Choose different columns or confirm a date/time field and a numeric measure. Manual mapping is available when automatic detection is uncertain.</div>}
      </div>
      <div className="forecast-aside"><div className="panel experiment-info"><div className="panel-kicker">MODEL BLUEPRINT</div><h3>Attention-pooled residual LSTM</h3><p>One shared recurrent model learns price changes across the selected groups.</p><div className="blueprint-flow"><div><span className="blueprint-icon"><Database size={15} /></span><div><strong>Panel sequences</strong><small>{groups.length ? groups.join(' × ') : 'Single time series'}</small></div></div><div className="flow-line" /><div><span className="blueprint-icon violet"><BrainCircuit size={15} /></span><div><strong>LSTM encoder</strong><small>Lookback window · {lookback} steps</small></div></div><div className="flow-line" /><div><span className="blueprint-icon green"><TrendingUp size={15} /></span><div><strong>Residual forecast</strong><small>Predict Δ target, add to last value</small></div></div></div><div className="benchmark-note"><Target size={15} /><span>Every run is evaluated against last-value and moving-average baselines.</span></div></div>
        <div className="panel data-context"><div className="panel-kicker">DETECTED DATA CONTEXT</div><h3>Dataset readiness</h3><div className="context-line"><span>Time range</span><strong>{profile?.date_range ? `${formatDate(profile.date_range.start)} — ${formatDate(profile.date_range.end)}` : 'Unknown'}</strong></div><div className="context-line"><span>Numeric measures</span><strong>{numericColumns.length}</strong></div><div className="context-line"><span>Group dimensions</span><strong>{groupOptions.length}</strong></div><div className="context-line"><span>Data quality</span><strong>{profile?.quality_score ?? 0}/100</strong></div></div>
      </div>
    </div>}
  </>
}

