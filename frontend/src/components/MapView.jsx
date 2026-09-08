import { useEffect, useMemo, useState } from 'react'
import {
  MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, Marker,
  LayersControl, useMap, useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import api from '../services/api.js'

const MADURAI_CENTER = [9.925, 78.119]

const pickIcon = L.divIcon({
  className: '',
  html: '<div style="width:16px;height:16px;border-radius:50%;background:#38bdf8;border:2px solid #fff;box-shadow:0 0 0 3px rgba(56,189,248,.5)"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
})

const POI_COLOR = {
  hospital: '#f87171',
  education: '#fbbf24',
  rail_station: '#c084fc',
  other: '#94a3b8',
}
const LU_COLOR = {
  farmland: '#4ade80', farmyard: '#4ade80', orchard: '#22c55e',
  residential: '#fb923c', commercial: '#f97316', retail: '#f97316',
  industrial: '#a16207', construction: '#eab308', forest: '#15803d',
  meadow: '#84cc16', quarry: '#78716c',
}

function FixSize() {
  const map = useMap()
  useEffect(() => {
    const t = setTimeout(() => map.invalidateSize(), 220)
    return () => clearTimeout(t)
  }, [map])
  return null
}

function ClickCapture({ onPick }) {
  useMapEvents({
    click(e) {
      onPick?.({ lat: +e.latlng.lat.toFixed(6), lng: +e.latlng.lng.toFixed(6) })
    },
  })
  return null
}

export default function MapView({
  picked, onPick,
  layers = { infrastructure: true, hydrology: true, landuse: false, demo: false },
}) {
  const [boundary, setBoundary] = useState(null)
  const [boundaryIsDemo, setBoundaryIsDemo] = useState(false)
  const [infra, setInfra] = useState(null)
  const [hydro, setHydro] = useState(null)
  const [landuse, setLanduse] = useState(null)
  const [demoGrid, setDemoGrid] = useState(null)
  const [notes, setNotes] = useState({})

  const note = (k, v) => setNotes((n) => ({ ...n, [k]: v }))

  useEffect(() => {
    api.boundary().then((r) => {
      if (r?.available) { setBoundary(r.geojson); setBoundaryIsDemo(!!r.is_demo) }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!layers.infrastructure || infra) return
    api.infrastructure()
      .then((r) => r?.available ? setInfra(r.geojson) : note('infra', r?.reason))
      .catch((e) => note('infra', e.message))
  }, [layers.infrastructure]) // eslint-disable-line

  useEffect(() => {
    if (!layers.hydrology || hydro) return
    api.hydrology()
      .then((r) => r?.available ? setHydro(r.geojson) : note('hydro', r?.reason))
      .catch((e) => note('hydro', e.message))
  }, [layers.hydrology]) // eslint-disable-line

  useEffect(() => {
    if (!layers.landuse || landuse) return
    note('landuse', 'loading…')
    api.landuse()
      .then((r) => { r?.available ? setLanduse(r.geojson) : note('landuse', r?.reason); if (r?.available) note('landuse', null) })
      .catch((e) => note('landuse', e.message))
  }, [layers.landuse]) // eslint-disable-line

  useEffect(() => {
    if (!layers.demo) { setDemoGrid(null); return }
    api.demoGrid().then((r) => setDemoGrid(r.geojson)).catch(() => {})
  }, [layers.demo])

  const pois = useMemo(
    () => (infra?.features || []).filter((f) => f.geometry?.type === 'Point'),
    [infra],
  )
  const roads = useMemo(() => ({
    type: 'FeatureCollection',
    features: (infra?.features || []).filter((f) => f.geometry?.type === 'LineString'),
  }), [infra])

  return (
    <div className="map-wrap">
      <MapContainer center={MADURAI_CENTER} zoom={12} scrollWheelZoom>
        <FixSize />
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="OSM Standard">
            <TileLayer attribution='&copy; OpenStreetMap contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite (Esri)">
            <TileLayer maxZoom={19}
              attribution='Imagery &copy; Esri, Maxar, Earthstar Geographics'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Light (Esri)">
            <TileLayer maxZoom={16}
              attribution='Tiles &copy; Esri'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Dark (Esri)">
            <TileLayer maxZoom={16}
              attribution='Tiles &copy; Esri'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="OSM Humanitarian">
            <TileLayer attribution='&copy; OpenStreetMap contributors, HOT'
              url="https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png" />
          </LayersControl.BaseLayer>
        </LayersControl>

        {boundary && (
          <GeoJSON data={boundary} style={{
            color: boundaryIsDemo ? '#f87171' : '#38bdf8', weight: 2,
            dashArray: boundaryIsDemo ? '6 6' : undefined, fillOpacity: 0.03,
          }} />
        )}

        {layers.landuse && landuse && (
          <GeoJSON key={`lu-${landuse.features.length}`} data={landuse}
            style={(f) => {
              const t = f.properties?.tag
              return { color: LU_COLOR[t] || '#64748b', weight: 1, fillOpacity: 0.18 }
            }}
            onEachFeature={(f, layer) => layer.bindPopup(
              `<strong>${f.properties?.name || 'land use'}</strong><br/>landuse=${f.properties?.tag}`)} />
        )}

        {layers.hydrology && hydro && (
          <GeoJSON key={`hy-${hydro.features.length}`} data={hydro}
            style={(f) => f.geometry.type === 'LineString'
              ? { color: '#38bdf8', weight: 2, opacity: 0.85 }
              : { color: '#38bdf8', weight: 1, fillColor: '#38bdf8', fillOpacity: 0.35 }}
            onEachFeature={(f, layer) => layer.bindPopup(
              `<strong>${f.properties?.name || 'water'}</strong><br/>${f.properties?.tag || ''}`)} />
        )}

        {layers.demo && demoGrid && (
          <GeoJSON data={demoGrid}
            style={{ color: '#f87171', weight: 1, dashArray: '3 3', fillOpacity: 0.02 }} />
        )}

        {layers.infrastructure && roads.features.length > 0 && (
          <GeoJSON key={`rd-${roads.features.length}`} data={roads}
            style={{ color: '#64748b', weight: 1.3, opacity: 0.7 }} />
        )}

        {layers.infrastructure && pois.map((f) => {
          const [lng, lat] = f.geometry.coordinates
          const kind = f.properties?.kind || 'other'
          return (
            <CircleMarker key={`${f.properties?.osm_id}-${kind}`} center={[lat, lng]}
              radius={5} pathOptions={{ color: POI_COLOR[kind] || '#94a3b8', weight: 1, fillOpacity: 0.85 }}>
              <Popup><strong>{f.properties?.name || '(unnamed)'}</strong><br />{kind}</Popup>
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

      <div className="map-legend">
        <div style={{ fontWeight: 600, marginBottom: 4, color: 'var(--text-dim)' }}>Legend</div>
        <div className="lg-row"><span className="sw line" style={{ background: '#38bdf8' }} /> Boundary / rivers</div>
        {layers.hydrology && <div className="lg-row"><span className="sw" style={{ background: '#38bdf8' }} /> Water bodies</div>}
        {layers.infrastructure && <>
          <div className="lg-row"><span className="sw line" style={{ background: '#64748b' }} /> Major roads</div>
          <div className="lg-row"><span className="sw" style={{ background: '#f87171' }} /> Hospital / clinic</div>
          <div className="lg-row"><span className="sw" style={{ background: '#fbbf24' }} /> School / college</div>
          <div className="lg-row"><span className="sw" style={{ background: '#c084fc' }} /> Rail station</div>
        </>}
        {layers.landuse && <>
          <div className="lg-row"><span className="sw" style={{ background: '#4ade80' }} /> Farmland</div>
          <div className="lg-row"><span className="sw" style={{ background: '#fb923c' }} /> Residential / built</div>
        </>}
        {(notes.infra || notes.hydro || notes.landuse) && (
          <div className="lg-row faint" style={{ marginTop: 6 }}>
            {notes.landuse === 'loading…' ? 'land use loading…' : (notes.infra || notes.hydro || notes.landuse)}
          </div>
        )}
      </div>
    </div>
  )
}
