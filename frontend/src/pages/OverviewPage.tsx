import type { ReactNode } from 'react'
import { Activity, AlertCircle, ArrowRight, ArrowUpRight, BarChart3, Boxes, BrainCircuit, ChevronRight, CloudUpload, CircleHelp, Database, FileSpreadsheet, Gauge, ShieldCheck, Sparkles, Target, TrendingUp, Upload, Zap } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PageHeading } from '../components/PageHeading'
import { formatDate, formatNumber } from '../lib/format'
import type { DashboardOverview, Dataset, Page } from '../types'

export function OverviewPage({ overview, datasets, loading, onUpload, onDemo, demoLoading, onNavigate, onSelect, onForecast }: {
  overview: DashboardOverview | null; datasets: Dataset[]; loading: boolean; onUpload: () => void; onDemo: () => void; demoLoading: boolean; onNavigate: (page: Page) => void; onSelect: (id: string) => void; onForecast: () => void
}) {
  const featured = datasets[0]
  const chartData = featured?.profile.time_series_preview ?? []
  const profile = featured?.profile
  return <>
    <PageHeading eyebrow="MARKET INTELLIGENCE / INDIA" title="Good afternoon, analyst." subtitle="Your commodity data, quality signals and forecasting experiments in one place."
      actions={<><button className="button button-secondary" onClick={onDemo} disabled={demoLoading}><Sparkles size={16} />{demoLoading ? 'Loading demo…' : 'Try demo data'}</button><button className="button button-primary" onClick={onUpload}><CloudUpload size={17} />Import dataset</button></>} />
    <section className="hero-banner">
      <div className="hero-grid" />
      <div className="hero-content"><div className="hero-label"><span className="hero-dot" /> YOUR MARKET DATA WORKSPACE</div><h2>Turn raw market data into<br /><em>decisions with direction.</em></h2><p>Upload a dataset. MandiCast will map its structure, surface quality issues and prepare a forecasting workflow around the columns it finds.</p><button className="hero-button" onClick={onUpload}>Explore your data <ArrowRight size={16} /></button></div>
      <div className="hero-visual" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core"><Activity size={30} /></div><div className="orbit-node node-one"><TrendingUp size={16} /></div><div className="orbit-node node-two"><Database size={16} /></div><div className="orbit-node node-three"><BrainCircuit size={16} /></div><div className="visual-caption">DATA → SIGNAL → FORECAST</div></div>
    </section>
    <div className="section-title-row"><div><h2>Workspace overview</h2><p>Coverage across your uploaded datasets</p></div><button className="text-button" onClick={() => onNavigate('datasets')}>View datasets <ArrowRight size={14} /></button></div>
    <section className="stat-grid">
      <StatCard icon={<Database size={18} />} label="Datasets" value={formatNumber(overview?.datasets ?? datasets.length)} foot="Uploaded sources" accent="blue" />
      <StatCard icon={<Boxes size={18} />} label="Total observations" value={formatNumber(overview?.total_rows ?? 0)} foot="Rows across all files" accent="violet" />
      <StatCard icon={<Target size={18} />} label="Data fields" value={formatNumber(overview?.total_columns ?? 0)} foot="Detected columns" accent="mint" />
      <StatCard icon={<ShieldCheck size={18} />} label="Workspace status" value={loading ? 'Loading' : 'Ready'} foot={featured ? `Latest upload · ${formatDate(featured.created_at)}` : 'Waiting for your first dataset'} accent="amber" />
    </section>
    <section className="dashboard-grid">
      <div className="panel chart-panel">
        <div className="panel-header"><div><div className="panel-kicker">DATA EXPLORER</div><h3>{featured ? `${profile?.target_column ?? 'Selected measure'} · trend preview` : 'Price movement overview'}</h3><p>{featured ? `${featured.filename} · ${profile?.time_series_label ?? 'representative series'} · ${profile?.date_range?.start ?? '—'} to ${profile?.date_range?.end ?? '—'}` : 'Upload a dataset to generate your first trend view.'}</p></div>{featured && <span className="tag tag-blue"><span />Auto-profiled</span>}</div>
        {chartData.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height={265}><AreaChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}><defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3B82F6" stopOpacity={0.22} /><stop offset="100%" stopColor="#3B82F6" stopOpacity={0.01} /></linearGradient></defs><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#E9EDF3" /><XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#929BAB' }} minTickGap={25} /><YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#929BAB' }} tickFormatter={(v: number) => new Intl.NumberFormat('en-IN', { notation: 'compact' }).format(v)} /><Tooltip contentStyle={{ border: '1px solid #E7EBF1', borderRadius: 12, boxShadow: '0 12px 34px #15223814', fontSize: 12 }} formatter={(value) => [formatNumber(Number(value)), profile?.target_column ?? 'Value']} labelFormatter={(label) => formatDate(String(label))} /><Area type="monotone" dataKey="value" stroke="#3978E8" strokeWidth={2.2} fill="url(#trendFill)" activeDot={{ r: 4, strokeWidth: 0 }} /></AreaChart></ResponsiveContainer></div> : <EmptyChart onUpload={onUpload} onDemo={onDemo} />}
        <div className="chart-bottom"><span><i className="legend-dot" /> Aggregated observations</span><button className="text-button" onClick={() => featured ? onSelect(featured.id) : onNavigate('datasets')}>Inspect dataset <ArrowUpRight size={14} /></button></div>
      </div>
      <div className="panel quality-panel">
        <div className="panel-header"><div><div className="panel-kicker">DATA HEALTH</div><h3>Quality snapshot</h3><p>{featured ? 'Signals from the most recent upload' : 'Quality indicators appear after upload'}</p></div><div className="quality-icon"><Gauge size={18} /></div></div>
        {profile ? <><div className="quality-score-row"><div><strong>{profile.quality_score}</strong><span>/ 100</span></div><span className={`quality-pill ${profile.quality_score >= 85 ? 'good' : profile.quality_score >= 65 ? 'moderate' : 'poor'}`}>{profile.quality_score >= 85 ? 'Healthy' : profile.quality_score >= 65 ? 'Review' : 'Needs attention'}</span></div><div className="quality-track"><span style={{ width: `${profile.quality_score}%` }} /></div><div className="quality-list"><QualityLine label="Missing cells" value={`${profile.missing_pct.toFixed(1)}%`} tone={profile.missing_pct > 20 ? 'warning' : 'good'} /><QualityLine label="Duplicate rows" value={formatNumber(profile.duplicate_rows)} tone={profile.duplicate_rows ? 'warning' : 'good'} /><QualityLine label="Detected columns" value={formatNumber(profile.columns_count)} tone="neutral" /><QualityLine label="Forecast readiness" value={profile.task_type === 'time_series_forecasting' ? 'Auto-detected' : (profile.numeric_columns.length ? 'Manual mapping' : 'Needs numeric measure')} tone={profile.task_type === 'time_series_forecasting' ? 'good' : 'warning'} /></div>{profile.warnings.length > 0 && <div className="quality-note"><AlertCircle size={14} /><span>{profile.warnings.length} data quality note{profile.warnings.length > 1 ? 's' : ''} to review</span></div>}</> : <div className="empty-quality"><ShieldCheck size={30} /><strong>No dataset to inspect</strong><span>Import a file to see missingness, duplicates and forecast readiness.</span><button className="button button-secondary button-small" onClick={onUpload}>Import a dataset</button></div>}
      </div>
    </section>
    <section className="bottom-grid">
      <div className="panel recent-panel"><div className="panel-header"><div><div className="panel-kicker">YOUR SOURCES</div><h3>Recent datasets</h3></div><button className="icon-button" onClick={() => onNavigate('datasets')}><ArrowUpRight size={16} /></button></div>{datasets.length ? <div className="recent-list">{datasets.slice(0, 4).map((item) => <button className="recent-item" key={item.id} onClick={() => onSelect(item.id)}><div className="file-icon"><FileSpreadsheet size={18} /></div><div className="recent-copy"><strong>{item.filename}</strong><span>{formatNumber(item.row_count)} rows · {item.column_count} fields · {formatDate(item.created_at)}</span></div><span className="type-chip">{item.file_type.toUpperCase()}</span><ChevronRight size={16} className="muted-icon" /></button>)}</div> : <div className="compact-empty"><span>Your workspace is empty.</span><button className="text-button" onClick={onUpload}>Upload your first file <ArrowRight size={13} /></button></div>}</div>
      <div className="panel quick-panel"><div className="panel-header"><div><div className="panel-kicker">NEXT STEPS</div><h3>Continue building</h3></div><div className="quick-spark"><Zap size={17} /></div></div><div className="quick-actions"><button onClick={onUpload}><div className="quick-icon quick-blue"><Upload size={17} /></div><div><strong>Profile a new dataset</strong><span>Detect schema, data types and quality</span></div><ArrowRight size={15} /></button><button onClick={onForecast}><div className="quick-icon quick-violet"><BrainCircuit size={17} /></div><div><strong>Open forecast lab</strong><span>Train and benchmark an LSTM model</span></div><ArrowRight size={15} /></button><button onClick={() => onNavigate('guide')}><div className="quick-icon quick-amber"><CircleHelp size={17} /></div><div><strong>Prepare your data</strong><span>Review supported columns and formats</span></div><ArrowRight size={15} /></button></div></div>
    </section>
  </>
}

function StatCard({ icon, label, value, foot, accent }: { icon: ReactNode; label: string; value: string; foot: string; accent: string }) {
  return <div className="stat-card"><div className={`stat-icon ${accent}`}>{icon}</div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-foot">{foot}</div></div>
}
function QualityLine({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className="quality-line"><span>{label}</span><strong>{value}</strong><i className={`quality-dot ${tone}`} /></div>
}
function EmptyChart({ onUpload, onDemo }: { onUpload: () => void; onDemo: () => void }) {
  return <div className="empty-chart"><div className="empty-chart-grid"><div /><div /><div /><div /></div><div className="empty-chart-content"><div className="chart-empty-icon"><BarChart3 size={23} /></div><strong>Your first market trend starts here</strong><span>Import a CSV, Excel, JSON or Parquet file and the workspace will identify its time and measure columns.</span><div><button className="button button-primary button-small" onClick={onUpload}><Upload size={14} />Upload dataset</button><button className="button button-ghost button-small" onClick={onDemo}>Use demo</button></div></div></div>
}

