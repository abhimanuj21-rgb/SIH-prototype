import { useEffect, useMemo, useState } from 'react'
import {
  MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, Marker,
  LayersControl, useMap, useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import api from '../services/api.js'

const CITY_CENTERS = {
  madurai: { center: [9.925, 78.119], zoom: 12 },
  bhopal: { center: [23.2599, 77.4126], zoom: 12 },
  kovilpatti: { center: [9.1744, 77.8683], zoom: 13 },
}
const POI_MIN_ZOOM = 13

const pickIcon = L.divIcon({
  className: '',
  html: '<div style="width:16px;height:16px;border-radius:50%;background:#38bdf8;border:2px solid #fff;box-shadow:0 0 0 3px rgba(56,189,248,.5)"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
})

// stroke stays white for contrast on satellite; fill carries the meaning
const POI = {
  hospital:     { fill: '#ef4444', label: 'Hospital' },
  clinic:       { fill: '#f59e0b', label: 'Clinic / doctor' },
  school:       { fill: '#22c55e', label: 'School' },
  college:      { fill: '#3b82f6', label: 'College / university' },
  rail_station: { fill: '#a855f7', label: 'Railway station' },
  other:        { fill: '#94a3b8', label: 'Other' },
}
const LU_COLOR = {
  farmland: '#4ade80', farmyard: '#4ade80', orchard: '#22c55e',
  residential: '#fb923c', commercial: '#f97316', retail: '#f97316',
  industrial: '#a16207', construction: '#eab308', forest: '#15803d',
  meadow: '#84cc16', quarry: '#78716c',
}

function osmUrl(p) {
  const t = p?.osm_type || 'node'
  return p?.osm_id ? `https://www.openstreetmap.org/${t}/${p.osm_id}` : null
}

function FixSize() {
  const map = useMap()
  useEffect(() => {
    const t = setTimeout(() => map.invalidateSize(), 220)
    return () => clearTimeout(t)
  }, [map])
  return null
}

function Recenter({ center, zoom }) {
  const map = useMap()
  useEffect(() => { map.setView(center, zoom) }, [center, zoom]) // eslint-disable-line
  return null
}

function MapEvents({ onPick, onZoom }) {
  const map = useMapEvents({
    click(e) { onPick?.({ lat: +e.latlng.lat.toFixed(6), lng: +e.latlng.lng.toFixed(6) }) },
    zoomend() { onZoom?.(map.getZoom()) },
  })
  useEffect(() => { onZoom?.(map.getZoom()) }, []) // eslint-disable-line
  return null
}

export default function MapView({
  picked, onPick, city = 'madurai', onDemoGridStats,
  layers = { infrastructure: true, hydrology: true, landuse: false, demo: false },
}) {
  const [boundary, setBoundary] = useState(null)
  const [boundaryIsDemo, setBoundaryIsDemo] = useState(false)
  const [infra, setInfra] = useState(null)
  const [hydro, setHydro] = useState(null)
  const [landuse, setLanduse] = useState(null)
  const [demoGrid, setDemoGrid] = useState(null)
  const [notes, setNotes] = useState({})
  const [zoom, setZoom] = useState(12)

  const note = (k, v) => setNotes((n) => ({ ...n, [k]: v }))
  const view = CITY_CENTERS[city] || CITY_CENTERS.madurai

  // Switching cities invalidates every previously-fetched layer — each
  // effect below re-fetches for the new city once its cached state is null.
  useEffect(() => {
    setBoundary(null); setInfra(null); setHydro(null); setLanduse(null)
    setDemoGrid(null); setNotes({})
  }, [city])

  useEffect(() => {
    api.boundary(city).then((r) => {
      if (r?.available) { setBoundary(r.geojson); setBoundaryIsDemo(!!r.is_demo) }
    }).catch(() => {})
  }, [city])

  useEffect(() => {
    if (!layers.infrastructure || infra) return
    api.infrastructure(city)
      .then((r) => r?.available ? setInfra(r.geojson) : note('infra', r?.reason))
      .catch((e) => note('infra', e.message))
  }, [layers.infrastructure, city]) // eslint-disable-line

  useEffect(() => {
    if (!layers.hydrology || hydro) return
    api.hydrology(city)
      .then((r) => r?.available ? setHydro(r.geojson) : note('hydro', r?.reason))
      .catch((e) => note('hydro', e.message))
  }, [layers.hydrology, city]) // eslint-disable-line

  useEffect(() => {
    if (!layers.landuse || landuse) return
    note('landuse', 'loading…')
    api.landuse(city)
      .then((r) => { if (r?.available) { setLanduse(r.geojson); note('landuse', null) } else note('landuse', r?.reason) })
      .catch((e) => note('landuse', e.message))
  }, [layers.landuse, city]) // eslint-disable-line

  useEffect(() => {
    if (!layers.demo) { setDemoGrid(null); onDemoGridStats?.(null); return }
    api.demoGrid(city).then((r) => {
      setDemoGrid(r.geojson)
      const areas = (r.geojson?.features || []).map((f) => f.properties.area_sqm)
      if (areas.length) {
        const total = areas.reduce((a, b) => a + b, 0)
        onDemoGridStats?.({ count: areas.length, totalSqm: total, avgSqm: total / areas.length })
      }
    }).catch(() => {})
  }, [layers.demo, city]) // eslint-disable-line

  const pois = useMemo(
    () => (infra?.features || []).filter((f) => f.geometry?.type === 'Point'),
    [infra],
  )
  const roads = useMemo(() => ({
    type: 'FeatureCollection',
    features: (infra?.features || []).filter((f) => f.geometry?.type === 'LineString'),
  }), [infra])

  const showPois = layers.infrastructure && zoom >= POI_MIN_ZOOM
  const poiKinds = useMemo(
    () => [...new Set(pois.map((f) => f.properties?.kind || 'other'))],
    [pois],
  )

  return (
    <div className="map-wrap">
      <MapContainer center={view.center} zoom={view.zoom} scrollWheelZoom>
        <FixSize />
        <Recenter center={view.center} zoom={view.zoom} />
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="OSM Standard">
            <TileLayer maxZoom={18}
              attribution='&copy; OpenStreetMap contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite (Esri)">
            <TileLayer maxZoom={19}
              attribution='Imagery &copy; Esri, Maxar, Earthstar Geographics'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Light (Esri)">
            <TileLayer maxZoom={16} attribution='Tiles &copy; Esri'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Dark (Esri)">
            <TileLayer maxZoom={16} attribution='Tiles &copy; Esri'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="OSM Humanitarian">
            <TileLayer maxZoom={18}
              attribution='&copy; OpenStreetMap contributors, HOT'
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
            style={(f) => ({ color: LU_COLOR[f.properties?.tag] || '#64748b', weight: 1, fillOpacity: 0.18 })}
            onEachFeature={(f, layer) => layer.bindPopup(
              `<strong>${f.properties?.name || 'land use'}</strong><br/>landuse=${f.properties?.tag}`)} />
        )}

        {layers.hydrology && hydro && (
          <GeoJSON key={`hy-${hydro.features.length}`} data={hydro}
            style={(f) => f.geometry.type === 'LineString'
              ? { color: '#38bdf8', weight: 1.2, opacity: 0.55 }
              : { color: '#38bdf8', weight: 0.6, fillColor: '#38bdf8', fillOpacity: 0.22 }}
            onEachFeature={(f, layer) => layer.bindPopup(
              `<strong>${f.properties?.name || 'water'}</strong><br/>${f.properties?.tag || ''}`)} />
        )}

        {layers.demo && demoGrid && (
          <GeoJSON key={`cad-${city}-${demoGrid.features.length}`} data={demoGrid}
            style={{ color: '#f87171', weight: 1, dashArray: '3 3', fillOpacity: 0.02 }}
            onEachFeature={(f, layer) => {
              const p = f.properties || {}
              layer.bindPopup(
                `<strong>${p.demo_parcel_id}</strong> <em>(DEMO — not a real parcel)</em><br/>` +
                `${p.area_sqm.toLocaleString()} m² · ${p.area_cents.toLocaleString()} cents · ` +
                `${p.area_sqft.toLocaleString()} sq ft`)
              layer.on('mouseover', () => layer.setStyle({ fillOpacity: 0.22, weight: 2 }))
              layer.on('mouseout', () => layer.setStyle({ fillOpacity: 0.02, weight: 1 }))
            }} />
        )}

        {layers.infrastructure && roads.features.length > 0 && (
          <GeoJSON key={`rd-${roads.features.length}`} data={roads}
            style={{ color: '#64748b', weight: 1.3, opacity: 0.7 }} />
        )}

        {showPois && pois.map((f) => {
          const [lng, lat] = f.geometry.coordinates
          const p = f.properties || {}
          const kind = p.kind || 'other'
          const meta = POI[kind] || POI.other
          const url = osmUrl(p)
          return (
            <CircleMarker key={`${p.osm_type}-${p.osm_id}`} center={[lat, lng]}
              radius={kind === 'hospital' ? 6 : 5}
              pathOptions={{ color: '#fff', weight: 1.5, fillColor: meta.fill, fillOpacity: 0.95 }}>
              <Popup>
                <strong>{p.name || `(unnamed ${meta.label.toLowerCase()})`}</strong><br />
                <span style={{ color: 'var(--text-dim)' }}>{meta.label} · <code>{p.osm_tag}</code></span>
                {p.operator ? <><br />operator: {p.operator}</> : null}
                {url && <><br /><a href={url} target="_blank" rel="noreferrer">verify / fix on OpenStreetMap ↗</a></>}
              </Popup>
            </CircleMarker>
          )
        })}

        {picked && (
          <Marker position={[picked.lat, picked.lng]} icon={pickIcon}>
            <Popup>{picked.lat}, {picked.lng}</Popup>
          </Marker>
        )}

        <MapEvents onPick={onPick} onZoom={setZoom} />
      </MapContainer>

      <div className="map-legend">
        <div style={{ fontWeight: 600, marginBottom: 4, color: 'var(--text-dim)' }}>Legend</div>
        <div className="lg-row"><span className="sw line" style={{ background: '#38bdf8' }} /> Boundary / rivers</div>
        {layers.hydrology && <div className="lg-row"><span className="sw" style={{ background: '#38bdf8' }} /> Water bodies</div>}
        {layers.infrastructure && <>
          <div className="lg-row"><span className="sw line" style={{ background: '#64748b' }} /> Major roads</div>
          {(showPois ? poiKinds : Object.keys(POI).filter((k) => k !== 'other')).map((k) => (
            <div className="lg-row" key={k}><span className="sw" style={{ background: POI[k]?.fill }} /> {POI[k]?.label || k}</div>
          ))}
        </>}
        {layers.landuse && <>
          <div className="lg-row"><span className="sw" style={{ background: '#4ade80' }} /> Farmland</div>
          <div className="lg-row"><span className="sw" style={{ background: '#fb923c' }} /> Residential / built</div>
        </>}
        {layers.demo && <>
          <div className="lg-row"><span className="sw line" style={{ background: '#f87171' }} /> Demo cadastral parcels</div>
          <div className="lg-row faint" style={{ marginTop: 2 }}>Click a parcel for its (synthetic) area</div>
        </>}
        {layers.infrastructure && !showPois && (
          <div className="lg-row faint" style={{ marginTop: 6 }}>Zoom in to see facilities</div>
        )}
        {layers.infrastructure && showPois && (
          <div className="lg-row faint" style={{ marginTop: 6 }}>Facilities are OSM data — click to verify</div>
        )}
        {(notes.infra || notes.hydro || (notes.landuse && notes.landuse !== 'loading…')) && (
          <div className="lg-row faint" style={{ marginTop: 6 }}>
            {notes.infra || notes.hydro || notes.landuse}
          </div>
        )}
        {notes.landuse === 'loading…' && (
          <div className="lg-row faint" style={{ marginTop: 6 }}>land use loading…</div>
        )}
      </div>
    </div>
  )
}
