import { Link } from 'react-router-dom'
import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'
import { Skeleton, ErrorBox, StatTile, SectionTitle } from '../components/Bits.jsx'
import Reveal from '../components/Reveal.jsx'

export default function DashboardPage() {
  const { data, error, loading } = useAsync(() => api.registrySummary(), [])

  return (
    <div className="page">
      <h1>Dashboard</h1>
      <p className="page__lead">
        A professional, evidence-first platform for land governance and research.
        Prototype areas: <strong>Madurai</strong> and <strong>Kovilpatti</strong>
        (Tamil Nadu), and <strong>Bhopal</strong> (Madhya Pradesh). The platform
        reports only what real data can substantiate and marks every gap explicitly.
      </p>

      {loading && <div className="card"><Skeleton lines={4} /></div>}
      <ErrorBox error={error} />

      {data && (
        <>
          <div className="grid-3">
            {[
              <StatTile accent value={data.total} label="Datasets registered" />,
              <StatTile accent value={data.analytically_usable_count} label="Analytically usable now"
                sub="status AVAILABLE + eligible" />,
              <StatTile value={data.by_status?.OFFICIAL_ACCESS_REQUIRED || 0} label="Official access required" />,
              <StatTile value={data.by_status?.DATA_UNAVAILABLE || 0} label="Open, acquisition pending" />,
              <StatTile value={data.by_status?.DOCUMENT_ONLY || 0} label="Document only" />,
              <StatTile value={data.by_status?.DEMO_ONLY || 0} label="Demo only" />,
            ].map((tile, i) => <Reveal as="div" key={i} delay={i * 60}>{tile}</Reveal>)}
          </div>

          <Reveal className="card">
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
          </Reveal>
        </>
      )}

      <Reveal className="card">
        <SectionTitle>Where to go</SectionTitle>
        <ul>
          <li><Link to="/app/explorer">Explorer</Link> — switch between Madurai, Bhopal and Kovilpatti, satellite + OSM base layers, water / land-use / infrastructure overlays, click to pick a point</li>
          <li><Link to="/app/intelligence">Land Intelligence</Link> — a plain-language land report for any point: access vs the city, live weather &amp; air, terrain, soil, amenities, what it could suit — and a downloadable PDF</li>
          <li><Link to="/app/data-registry">Data Registry</Link> — all {data?.total ?? ''} datasets with provenance and analytical eligibility</li>
          <li><Link to="/app/data-quality">Data Quality</Link> — automated audit of the registry</li>
          <li><Link to="/app/official-data-access">Official Data Access</Link> — what is restricted and how to request it</li>
        </ul>
      </Reveal>

      <Reveal className="card">
        <SectionTitle>Build status</SectionTitle>
        <p className="muted">
          Live sources wired: Open-Meteo (ERA5 climate, current weather &amp; forecast,
          Copernicus DEM elevation, CAMS air quality), NOAA airport weather
          observations, ISRIC SoilGrids, and OpenStreetMap infrastructure / hydrology /
          land-use / amenities / addresses. Real Madurai Corporation, Bhopal district and
          Kovilpatti taluk boundaries. Everything else is acquisition-pending,
          official-access-required, or document-only — and says so.
        </p>
      </Reveal>
    </div>
  )
}
