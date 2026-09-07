import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MapView from '../components/MapView.jsx'

export default function ExplorerPage() {
  const [picked, setPicked] = useState(null)
  const [showInfra, setShowInfra] = useState(true)
  const [showDemo, setShowDemo] = useState(false)
  const navigate = useNavigate()

  return (
    <div className="page">
      <h1>Explorer</h1>
      <p className="page__lead">
        OpenStreetMap basemap with real layers for the Madurai prototype area.
        Click anywhere to pick a coordinate, then open Land Intelligence for its
        evidence report.
      </p>

      <div className="row" style={{ marginBottom: 12 }}>
        <label className="row"><input type="checkbox" checked={showInfra} onChange={(e) => setShowInfra(e.target.checked)} /> OSM infrastructure</label>
        <label className="row"><input type="checkbox" checked={showDemo} onChange={(e) => setShowDemo(e.target.checked)} /> Demo cadastral grid</label>
        {picked && (
          <button onClick={() => navigate('/intelligence', { state: picked })}>
            Land Intelligence for {picked.lat}, {picked.lng}
          </button>
        )}
      </div>

      {showDemo && (
        <div className="demo-flag">
          DEMO DATA — SAMPLE DIGITAL CADASTRAL GRID. Synthetic, not real parcels.
          Excluded from all analysis and evidence.
        </div>
      )}

      <MapView
        picked={picked}
        onPick={setPicked}
        showInfrastructure={showInfra}
        showDemoGrid={showDemo}
      />

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Selected coordinate</h3>
        {picked
          ? <p>Latitude <code>{picked.lat}</code>, Longitude <code>{picked.lng}</code></p>
          : <p className="muted">Click the map to select a point.</p>}
      </div>
    </div>
  )
}
