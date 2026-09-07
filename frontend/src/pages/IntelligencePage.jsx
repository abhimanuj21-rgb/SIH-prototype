import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import api from '../services/api.js'
import { Loading, ErrorBox } from '../components/Bits.jsx'

const DEFAULT = { lat: 9.9252, lng: 78.1198 }

export default function IntelligencePage() {
  const routed = useLocation().state
  const [lat, setLat] = useState(String(routed?.lat ?? DEFAULT.lat))
  const [lng, setLng] = useState(String(routed?.lng ?? DEFAULT.lng))

  const [report, setReport] = useState(null)
  const [suit, setSuit] = useState(null)
  const [suitType, setSuitType] = useState('agricultural')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function analyse() {
    setLoading(true); setError(null); setReport(null); setSuit(null)
    try {
      const la = parseFloat(lat), lo = parseFloat(lng)
      const [r, s] = await Promise.all([
        api.evidenceReport(la, lo),
        api.suitability(la, lo, suitType),
      ])
      setReport(r); setSuit(s)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (routed?.lat) analyse() /* eslint-disable-line */ }, [])

  const invalidReport = report && report.error

  return (
    <div className="page">
      <h1>Land Intelligence</h1>
      <p className="page__lead">
        Evidence report for a single location: what the platform can verify from
        real sources, and every gap it cannot. Plus a transparent, rule-based
        suitability screen (no AI, no prediction).
      </p>

      <div className="card">
        <div className="row">
          <label>Lat <input className="inline-input" value={lat} onChange={(e) => setLat(e.target.value)} /></label>
          <label>Lon <input className="inline-input" value={lng} onChange={(e) => setLng(e.target.value)} /></label>
          <label>
            Suitability&nbsp;
            <select className="inline-input" value={suitType} onChange={(e) => setSuitType(e.target.value)}>
              <option value="agricultural">agricultural</option>
              <option value="development">development</option>
            </select>
          </label>
          <button onClick={analyse} disabled={loading}>Analyse</button>
        </div>
        <p className="muted" style={{ marginTop: 8, marginBottom: 0 }}>
          Madurai prototype AOI ≈ lat 9.75–10.15, lon 77.95–78.35.
        </p>
      </div>

      {loading && <Loading what="evidence + suitability" />}
      <ErrorBox error={error} />

      {invalidReport && <div className="error-box">{report.error}</div>}

      {report && !invalidReport && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0 }}>Evidence report</h3>
              <div className="row">
                <a className="btn secondary" href={api.exportUrl('json', lat, lng)} target="_blank" rel="noreferrer">Export JSON</a>
                <a className="btn secondary" href={api.exportUrl('pdf', lat, lng)} target="_blank" rel="noreferrer">Export PDF</a>
                <a className="btn secondary" href={api.manifestUrl()} target="_blank" rel="noreferrer">Provenance manifest</a>
              </div>
            </div>
            <p className="muted">
              {report.location?.latitude}, {report.location?.longitude}
              {report.location?.in_city_core ? ' · city core' : ' · outside city core'}
              {' · '}generated {report.generated}
            </p>

            <h4>Verified evidence ({report.verified_evidence?.length || 0})</h4>
            {(report.verified_evidence || []).length === 0 && (
              <p className="muted">Nothing could be verified from live sources for this point.</p>
            )}
            {(report.verified_evidence || []).map((v) => (
              <div key={v.topic} className="verified-item">
                <strong>{v.topic}</strong> — <span className="muted">{v.provenance?.source}</span>
                <table style={{ marginTop: 6 }}>
                  <tbody>
                    {Object.entries(v.value || {}).map(([k, val]) => (
                      <tr key={k}><td>{k.replaceAll('_', ' ')}</td><td>{val === null ? '— not mapped' : String(val)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}

            <h4 style={{ marginTop: 16 }}>Data gaps ({report.data_gaps?.length || 0})</h4>
            {(report.data_gaps || []).map((g) => (
              <div key={g.topic} className="gap-item">
                <strong>{g.topic}</strong>
                {g.dataset_status && <> — <span className="badge badge--DATA_UNAVAILABLE">{g.dataset_status.replaceAll('_', ' ')}</span></>}
                <div className="muted">{g.reason}</div>
                {g.resolution && <div className="muted"><em>Resolution:</em> {g.resolution}</div>}
              </div>
            ))}

            <h4 style={{ marginTop: 16 }}>Conclusion</h4>
            <p>{report.conclusion}</p>
            <p className="muted"><em>{report.disclaimer}</em></p>
          </div>

          <div className="card">
            <h3>Suitability — {suit?.type}</h3>
            {!suit && <p className="muted">—</p>}
            {suit?.error && <div className="error-box">{suit.error}</div>}
            {suit && !suit.error && !suit.scorable && (
              <>
                <p className="error-box">{suit.reason}</p>
                <p className="muted">Missing verified features: {suit.missing_features?.join(', ')}</p>
              </>
            )}
            {suit?.scorable && (
              <>
                <div className="row">
                  <div className="stat">{suit.score}/100</div>
                  <span className="badge badge--AVAILABLE">{suit.category}</span>
                </div>
                {suit.limiting_factors?.length > 0 && (
                  <p className="muted">Limiting factors: {suit.limiting_factors.join(', ')}</p>
                )}
              </>
            )}
            {suit && (
              <table style={{ marginTop: 10 }}>
                <thead><tr><th>Criterion</th><th>Value</th><th>Points</th><th>Max</th></tr></thead>
                <tbody>
                  {(suit.breakdown || []).map((b) => (
                    <tr key={b.criterion}>
                      <td>{b.criterion}</td>
                      <td>{b.value === null ? '— missing' : String(b.value)}</td>
                      <td>{b.points === null ? '—' : b.points}</td>
                      <td>{b.max}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="muted"><em>{suit?.method}. {suit?.disclaimer}</em></p>
          </div>
        </>
      )}
    </div>
  )
}
