export const formatNumber = (value: number | undefined | null) =>
  value == null || !Number.isFinite(value)
    ? '—'
    : new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(value)

export const formatDate = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'

export const formatBytes = (value: number) =>
  value < 1024 * 1024 ? `${(value / 1024).toFixed(0)} KB` : `${(value / (1024 * 1024)).toFixed(2)} MB`

export const metric = (value: number | null | undefined, suffix = '') =>
  value == null ? '—' : `${value.toFixed(2)}${suffix}`
