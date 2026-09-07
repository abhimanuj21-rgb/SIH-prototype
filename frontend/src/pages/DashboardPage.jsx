import { Link } from 'react-router-dom'
import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'
import { Loading, ErrorBox, Stat } from '../components/Bits.jsx'

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

      {loading && <Loading what="registry summary" />}
      <ErrorBox error={error} />

      {data && (
        <>
          <div className="grid-2">
            <Stat value={data.total} label="Datasets registered" />
            <Stat value={data.analytically_usable_count} label="Analytically usable now" />
            <Stat value={data.by_status?.OFFICIAL_ACCESS_REQUIRED || 0} label="Official access required" />
            <Stat value={data.by_status?.DOCUMENT_ONLY || 0} label="Document only" />
          </div>

          <div className="card">
            <h3>Datasets by status</h3>
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
        <h3>Where to go</h3>
        <ul>
          <li><Link to="/explorer">Explorer</Link> — map of Madurai, real OSM layers, click to pick a point</li>
          <li><Link to="/intelligence">Land Intelligence</Link> — evidence report + rule-based suitability for a point</li>
          <li><Link to="/data-registry">Data Registry</Link> — all 26 datasets with provenance and analytical eligibility</li>
          <li><Link to="/data-quality">Data Quality</Link> — automated audit of the registry</li>
          <li><Link to="/official-data-access">Official Data Access</Link> — what is restricted and how to request it</li>
        </ul>
      </div>

      <div className="card">
        <h3>Build status</h3>
        <p className="muted">
          Phase 1 scaffold (2026-09-08). Live sources wired: Open-Meteo climate,
          OpenStreetMap infrastructure/hydrology. Everything else is
          acquisition-pending, official-access-required, or document-only — and
          says so.
        </p>
      </div>
    </div>
  )
}
