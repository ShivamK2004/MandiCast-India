import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, AlertCircle, ArrowUpRight, Bell, BrainCircuit, CheckCircle2,
  ChevronRight, CircleHelp, Command, Database,
  Clock3, LayoutDashboard, Menu, RefreshCw, Sparkles, X,
  type LucideIcon,
} from 'lucide-react'
import { api } from './api/client'
import { OverviewPage } from './pages/OverviewPage'
import { DatasetsPage } from './pages/DatasetsPage'
import { ForecastPage } from './pages/ForecastPage'
import { RunsPage } from './pages/RunsPage'
import { GuidePage } from './pages/GuidePage'
import { formatNumber } from './lib/format'
import type { DashboardOverview, Dataset, Job, Page } from './types'

const navItems: { id: Page; label: string; section: string; icon: LucideIcon }[] = [
  { id: 'overview', label: 'Overview', section: 'WORKSPACE', icon: LayoutDashboard },
  { id: 'datasets', label: 'Datasets', section: 'WORKSPACE', icon: Database },
  { id: 'forecast', label: 'Forecast lab', section: 'MODELLING', icon: BrainCircuit },
  { id: 'runs', label: 'Model runs', section: 'MODELLING', icon: Activity },
  { id: 'guide', label: 'Data guide', section: 'RESOURCES', icon: CircleHelp },
]

