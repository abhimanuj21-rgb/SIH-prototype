import { Skeleton, ErrorBox } from './Bits.jsx'

function categoryChip(cat) {
  const c = (cat || '').toLowerCase()
  if (c.includes('agri')) return 'chip agri'
  if (c.includes('built')) return 'chip built'
  if (c.includes('water')) return 'chip water'
  if (c.includes('natural') || c.includes('rural') || c.includes('open')) return 'chip rural'
  return 'chip'
}

function Dist({ d }) {
  if (d == null) return <span className="faint">not mapped nearby</span>
  return <strong>{d >= 1000 ? `${(d / 1000).toFixed(1)} km` : `${d} m`}</strong>
}

export default function SiteContext({ data, loading, error }) {
  if (loading) {
    return (
      <div className="card">
        <div className="section-title">Site character (live OpenStreetMap)</div>
        <div className="site-grid">
          {[0, 1, 2].map((i) => (
            <div className="site-card" key={i}><Skeleton lines={4} /></div>
          ))}
        </div>
        <p className="faint" style={{ marginTop: 10, marginBottom: 0 }}>
          Querying Overpass — first lookup for an area can take up to a minute,
          then it is cached.
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <div className="section-title">Site character</div>
        <ErrorBox error={error} />
      </div>
    )
  }

  if (!data) return null
  if (!data.available) {
    return (
      <div className="card">
        <div className="section-title">Site character</div>
        <p className="error-box">{data.reason || 'OSM site context unavailable for this point.'}</p>
      </div>
    )
  }

  const { water, land_use: land, development: dev } = data
  const wc = water?.available !== false ? water : null
  const lc = land?.available !== false ? land : null

  return (
    <div className="card">
      <div className="section-title">Site character — OpenStreetMap (cached AOI layers)</div>
      <div className="site-grid">

        {/* WATER */}
        <div className="site-card">
          <h4>💧 Water source &amp; bodies</h4>
          {!wc && <p className="error-box">{water?.reason}</p>}
          {wc && <>
            <p>{wc.summary}</p>
            <table className="kv"><tbody>
              <tr><td>Nearest river / stream</td><td>
                {wc.nearest_river_or_stream?.name
                  ? <>{wc.nearest_river_or_stream.name} — <Dist d={wc.nearest_river_or_stream.distance_m} /></>
                  : <Dist d={wc.nearest_river_or_stream?.distance_m} />}
              </td></tr>
              <tr><td>Nearest tank / pond / lake</td><td>
                {wc.nearest_waterbody?.name
                  ? <>{wc.nearest_waterbody.name} — <Dist d={wc.nearest_waterbody.distance_m} /></>
                  : <Dist d={wc.nearest_waterbody?.distance_m} />}
              </td></tr>
              <tr><td>Nearest canal / channel</td><td><Dist d={wc.nearest_canal_or_drain?.distance_m} /></td></tr>
              <tr><td>Within 2.5 km</td><td>
                {wc.counts_within_2_5km.rivers_streams} rivers/streams · {wc.counts_within_2_5km.waterbodies} waterbodies · {wc.counts_within_2_5km.canals_drains} canals
              </td></tr>
              <tr><td>Coast / sea</td><td className="faint">{wc.coast.note}</td></tr>
            </tbody></table>
          </>}
        </div>

        {/* LAND USE */}
        <div className="site-card">
          <h4>🌾 Land use — agricultural or built?</h4>
          {!lc && <p className="error-box">{land?.reason}</p>}
          {lc && <>
            <div className="lead-val">
              <span className={categoryChip(lc.effective_category)}>{lc.effective_category}</span>
            </div>
            <p>{lc.summary}</p>
            <div className="mini">
              {lc.on_parcel
                ? <>OSM tag on this point: <code>{lc.on_parcel.osm_tag}</code>{lc.on_parcel.name ? ` (${lc.on_parcel.name})` : ''}</>
                : 'No land-use polygon on the exact point.'}
            </div>
            {Object.keys(lc.nearby_tags_within_600m || {}).length > 0 && (
              <div className="mini" style={{ marginTop: 6 }}>
                Within 600 m: {Object.entries(lc.nearby_tags_within_600m)
                  .sort((a, b) => b[1] - a[1]).slice(0, 6)
                  .map(([k, v]) => `${k}×${v}`).join(', ')}
              </div>
            )}
            <div className="mini" style={{ marginTop: 6 }}>
              Definitive land cover needs the Esri/Sentinel-2 raster (still a data gap).
            </div>
          </>}
        </div>

        {/* DEVELOPMENT */}
        <div className="site-card">
          <h4>🏗️ How developed is it?</h4>
          <div className="lead-val">{dev.level}</div>
          <p>{dev.summary}</p>
          <table className="kv"><tbody>
            <tr><td>Built-up land parcels ≤600 m</td><td><strong>{dev.built_landuse_polys_within_600m}</strong></td></tr>
            <tr><td>Farmland parcels ≤600 m</td><td><strong>{dev.agricultural_landuse_polys_within_600m}</strong></td></tr>
            <tr><td>Major road segments ≤600 m</td><td><strong>{dev.major_road_segments_within_600m}</strong></td></tr>
            <tr><td>Mapped facilities ≤600 m</td><td><strong>{dev.mapped_facilities_within_600m}</strong></td></tr>
          </tbody></table>
          <div className="mini" style={{ marginTop: 6 }}>{dev.method}</div>
        </div>
      </div>

      <p className="faint" style={{ margin: '12px 0 0' }}>
        Source: {data.provenance?.source}. {data.provenance?.note}
      </p>
    </div>
  )
}
