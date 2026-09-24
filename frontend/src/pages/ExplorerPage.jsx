import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MapView from '../components/MapView.jsx'
import Reveal from '../components/Reveal.jsx'
import api from '../services/api.js'

const LAYER_DEFS = [
  ['infrastructure', 'Infrastructure (roads, health, education, rail)'],
  ['hydrology', 'Water bodies & rivers'],
  ['landuse', 'Land use (farmland / residential / …)'],
  ['demo', 'Demo cadastral parcels'],
]

const FALLBACK_CITIES = [
  { id: 'madurai', label: 'Madurai', state: 'Tamil Nadu' },
  { id: 'bhopal', label: 'Bhopal', state: 'Madhya Pradesh' },
  { id: 'kovilpatti', label: 'Kovilpatti', state: 'Tamil Nadu' },
]

export default function ExplorerPage() {
  const [cities, setCities] = useState(FALLBACK_CITIES)
  const [city, setCity] = useState('madurai')
  const [picked, setPicked] = useState(null)
  const [demoStats, setDemoStats] = useState(null)
  const [layers, setLayers] = useState({
    infrastructure: true, hydrology: true, landuse: false, demo: false,
  })
  const navigate = useNavigate()
  const toggle = (k) => setLayers((l) => ({ ...l, [k]: !l[k] }))

  useEffect(() => { api.cities().then((r) => r?.cities && setCities(r.cities)).catch(() => {}) }, [])

  const changeCity = (id) => {
    if (id === city) return
    setCity(id)
    setPicked(null)
    setDemoStats(null)
  }

  return (
    <div className="page">
      <h1>Explorer</h1>
      <p className="page__lead">
        Switch base maps (including Esri satellite for a street-level view of how
        built-up an area is) and toggle real OpenStreetMap layers. Click anywhere
        to pick a coordinate, then open Land Intelligence for its full evidence
        report and site character.
      </p>

      <div className="row" style={{ marginBottom: 12 }}>
        {cities.map((c) => (
          <button key={c.id} className={city === c.id ? '' : 'secondary'}
            onClick={() => changeCity(c.id)} title={c.state}>
            {c.label}
          </button>
        ))}
      </div>

      <div className="map-toolbar">
        {LAYER_DEFS.map(([k, label]) => (
          <label key={k} className={`toggle${layers[k] ? ' on' : ''}`}>
            <input type="checkbox" checked={layers[k]} onChange={() => toggle(k)} />
            {label}
          </label>
        ))}
      </div>

      {layers.demo && (
        <div className="demo-flag">
          DEMO DATA — SYNTHETIC CADASTRAL PARCEL FABRIC. Not real parcels.
          Excluded from all analysis and evidence.
          {demoStats && (
            <> {demoStats.count} parcels · avg {Math.round(demoStats.avgSqm).toLocaleString()} m²
              ({(demoStats.avgSqm / 40.4686).toFixed(2)} cents) each.</>
          )}
        </div>
      )}

      <MapView picked={picked} onPick={setPicked} city={city} layers={layers}
        onDemoGridStats={setDemoStats} />

      <Reveal className="card" style={{ marginTop: 16 }}>
        <div className="card__head">
          <h3>Selected coordinate</h3>
          {picked && (
            <button onClick={() => navigate(`/app/intelligence?lat=${picked.lat}&lon=${picked.lng}`)}>
              Open Land Intelligence →
            </button>
          )}
        </div>
        {picked
          ? <p className="muted">Latitude <code>{picked.lat}</code>, longitude <code>{picked.lng}</code>.
            The Land Intelligence page will pull climate, infrastructure, water,
            land use and development for this point.</p>
          : <p className="muted">Click the map to select a point.</p>}
      </Reveal>
    </div>
  )
}
