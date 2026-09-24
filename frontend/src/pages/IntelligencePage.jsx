import { useEffect, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import api from '../services/api.js'
import { ErrorBox, SectionTitle, ExternalViews, Skeleton } from '../components/Bits.jsx'
import SiteContext from '../components/SiteContext.jsx'
import Reveal from '../components/Reveal.jsx'
import { Verdict, FacilityChart, UseFit, Coverage } from '../components/LandReport.jsx'
import LandDetails from '../components/LandDetails.jsx'

const DEFAULT = { lat: 9.9252, lng: 78.1198 }

// Real points inside each prototype AOI — quick ways to see contrasting outcomes.
const SAMPLES = [
  { label: 'Madurai centre', lat: 9.9252, lng: 78.1198 },
  { label: 'Madurai outskirts', lat: 9.80, lng: 78.30 },
  { label: 'Bhopal centre', lat: 23.2599, lng: 77.4126 },
  { label: 'Bhopal fringe', lat: 23.15, lng: 77.30 },
  { label: 'Kovilpatti town', lat: 9.1744, lng: 77.8683 },
]

const LAST_KEY = 'ndp.lastLocation'

function readLast() {
  try { return JSON.parse(localStorage.getItem(LAST_KEY)) } catch { return null }
}

export default function IntelligencePage() {
  const routed = useLocation().state
  const [params, setParams] = useSearchParams()
  // a shared link (?lat=&lon=) wins, then a click from Explorer, then the last spot used
  const qLat = params.get('lat'), qLon = params.get('lon')
  const start = qLat && qLon ? { lat: qLat, lng: qLon }
    : routed?.lat ? routed : readLast() || DEFAULT
  const [lat, setLat] = useState(String(start.lat))
  const [lng, setLng] = useState(String(start.lng))
  const [at, setAt] = useState(null) // the coordinate the current result is for

  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [locating, setLocating] = useState(false)

  const [suitType, setSuitType] = useState('agricultural')
  const [suit, setSuit] = useState(null)

  async function analyse(la = parseFloat(lat), lo = parseFloat(lng)) {
    if (!Number.isFinite(la) || !Number.isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) {
      setError(new Error('Enter a valid latitude (−90 to 90) and longitude (−180 to 180), e.g. 9.9252 and 78.1198.'))
      return
    }
    la = Math.round(la * 1e5) / 1e5
    lo = Math.round(lo * 1e5) / 1e5
    setLat(String(la)); setLng(String(lo))
    setLoading(true); setError(null); setProfile(null); setSuit(null)
    setParams({ lat: String(la), lon: String(lo) }, { replace: true })
    try {
      const p = await api.landProfile(la, lo)
      setProfile(p); setAt({ la, lo })
      if (!p.error) {
        try { localStorage.setItem(LAST_KEY, JSON.stringify({ lat: la, lng: lo })) } catch { /* private mode */ }
      }
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  function locateMe() {
    if (!navigator.geolocation) {
      setError(new Error('This browser cannot share its location.'))
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => { setLocating(false); analyse(pos.coords.latitude, pos.coords.longitude) },
      (err) => { setLocating(false); setError(new Error(`Could not get your location: ${err.message}`)) },
      { enableHighAccuracy: true, timeout: 15000 },
    )
  }

  useEffect(() => {
    if ((qLat && qLon) || routed?.lat) analyse() // eslint-disable-line react-hooks/exhaustive-deps
  }, [])

  // browser tab title follows the place being looked at
  useEffect(() => {
    const loc = profile && !profile.error ? profile.location : null
    const place = profile?.details?.locality?.value?.suburb_or_village || loc?.city_label
    document.title = loc
      ? `${place ? place + ' · ' : ''}Land report — National Digital Platform`
      : 'Land Intelligence — National Digital Platform'
    return () => { document.title = 'National Digital Platform — Madurai, Bhopal & Kovilpatti' }
  }, [profile])

  // the rule-based suitability screen lives under "technical details"
  useEffect(() => {
    if (!at) return
    api.suitability(at.la, at.lo, suitType).then(setSuit).catch(() => setSuit(null))
  }, [at, suitType])

  const invalid = profile && profile.error
  const ok = profile && !invalid
  const report = ok ? profile.report : null
  const labelFor = (topic) =>
    ok ? ([...profile.evidence_coverage.unknown, ...profile.evidence_coverage.known]
      .find((x) => x.topic === topic)?.label || topic) : topic

  return (
    <div className="page">
      <h1>Land Intelligence</h1>
      <p className="page__lead">
        Pick any point and get a plain-language land report: how well served
        it is, how it compares with the rest of the city, what it could suit —
        and exactly which checks are still open. Built only from verified data;
        downloadable as a PDF.
      </p>

      <Reveal className="card">
        <form className="row" onSubmit={(e) => { e.preventDefault(); analyse() }}>
          <label className="muted">Lat <input className="inline-input" inputMode="decimal" value={lat}
                                              onChange={(e) => setLat(e.target.value)} aria-label="Latitude" /></label>
          <label className="muted">Lon <input className="inline-input" inputMode="decimal" value={lng}
                                              onChange={(e) => setLng(e.target.value)} aria-label="Longitude" /></label>
          <button type="submit" disabled={loading}>{loading ? 'Analysing…' : 'Analyse location'}</button>
          <button type="button" className="btn secondary" onClick={locateMe} disabled={loading || locating}>
            {locating ? 'Locating…' : '📍 My location'}
          </button>
        </form>
        <div className="lr-samples">
          <span className="faint">Try:</span>
          {SAMPLES.map((s) => (
            <button key={s.label} disabled={loading}
                    className={`btn ghost${at && at.la === s.lat && at.lo === s.lng ? ' on' : ''}`}
                    onClick={() => analyse(s.lat, s.lng)}>{s.label}</button>
          ))}
        </div>
        <p className="faint" style={{ marginTop: 10, marginBottom: 0 }}>
          Covered areas: Madurai ≈ lat 9.75–10.15, lon 77.95–78.35 ·
          Bhopal ≈ lat 23.10–23.42, lon 77.25–77.55 ·
          Kovilpatti ≈ lat 9.12–9.23, lon 77.82–77.92. Tip: click a point in the Explorer map to open it here.
        </p>
      </Reveal>

      {loading && (
        <div className="card">
          <div className="lr-verdict__main">
            <div className="lr-gauge"><div className="skeleton" style={{ width: 128, height: 128, borderRadius: '50%' }} /></div>
            <div style={{ flex: 1 }}><Skeleton lines={4} height={16} /></div>
          </div>
          <p className="faint" style={{ margin: '12px 0 0' }}>Gathering climate, terrain, soil, air quality, facilities and land use for this point — the first lookup takes ~10 s…</p>
        </div>
      )}
      <ErrorBox error={error} />
      {invalid && <div className="error-box">{profile.error} Try one of the sample places above, or pick a point on the Explorer map.</div>}

      {ok && (
        <>
          <Verdict profile={profile}
                   pdfUrl={api.exportUrl('pdf', at.la, at.lo)} />

          <FacilityChart facilities={profile.facilities}
                         cityLabel={profile.location.city_label}
                         samplePoints={profile.benchmark.sample_points} />

          <LandDetails details={profile.details} location={profile.location} />

          <div className="lr-two">
            <UseFit uses={profile.use_fit} labelFor={labelFor} />
            <Coverage coverage={profile.evidence_coverage} note={profile.verdict.confidence_note} />
          </div>

          <SiteContext data={profile.site || { available: false, reason: 'Site context layers are still warming up — retry shortly.' }} />

          <details className="card lr-details">
            <summary>Technical details — raw evidence, data gaps, rule-based suitability &amp; method</summary>

            <SectionTitle>View this location externally</SectionTitle>
            <ExternalViews lat={profile.location.latitude} lng={profile.location.longitude} />

            <SectionTitle>How the scores are made</SectionTitle>
            <ul className="lr-method">
              <li>{profile.method.access}</li>
              <li>{profile.method.benchmark}</li>
              <li>{profile.method.use_fit}</li>
              {profile.method.details && <li>{profile.method.details}</li>}
            </ul>

            <SectionTitle>Verified evidence ({report.verified_evidence.length})</SectionTitle>
            {report.verified_evidence.map((v) => (
              <div key={v.topic} className="item verified">
                <div className="item__title">
                  {v.topic.replaceAll('_', ' ')}
                  <span className="faint" style={{ fontWeight: 400 }}>· {v.provenance?.source}</span>
                </div>
                <table className="kv"><tbody>
                  {Object.entries(v.value || {}).map(([k, val]) => (
                    <tr key={k}>
                      <td>{k.replaceAll('_', ' ')}</td>
                      <td>{val === null ? <span className="faint">— not mapped</span> : String(val)}</td>
                    </tr>
                  ))}
                </tbody></table>
              </div>
            ))}

            <SectionTitle>Data gaps ({report.data_gaps.length})</SectionTitle>
            {report.data_gaps.map((g) => (
              <div key={g.topic} className="item gap">
                <div className="item__title">
                  {g.topic.replaceAll('_', ' ')}
                  {g.dataset_status && <span className={`badge badge--${g.dataset_status}`}>{g.dataset_status.replaceAll('_', ' ')}</span>}
                </div>
                <div className="muted">{g.reason}</div>
                {g.resolution && <div className="faint"><em>Resolution:</em> {g.resolution}</div>}
              </div>
            ))}

            <SectionTitle>
              Rule-based suitability (terrain + satellite land cover required){' '}
              <select className="inline-input" value={suitType} onChange={(e) => setSuitType(e.target.value)}>
                <option value="agricultural">agricultural</option>
                <option value="development">development</option>
              </select>
            </SectionTitle>
            {suit && !suit.error && !suit.scorable && (
              <p className="muted">{suit.reason} Missing: {suit.missing_features?.join(', ')}.</p>
            )}
            {suit?.scorable && (
              <p><strong>{suit.score}/100</strong> — {suit.category}</p>
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

            <SectionTitle>Evidence conclusion</SectionTitle>
            <p>{report.conclusion}</p>
          </details>

          <p className="faint"><em>{profile.disclaimer} Generated {profile.generated}.</em></p>
        </>
      )}
    </div>
  )
}
