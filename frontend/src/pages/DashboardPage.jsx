import { Link } from 'react-router-dom'
import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'
import { Skeleton, ErrorBox, StatTile, SectionTitle } from '../components/Bits.jsx'

export default function DashboardPage() {
  const { data, error, loading } = useAsync(() => api.registrySummary(), [])

  return (
    <div className="page">
      <h1>Dashboard</h1>
      <p className="page__lead">
        A professional, evidence-first platform for land governance and research.
        Prototype area: <strong>Madurai, Tamil Nadu</strong>. The platform reports
        only what real data can substantiate and marks every gap explicitly.
      </p>

      {loading && <div className="card"><Skeleton lines={4} /></div>}
      <ErrorBox error={error} />

      {data && (
        <>
          <div className="grid-3">
            <StatTile accent value={data.total} label="Datasets registered" />
            <StatTile accent value={data.analytically_usable_count} label="Analytically usable now"
              sub="status AVAILABLE + eligible" />
            <StatTile value={data.by_status?.OFFICIAL_ACCESS_REQUIRED || 0} label="Official access required" />
            <StatTile value={data.by_status?.DATA_UNAVAILABLE || 0} label="Open, acquisition pending" />
            <StatTile value={data.by_status?.DOCUMENT_ONLY || 0} label="Document only" />
            <StatTile value={data.by_status?.DEMO_ONLY || 0} label="Demo only" />
          </div>

          <div className="card">
            <SectionTitle>Datasets by status</SectionTitle>
            <table>
              <tbody>
                {Object.entries(data.by_status || {}).map(([s, n]) => (
                  <tr key={s}>
                    <td>{data.status_meta?.[s]?.icon} {s.replaceAll('_', ' ')}</td>
                    <td style={{ textAlign: 'right', width: 60 }}>{n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="card">
        <SectionTitle>Where to go</SectionTitle>
        <ul>
          <li><Link to="/explorer">Explorer</Link> — Madurai map, satellite + OSM base layers, water / land-use / infrastructure overlays, click to pick a point</li>
          <li><Link to="/intelligence">Land Intelligence</Link> — evidence report, site character (water · land use · development) and rule-based suitability for a point</li>
          <li><Link to="/data-registry">Data Registry</Link> — all 26 datasets with provenance and analytical eligibility</li>
          <li><Link to="/data-quality">Data Quality</Link> — automated audit of the registry</li>
          <li><Link to="/official-data-access">Official Data Access</Link> — what is restricted and how to request it</li>
        </ul>
      </div>

      <div className="card">
        <SectionTitle>Build status</SectionTitle>
        <p className="muted">
          Live sources wired: Open-Meteo climate, OpenStreetMap
          infrastructure / hydrology / land-use (via Overpass). Real Madurai
          Corporation boundary. Everything else is acquisition-pending,
          official-access-required, or document-only — and says so.
        </p>
      </div>
    </div>
  )
}
