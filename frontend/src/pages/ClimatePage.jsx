import { useState } from 'react'
import api from '../services/api.js'
import { Loading, ErrorBox } from '../components/Bits.jsx'
import Reveal from '../components/Reveal.jsx'

const DEFAULT = { lat: '9.9252', lng: '78.1198' }

export default function ClimatePage() {
  const [lat, setLat] = useState(DEFAULT.lat)
  const [lng, setLng] = useState(DEFAULT.lng)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function load() {
    setLoading(true); setError(null); setData(null)
    try {
      const r = await api.evidenceLocation(parseFloat(lat), parseFloat(lng))
      setData(r)
    } catch (e) { setError(e) } finally { setLoading(false) }
  }

  const climate = data?.verified_evidence?.find((v) => v.topic === 'climate')

  return (
    <div className="page">
      <h1>Climate</h1>
      <p className="page__lead">
        Real ERA5 climate normals from the Open-Meteo Archive API (keyless,
        ~9 km reanalysis grid). This is one of the few sources wired live in the
        current build.
      </p>

      <Reveal className="card">
        <div className="row">
          <label>Lat <input className="inline-input" value={lat} onChange={(e) => setLat(e.target.value)} /></label>
          <label>Lon <input className="inline-input" value={lng} onChange={(e) => setLng(e.target.value)} /></label>
          <button onClick={load} disabled={loading}>Get climate</button>
        </div>
      </Reveal>

      {loading && <Loading what="climate normals" />}
      <ErrorBox error={error} />

      {data && !climate && (
        <Reveal className="card">
          <p className="error-box">
            Climate could not be verified for this point
            {data.data_gaps?.find((g) => g.topic === 'climate')
              ? `: ${data.data_gaps.find((g) => g.topic === 'climate').reason}` : '.'}
          </p>
        </Reveal>
      )}

      {climate && (
        <Reveal className="card">
          <h3>Climate normals</h3>
          <p className="muted">{climate.provenance?.source} · {climate.value?.period} · {climate.provenance?.resolution}</p>
          <table>
            <tbody>
              {Object.entries(climate.value || {}).map(([k, v]) => (
                <tr key={k}><td>{k.replaceAll('_', ' ')}</td><td>{String(v)}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="muted"><em>Confidence: {climate.provenance?.confidence}. Retrieved {climate.provenance?.retrieved}.</em></p>
        </Reveal>
      )}
    </div>
  )
}
