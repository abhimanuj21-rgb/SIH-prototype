// Small shared presentational bits.

export function Loading({ what = 'data' }) {
  return <div className="spinner">Loading {what}…</div>
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="error-box">{String(error.message || error)}</div>
}

export function StatusBadge({ status }) {
  return <span className={`badge badge--${status}`}>{status?.replaceAll('_', ' ')}</span>
}

export function Stat({ value, label }) {
  return (
    <div className="card">
      <div className="stat">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
