import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import api from '../services/api.js'
import { Loading, ErrorBox, SectionTitle, ExternalViews } from '../components/Bits.jsx'
import SiteContext from '../components/SiteContext.jsx'

const DEFAULT = { lat: 9.9252, lng: 78.1198 }

export default function IntelligencePage() {
  const routed = useLocation().state
  const [lat, setLat] = useState(String(routed?.lat ?? DEFAULT.lat))
  const [lng, setLng] = useState(String(routed?.lng ?? DEFAULT.lng))
  const [suitType, setSuitType] = useState('agricultural')

  const [report, setReport] = useState(null)
  const [suit, setSuit] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [site, setSite] = useState(null)
  const [siteLoading, setSiteLoading] = useState(false)
  const [siteError, setSiteError] = useState(null)
  const analysedAt = useRef(null)

  async function analyse() {
    const la = parseFloat(lat), lo = parseFloat(lng)
    analysedAt.current = { la, lo }
    setLoading(true); setError(null); setReport(null); setSuit(null)
    setSite(null); setSiteError(null); setSiteLoading(true)

    // fast pair
    try {
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

    // slow site context — separate, non-blocking
    api.siteContext(la, lo)
      .then((sc) => setSite(sc))
      .catch((e) => setSiteError(e))
      .finally(() => setSiteLoading(false))
  }

  useEffect(() => { if (routed?.lat) analyse() /* eslint-disable-line */ }, [])

  const invalid = report && report.error

  return (
    <div className="page">
      <h1>Land Intelligence</h1>
      <p className="page__lead">
        One location, everything the platform can verify from real sources —
        climate, infrastructure, water, land use and how developed the
        surroundings are — plus every gap it cannot, and a transparent
        rule-based suitability screen (no AI, no prediction).
      </p>

      <div className="card">
        <div className="row">
          <label className="muted">Lat <input className="inline-input" value={lat} onChange={(e) => setLat(e.target.value)} /></label>
          <label className="muted">Lon <input className="inline-input" value={lng} onChange={(e) => setLng(e.target.value)} /></label>
          <label className="muted">
            Suitability{' '}
            <select className="inline-input" value={suitType} onChange={(e) => setSuitType(e.target.value)}>
              <option value="agricultural">agricultural</option>
              <option value="development">development</option>
            </select>
          </label>
          <button onClick={analyse} disabled={loading}>Analyse</button>
        </div>
        <p className="faint" style={{ marginTop: 10, marginBottom: 0 }}>
          Madurai prototype AOI ≈ lat 9.75–10.15, lon 77.95–78.35.
        </p>
      </div>

      {loading && <Loading what="climate, infrastructure & suitability" />}
      <ErrorBox error={error} />
      {invalid && <div className="error-box">{report.error}</div>}

      {report && !invalid && (
        <>
          <div className="card">
            <div className="card__head">
              <div>
                <h3 style={{ margin: 0 }}>
                  {report.location?.latitude}, {report.location?.longitude}
                </h3>
                <span className="faint">
                  {report.location?.in_city_core ? 'Within Madurai city core' : 'Outside city core'} · generated {report.generated}
                </span>
              </div>
              <div className="tag-list">
                <a className="btn secondary" href={api.exportUrl('json', lat, lng)} target="_blank" rel="noreferrer">JSON</a>
                <a className="btn secondary" href={api.exportUrl('pdf', lat, lng)} target="_blank" rel="noreferrer">PDF</a>
                <a className="btn secondary" href={api.manifestUrl()} target="_blank" rel="noreferrer">Manifest</a>
              </div>
            </div>
            <SectionTitle>View this location externally</SectionTitle>
            <ExternalViews lat={report.location?.latitude} lng={report.location?.longitude} />
          </div>

          <SiteContext data={site} loading={siteLoading} error={siteError} />

          <div className="card">
            <SectionTitle>Verified evidence ({report.verified_evidence?.length || 0})</SectionTitle>
            {(report.verified_evidence || []).length === 0 && (
              <p className="muted">Nothing could be verified from live sources for this point.</p>
            )}
            {(report.verified_evidence || []).map((v) => (
              <div key={v.topic} className="item verified">
                <div className="item__title">
                  {v.topic.replaceAll('_', ' ')}
                  <span className="faint" style={{ fontWeight: 400 }}>· {v.provenance?.source}</span>
                </div>
                <table className="kv"><tbody>
                  {Object.entries(v.value || {}).map(([k, val]) => (
                    <tr key={k}>
                      <td>{k.replaceAll('_', ' ')}</td>
                      <td>{val === null ? <span className="faint">— not mapped</span>
                        : typeof val === 'object' ? <code>{JSON.stringify(val)}</code>
                        : String(val)}</td>
                    </tr>
                  ))}
                </tbody></table>
              </div>
            ))}

            <SectionTitle>Data gaps ({report.data_gaps?.length || 0})</SectionTitle>
            {(report.data_gaps || []).map((g) => (
              <div key={g.topic} className="item gap">
                <div className="item__title">
                  {g.topic.replaceAll('_', ' ')}
                  {g.dataset_status && <span className={`badge badge--${g.dataset_status}`}>{g.dataset_status.replaceAll('_', ' ')}</span>}
                </div>
                <div className="muted">{g.reason}</div>
                {g.resolution && <div className="faint"><em>Resolution:</em> {g.resolution}</div>}
              </div>
            ))}

            <SectionTitle>Conclusion</SectionTitle>
            <p>{report.conclusion}</p>
            <p className="faint"><em>{report.disclaimer}</em></p>
          </div>

          <div className="card">
            <SectionTitle>Suitability — {suit?.type}</SectionTitle>
            {suit?.error && <div className="error-box">{suit.error}</div>}
            {suit && !suit.error && !suit.scorable && (
              <>
                <p className="error-box">{suit.reason}</p>
                <p className="faint">Missing verified features: {suit.missing_features?.join(', ')}</p>
              </>
            )}
            {suit?.scorable && (
              <div className="row" style={{ marginBottom: 8 }}>
                <div className="stat">{suit.score}/100</div>
                <span className="badge badge--AVAILABLE">{suit.category}</span>
                {suit.limiting_factors?.length > 0 && (
                  <span className="faint">limited by {suit.limiting_factors.join(', ')}</span>
                )}
              </div>
            )}
            {suit && (
              <table><thead><tr><th>Criterion</th><th>Value</th><th>Points</th><th>Max</th></tr></thead>
                <tbody>
                  {(suit.breakdown || []).map((b) => (
                    <tr key={b.criterion}>
                      <td>{b.criterion}</td>
                      <td>{b.value === null ? <span className="faint">— missing</span> : String(b.value)}</td>
                      <td>{b.points === null ? '—' : b.points}</td>
                      <td>{b.max}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="faint" style={{ marginTop: 10 }}><em>{suit?.method}. {suit?.disclaimer}</em></p>
          </div>
        </>
      )}
    </div>
  )
}
