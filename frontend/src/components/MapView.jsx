import { useEffect, useMemo, useState } from 'react'
import {
  MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, useMapEvents, Marker,
} from 'react-leaflet'
import L from 'leaflet'
import api from '../services/api.js'

const MADURAI_CENTER = [9.925, 78.119]

// Avoid Leaflet's broken default-marker asset path under bundlers by using a
// tiny inline divIcon for the picked point.
const pickIcon = L.divIcon({
  className: '',
  html: '<div style="width:14px;height:14px;border-radius:50%;background:#4c9aff;border:2px solid #fff;box-shadow:0 0 0 2px #4c9aff"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
})

const KIND_COLOR = {
  road: '#64748b',
  hospital: '#ef4444',
  education: '#f59e0b',
  rail_station: '#a855f7',
  other: '#94a3b8',
}

function ClickCapture({ onPick }) {
  useMapEvents({
    click(e) {
      onPick?.({ lat: +e.latlng.lat.toFixed(6), lng: +e.latlng.lng.toFixed(6) })
    },
  })
  return null
}

export default function MapView({ picked, onPick, showInfrastructure = true, showDemoGrid = false }) {
  const [boundary, setBoundary] = useState(null)
  const [boundaryIsDemo, setBoundaryIsDemo] = useState(false)
  const [infra, setInfra] = useState(null)
  const [infraNote, setInfraNote] = useState('')
  const [demoGrid, setDemoGrid] = useState(null)

  useEffect(() => {
    api.boundary()
      .then((r) => {
        if (r?.available) { setBoundary(r.geojson); setBoundaryIsDemo(!!r.is_demo) }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!showInfrastructure) return
    api.infrastructure()
      .then((r) => {
        if (r?.available) setInfra(r.geojson)
        else setInfraNote(r?.reason || 'infrastructure layer unavailable')
      })
      .catch((e) => setInfraNote(e.message))
  }, [showInfrastructure])

  useEffect(() => {
    if (!showDemoGrid) { setDemoGrid(null); return }
    api.demoGrid().then((r) => setDemoGrid(r.geojson)).catch(() => {})
  }, [showDemoGrid])

  const points = useMemo(
    () => (infra?.features || []).filter((f) => f.geometry?.type === 'Point'),
    [infra],
  )
  const roads = useMemo(
    () => ({
      type: 'FeatureCollection',
      features: (infra?.features || []).filter((f) => f.geometry?.type === 'LineString'),
    }),
    [infra],
  )

  return (
    <div className="map-wrap">
      <MapContainer center={MADURAI_CENTER} zoom={12} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {boundary && (
          <GeoJSON
            data={boundary}
            style={{
              color: boundaryIsDemo ? '#ef4444' : '#4c9aff',
              weight: 2,
              dashArray: boundaryIsDemo ? '6 6' : undefined,
              fillOpacity: 0.04,
            }}
          />
        )}

        {demoGrid && (
          <GeoJSON
            data={demoGrid}
            style={{ color: '#ef4444', weight: 1, dashArray: '3 3', fillOpacity: 0.03 }}
          />
        )}

        {roads.features.length > 0 && (
          <GeoJSON
            key={`roads-${roads.features.length}`}
            data={roads}
            style={{ color: '#5b6b82', weight: 1.2, opacity: 0.7 }}
          />
        )}

        {points.map((f) => {
          const [lng, lat] = f.geometry.coordinates
          const kind = f.properties?.kind || 'other'
          return (
            <CircleMarker
              key={`${f.properties?.osm_id}-${kind}`}
              center={[lat, lng]}
              radius={kind === 'road' ? 2 : 5}
              pathOptions={{ color: KIND_COLOR[kind] || '#94a3b8', weight: 1, fillOpacity: 0.8 }}
            >
              <Popup>
                <strong>{f.properties?.name || '(unnamed)'}</strong><br />
                {kind}
              </Popup>
            </CircleMarker>
          )
        })}

        {picked && (
          <Marker position={[picked.lat, picked.lng]} icon={pickIcon}>
            <Popup>{picked.lat}, {picked.lng}</Popup>
          </Marker>
        )}

        <ClickCapture onPick={onPick} />
      </MapContainer>
      {infraNote && (
        <div className="muted" style={{ padding: '4px 8px', fontSize: '.75rem' }}>
          Infrastructure layer: {infraNote}
        </div>
      )}
    </div>
  )
}
