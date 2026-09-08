// Small shared presentational bits.

export function Loading({ what = 'data' }) {
  return <div className="spinner">Loading {what}…</div>
}

export function Skeleton({ lines = 3, height = 14 }) {
  return (
    <div>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{ height, width: i === lines - 1 ? '60%' : '100%', marginBottom: 8 }}
        />
      ))}
    </div>
  )
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="error-box">{String(error.message || error)}</div>
}

export function StatusBadge({ status }) {
  return <span className={`badge badge--${status}`}>{status?.replaceAll('_', ' ')}</span>
}

export function SectionTitle({ children }) {
  return <div className="section-title">{children}</div>
}

export function StatTile({ value, label, sub, accent }) {
  return (
    <div className={`stat-tile${accent ? ' accent' : ''}`}>
      <div className="stat">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

// Back-compat alias used by a few pages.
export function Stat(props) {
  return <StatTile {...props} />
}

// External "view this location" links — plain anchors, no data leaves the app
// until the user clicks.
export function ExternalViews({ lat, lng }) {
  const links = [
    ['OpenStreetMap', `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=18/${lat}/${lng}`],
    ['Google Maps', `https://www.google.com/maps/@${lat},${lng},18z`],
    ['Street View', `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}`],
    ['Mapillary', `https://www.mapillary.com/app/?lat=${lat}&lng=${lng}&z=17`],
    ['Bhuvan', `https://bhuvan-app1.nrsc.gov.in/bhuvan2d/bhuvan/bhuvan2d.php?lat=${lat}&lon=${lng}`],
  ]
  return (
    <div className="tag-list">
      {links.map(([label, href]) => (
        <a key={label} className="btn ghost" href={href} target="_blank" rel="noreferrer">
          {label} ↗
        </a>
      ))}
    </div>
  )
}
