import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MapView from '../components/MapView.jsx'

const LAYER_DEFS = [
  ['infrastructure', 'Infrastructure (roads, health, education, rail)'],
  ['hydrology', 'Water bodies & rivers'],
  ['landuse', 'Land use (farmland / residential / …)'],
  ['demo', 'Demo cadastral grid'],
]

export default function ExplorerPage() {
  const [picked, setPicked] = useState(null)
  const [layers, setLayers] = useState({
    infrastructure: true, hydrology: true, landuse: false, demo: false,
  })
  const navigate = useNavigate()
  const toggle = (k) => setLayers((l) => ({ ...l, [k]: !l[k] }))

  return (
    <div className="page">
      <h1>Explorer</h1>
      <p className="page__lead">
        Switch base maps (including Esri satellite for a street-level view of how
        built-up an area is) and toggle real OpenStreetMap layers. Click anywhere
        to pick a coordinate, then open Land Intelligence for its full evidence
        report and site character.
      </p>

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
          DEMO DATA — SAMPLE DIGITAL CADASTRAL GRID. Synthetic, not real parcels.
          Excluded from all analysis and evidence.
        </div>
      )}

      <MapView picked={picked} onPick={setPicked} layers={layers} />

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card__head">
          <h3>Selected coordinate</h3>
          {picked && (
            <button onClick={() => navigate('/intelligence', { state: picked })}>
              Open Land Intelligence →
            </button>
          )}
        </div>
        {picked
          ? <p className="muted">Latitude <code>{picked.lat}</code>, longitude <code>{picked.lng}</code>.
            The Land Intelligence page will pull climate, infrastructure, water,
            land use and development for this point.</p>
          : <p className="muted">Click the map to select a point.</p>}
      </div>
    </div>
  )
}