function App() {
  const [page, setPage] = useState<Page>('overview')
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [preview, setPreview] = useState<{ columns: string[]; rows: Record<string, unknown>[]; total_rows: number } | null>(null)
  const [currentJob, setCurrentJob] = useState<Job | null>(null)
  const [apiOnline, setApiOnline] = useState(false)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [toast, setToast] = useState<{ tone: 'success' | 'error' | 'info'; message: string } | null>(null)
  const [search, setSearch] = useState('')
  const [mobileNav, setMobileNav] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const activeDataset = useMemo(() => datasets.find((item) => item.id === selectedId) ?? datasets[0] ?? null, [datasets, selectedId])

  const refreshWorkspace = useCallback(async () => {
    try {
      const health = await api.health()
      setApiOnline(health.status === 'ok')
    } catch (error) {
      setApiOnline(false)
      setToast({ tone: 'error', message: error instanceof Error ? error.message : 'Could not connect to the API.' })
      setLoading(false)
      return
    }

    try {
      const [data, datasetRows, jobRows] = await Promise.all([api.overview(), api.datasets(), api.jobs()])
      setOverview(data)
      setDatasets(datasetRows)
      setJobs(jobRows)
      setSelectedId((old) => old && datasetRows.some((item) => item.id === old) ? old : datasetRows[0]?.id ?? '')
    } catch (error) {
      setToast({ tone: 'error', message: error instanceof Error ? error.message : 'Could not connect to the API.' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refreshWorkspace() }, [refreshWorkspace])

  useEffect(() => {
    if (apiOnline) return
    const timer = window.setInterval(() => {
      void api.health()
        .then((health) => {
          if (health.status === 'ok') void refreshWorkspace()
        })
        .catch(() => {
          // Keep the disconnected state while the API is unavailable; retry on the next interval.
        })
    }, 5000)
    return () => window.clearInterval(timer)
  }, [apiOnline, refreshWorkspace])

  useEffect(() => {
    if (!selectedId || page !== 'datasets') return
    api.preview(selectedId).then(setPreview).catch(() => setPreview(null))
  }, [selectedId, page])

  useEffect(() => {
    if (!currentJob?.id || !['queued', 'running'].includes(currentJob.status)) return
    const timer = window.setTimeout(() => {
      api.job(currentJob.id)
        .then((job) => {
          setCurrentJob(job)
          if (job.status === 'completed' || job.status === 'failed') {
            void refreshWorkspace()
            if (job.status === 'completed') setToast({ tone: 'success', message: 'Forecast run completed. Results are ready.' })
            else setToast({ tone: 'error', message: job.error ?? 'Forecast run failed.' })
          }
        })
        .catch((error) => setToast({ tone: 'error', message: error instanceof Error ? error.message : 'Could not refresh job status.' }))
    }, 1800)
    return () => window.clearTimeout(timer)
  }, [currentJob, refreshWorkspace])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 4200)
    return () => window.clearTimeout(timer)
  }, [toast])

  const handleUpload = async (file?: File) => {
    if (!file) return
    setUploading(true)
    try {
      const dataset = await api.upload(file)
      await refreshWorkspace()
      setSelectedId(dataset.id)
      setPage('datasets')
      setToast({ tone: 'success', message: `Profiled ${dataset.filename}: ${formatNumber(dataset.row_count)} rows and ${dataset.column_count} columns detected.` })
    } catch (error) {
      setToast({ tone: 'error', message: error instanceof Error ? error.message : 'Upload failed.' })
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const handleDemo = async () => {
    setDemoLoading(true)
    try {
      const dataset = await api.demo()
      await refreshWorkspace()
      setSelectedId(dataset.id)
      setPage('datasets')
      setToast({ tone: 'success', message: 'Synthetic India mandi demo dataset added. It is for product demonstration, not market reporting.' })
    } catch (error) {
      setToast({ tone: 'error', message: error instanceof Error ? error.message : 'Could not load demo data.' })
    } finally { setDemoLoading(false) }
  }

  const removeDataset = async (id: string) => {
    if (!window.confirm('Delete this dataset and its uploaded source file?')) return
    try {
      await api.removeDataset(id)
      await refreshWorkspace()
      setPreview(null)
      setToast({ tone: 'success', message: 'Dataset deleted.' })
    } catch (error) {
      setToast({ tone: 'error', message: error instanceof Error ? error.message : 'Delete failed.' })
    }
  }

  const startRun = async (config: {
    target_column: string; date_column: string; group_columns: string[]
    horizon: number; lookback: number; epochs: number; batch_size: number; hidden_size: number
  }) => {
    if (!activeDataset) return
    try {
      const job = await api.startForecast(activeDataset.id, config)
      setCurrentJob(job)
      setPage('runs')
      setToast({ tone: 'info', message: 'Forecast job queued. You can follow progress in Model runs.' })
      void refreshWorkspace()
    } catch (error) {
      setToast({ tone: 'error', message: error instanceof Error ? error.message : 'Could not start forecast.' })
    }
  }

  const navigate = (next: Page) => { setPage(next); setMobileNav(false) }

  return (
    <div className="app-shell">
      <input ref={fileInput} type="file" accept=".csv,.xlsx,.xls,.json,.jsonl,.parquet" hidden onChange={(event) => void handleUpload(event.target.files?.[0])} />
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><span /><span /><span /><span /></div>
          <div><div className="brand-name">mandicast<span>.</span></div><div className="brand-sub">INDIA MARKET INTELLIGENCE</div></div>
          <button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="workspace-select">
          <div className="workspace-avatar"><Command size={17} /></div>
          <div className="workspace-copy"><strong>Research workspace</strong><span>Personal environment</span></div>
        </div>
        <nav className="side-nav">
          {navItems.map((item, index) => {
            const Previous = navItems[index - 1]
            const showSection = !Previous || Previous.section !== item.section
            const Icon = item.icon
            return <div key={item.id}>
              {showSection && <div className="nav-section-label">{item.section}</div>}
              <button className={`nav-link ${page === item.id ? 'active' : ''}`} onClick={() => navigate(item.id)}>
                <Icon size={17} strokeWidth={1.9} /><span>{item.label}</span>
                {item.id === 'runs' && jobs.some((job) => job.status === 'running' || job.status === 'queued') && <span className="nav-pulse" />}
                {item.id === 'datasets' && datasets.length > 0 && <span className="nav-count">{datasets.length}</span>}
              </button>
            </div>
          })}
        </nav>
        <div className="sidebar-spacer" />
        <div className="side-callout">
          <div className="callout-icon"><Sparkles size={16} /></div>
          <strong>Bring your own data</strong>
          <p>Auto-detect date, measure and market dimensions from your files.</p>
          <button onClick={() => fileInput.current?.click()}>Upload dataset <ArrowUpRight size={14} /></button>
        </div>
        <div className="sidebar-footer">
          <div className="avatar">MK</div>
          <div className="profile-copy"><strong>Market analyst</strong><span>Local workspace</span></div>
        </div>
      </aside>
      {mobileNav && <button className="nav-backdrop" aria-label="Close menu" onClick={() => setMobileNav(false)} />}

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={19} /></button>
            <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><strong>{navItems.find((item) => item.id === page)?.label}</strong></div>
          </div>
          <div className="topbar-right">
            <div className={`system-status ${apiOnline ? 'online' : 'offline'}`}><span />{apiOnline ? 'API connected' : 'API disconnected'}</div>
            <button className="icon-button" title="Refresh workspace" onClick={() => void refreshWorkspace()}><RefreshCw size={17} /></button>
            <button className="icon-button notification-button" title="View model runs" onClick={() => navigate('runs')}><Bell size={17} /><i /></button>
            <div className="top-avatar">MK</div>
          </div>
        </header>

        <div className="page-content">
          {page === 'overview' && <OverviewPage
            overview={overview} datasets={datasets} loading={loading} onUpload={() => fileInput.current?.click()}
            onDemo={handleDemo} demoLoading={demoLoading} onNavigate={navigate} onSelect={(id) => { setSelectedId(id); setPage('datasets') }}
            onForecast={() => navigate('forecast')}
          />}
          {page === 'datasets' && <DatasetsPage
            datasets={datasets} selected={activeDataset} preview={preview} search={search} setSearch={setSearch}
            onUpload={() => fileInput.current?.click()} uploading={uploading} onSelect={setSelectedId} onDelete={removeDataset}
            onForecast={() => navigate('forecast')} onDemo={handleDemo} demoLoading={demoLoading}
          />}
          {page === 'forecast' && <ForecastPage dataset={activeDataset} currentJob={currentJob} onStart={startRun} onUpload={() => fileInput.current?.click()} />}
          {page === 'runs' && <RunsPage jobs={jobs} currentJob={currentJob} onSelectJob={(job) => { setCurrentJob(job); if (job.dataset_id) setSelectedId(job.dataset_id) }} />}
          {page === 'guide' && <GuidePage onUpload={() => fileInput.current?.click()} />}
        </div>
        <footer className="page-footer"><span>© 2026 MandiCast India</span><span>Built for transparent, reproducible market analysis</span><span className="footer-links"><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API docs <ArrowUpRight size={12} /></a><span>·</span><span>v1.0</span></span></footer>
      </main>
      {toast && <div className={`toast toast-${toast.tone}`}><span className="toast-icon">{toast.tone === 'success' ? <CheckCircle2 size={18} /> : toast.tone === 'error' ? <AlertCircle size={18} /> : <Clock3 size={18} />}</span><span>{toast.message}</span><button onClick={() => setToast(null)} aria-label="Dismiss"><X size={15} /></button></div>}
    </div>
  )
}

export default App
