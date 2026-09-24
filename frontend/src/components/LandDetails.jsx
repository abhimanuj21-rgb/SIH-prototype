// "Land details" — the deeper, per-topic view under the verdict: terrain
// cross-sections, soil make-up, monthly climate, air quality and everyday
// amenities. Every number comes from profile.details (see
// backend/services/land_details.py); a topic the platform could not verify
// renders its gap reason instead of a chart.
import { useCallback, useEffect, useState } from 'react'
import api from '../services/api.js'
import Reveal from './Reveal.jsx'
import { fmtDist } from './LandReport.jsx'

const C = { site: '#2A78D6', second: '#EB6834', dark: '#1C5CAB', grid: '#ECE8DF', ink: '#6B655C' }

function Gap({ d, what }) {
  return (
    <div className="ld-gap">
      <strong>{what} not available here.</strong> {d?.reason || 'The source did not return data.'}
      {d?.resolution && <div className="faint">{d.resolution}</div>}
    </div>
  )
}

function Src({ children }) {
  return <p className="ld-src">{children}</p>
}

// --- generic small charts (SVG, hover tooltips) --------------------------------
function Columns({ data, valueKey, labelKey, unit, color = C.site, refs = [], height = 170, fmt,
                   colorFn, labelEvery = 1 }) {
  const [hi, setHi] = useState(null)
  const W = 760, H = height, L = 40, R = 8, T = 12, B = 22
  const vals = data.map((d) => d[valueKey]).filter((v) => v != null)
  const max = Math.max(...vals, ...refs.map((r) => r.value), 1) * 1.1
  const bw = (W - L - R) / data.length
  const y = (v) => T + (H - T - B) * (1 - v / max)
  const ticks = niceTicks(max)
  const f = fmt || ((v) => `${v} ${unit}`)
  return (
    <div className="ld-chart" onMouseLeave={() => setHi(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${valueKey} by ${labelKey}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke={C.grid} />
            <text x={L - 5} y={y(t) + 3} textAnchor="end" className="ld-ax">{t}</text>
          </g>
        ))}
        {data.map((d, i) => {
          const v = d[valueKey]
          return (
            <g key={i} onMouseEnter={() => setHi(i)}>
              <rect x={L + i * bw} y={T} width={bw} height={H - T - B} fill="transparent" />
              {v != null && (
                <rect x={L + i * bw + bw * 0.14} y={y(v)} width={bw * 0.72} height={Math.max(0, H - B - y(v))}
                      rx="3" fill={colorFn ? colorFn(d) : color} opacity={hi == null || hi === i ? 1 : 0.45} />
              )}
              {i % labelEvery === 0 && (
                <text x={L + i * bw + bw / 2} y={H - 7} textAnchor="middle" className="ld-ax">{d[labelKey]}</text>
              )}
            </g>
          )
        })}
        {refs.map((r) => (
          <g key={r.label}>
            <line x1={L} x2={W - R} y1={y(r.value)} y2={y(r.value)} stroke={r.color || '#1C1A17'} strokeWidth="1.2" />
            <text x={W - R - 2} y={y(r.value) - 4} textAnchor="end" className="ld-ref">{r.label}</text>
          </g>
        ))}
      </svg>
      {hi != null && data[hi][valueKey] != null && (
        <div className="ld-tip" style={{ left: `${((L + (hi + 0.5) * bw) / W) * 100}%` }}>
          <strong>{data[hi][labelKey]}</strong> · {f(data[hi][valueKey])}
        </div>
      )}
    </div>
  )
}

function niceTicks(max) {
  const raw = max / 4
  const mag = Math.pow(10, Math.floor(Math.log10(raw || 1)))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => raw <= s) || mag * 10
  const out = []
  for (let t = 0; t <= max; t += step) out.push(Math.round(t * 100) / 100)
  return out
}

function Profile({ we, sn }) {
  const [hi, setHi] = useState(null)
  const W = 760, H = 220, L = 46, R = 12, T = 14, B = 26
  const all = [...we, ...sn].map((p) => p.elevation_m)
  const lo = Math.min(...all), hiZ = Math.max(...all)
  const pad = Math.max(2, (hiZ - lo) * 0.15)
  const zmin = Math.floor(lo - pad), zmax = Math.ceil(hiZ + pad)
  const x = (d) => L + ((d + 1000) / 2000) * (W - L - R)
  const y = (z) => T + (H - T - B) * (1 - (z - zmin) / (zmax - zmin))
  const path = (s) => s.map((p, i) => `${i ? 'L' : 'M'}${x(p.offset_m)},${y(p.elevation_m)}`).join(' ')
  const ticks = [zmin, Math.round((zmin + zmax) / 2), zmax]
  const idx = hi == null ? null : hi
  return (
    <div className="ld-chart" onMouseLeave={() => setHi(null)}
         onMouseMove={(e) => {
           const r = e.currentTarget.getBoundingClientRect()
           const px = ((e.clientX - r.left) / r.width) * W
           const i = Math.round(((px - L) / (W - L - R)) * 20)
           setHi(i >= 0 && i <= 20 ? i : null)
         }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Ground elevation cross-sections through the site">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke={C.grid} />
            <text x={L - 5} y={y(t) + 3} textAnchor="end" className="ld-ax">{t} m</text>
          </g>
        ))}
        {[-1000, -500, 0, 500, 1000].map((d) => (
          <text key={d} x={x(d)} y={H - 8} textAnchor="middle" className="ld-ax">
            {d === 0 ? 'site' : `${d > 0 ? '+' : '−'}${Math.abs(d) / 1000} km`}
          </text>
        ))}
        <line x1={x(0)} x2={x(0)} y1={T} y2={H - B} stroke="#1C1A17" strokeWidth="1" />
        <path d={path(we)} fill="none" stroke={C.site} strokeWidth="2" />
        <path d={path(sn)} fill="none" stroke={C.second} strokeWidth="2" />
        <text x={W - R} y={y(we[20].elevation_m) - 6} textAnchor="end" className="ld-lab" fill={C.site}>West → East</text>
        <text x={W - R} y={y(sn[20].elevation_m) + 14} textAnchor="end" className="ld-lab" fill={C.second}>South → North</text>
        {idx != null && (
          <g>
            <line x1={x(we[idx].offset_m)} x2={x(we[idx].offset_m)} y1={T} y2={H - B} stroke="#948C80" />
            <circle cx={x(we[idx].offset_m)} cy={y(we[idx].elevation_m)} r="4" fill={C.site} stroke="#fff" strokeWidth="2" />
            <circle cx={x(sn[idx].offset_m)} cy={y(sn[idx].elevation_m)} r="4" fill={C.second} stroke="#fff" strokeWidth="2" />
          </g>
        )}
      </svg>
      {idx != null && (
        <div className="ld-tip" style={{ left: `${(x(we[idx].offset_m) / W) * 100}%` }}>
          <strong>{we[idx].offset_m === 0 ? 'At the site' : `${Math.abs(we[idx].offset_m)} m from site`}</strong><br />
          W→E: {we[idx].elevation_m} m · S→N: {sn[idx].elevation_m} m
        </div>
      )}
    </div>
  )
}

// Multi-series line chart on one % axis (land-cover shares by year).
const LC_SERIES = [['built_pct', 'Built-up', '#B4543A'], ['crops_pct', 'Cropland', '#C98500'],
  ['trees_pct', 'Trees', '#2F7D4A'], ['water_pct', 'Water', '#2A78D6']]

function ShareLines({ series }) {
  const [hi, setHi] = useState(null)
  const W = 760, H = 210, L = 40, R = 90, T = 12, B = 24
  const x = (i) => L + (i / Math.max(1, series.length - 1)) * (W - L - R)
  const y = (v) => T + (H - T - B) * (1 - v / 100)
  // end-of-line labels, nudged apart so equal values don't print on top of each other
  const labelY = {}
  let prev = -Infinity
  for (const [k] of [...LC_SERIES].sort((a, b) => y(series[series.length - 1][a[0]]) - y(series[series.length - 1][b[0]]))) {
    const want = y(series[series.length - 1][k]) + 4
    labelY[k] = Math.max(want, prev + 13)
    prev = labelY[k]
  }
  return (
    <div className="ld-chart" onMouseLeave={() => setHi(null)}
         onMouseMove={(e) => {
           const r = e.currentTarget.getBoundingClientRect()
           const px = ((e.clientX - r.left) / r.width) * W
           const i = Math.round(((px - L) / (W - L - R)) * (series.length - 1))
           setHi(i >= 0 && i < series.length ? i : null)
         }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Share of land-cover classes within ~300 m, by year">
        {[0, 25, 50, 75, 100].map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke={C.grid} />
            <text x={L - 5} y={y(t) + 3} textAnchor="end" className="ld-ax">{t}%</text>
          </g>
        ))}
        {series.map((s, i) => (
          <text key={s.year} x={x(i)} y={H - 7} textAnchor="middle" className="ld-ax">{s.year}</text>
        ))}
        {LC_SERIES.map(([k, label, col]) => {
          const last = series[series.length - 1][k]
          return (
            <g key={k}>
              <path fill="none" stroke={col} strokeWidth="2.2"
                    d={series.map((s, i) => `${i ? 'L' : 'M'}${x(i)},${y(s[k])}`).join(' ')} />
              {series.map((s, i) => <circle key={i} cx={x(i)} cy={y(s[k])} r={hi === i ? 4.5 : 2.5}
                                            fill={col} stroke="#fff" strokeWidth="1.5" />)}
              <text x={W - R + 8} y={labelY[k]} className="ld-lab" fill={col}>{label} {last}%</text>
            </g>
          )
        })}
        {hi != null && <line x1={x(hi)} x2={x(hi)} y1={T} y2={H - B} stroke="#948C80" />}
      </svg>
      {hi != null && (
        <div className="ld-tip" style={{ left: `${(x(hi) / W) * 100}%` }}>
          <strong>{series[hi].year}</strong> · site: {series[hi].site_class}<br />
          {LC_SERIES.map(([k, label]) => `${label} ${series[hi][k]}%`).join(' · ')}
        </div>
      )}
    </div>
  )
}

function LandCover({ d }) {
  if (!d?.value) return <Gap d={d} what="Satellite land cover" />
  const v = d.value, det = d.detail
  const tone = v.trend.startsWith('Urbanising') ? ' warn' : ''
  const mixCol = { 'Built area': '#B4543A', Crops: '#C98500', Trees: '#2F7D4A', Water: '#2A78D6',
    'Flooded vegetation': '#6FB7C9', Rangeland: '#C9B458', 'Bare ground': '#B8A58C' }
  return (
    <>
      <div className="ld-stats">
        <div><strong>{v.site_class}</strong><span>at the point in {v.year}</span></div>
        <div><strong>{v.site_class_first}</strong><span>at the point in {v.first_year}</span></div>
        <div><strong>{v.built_change_pp > 0 ? '+' : ''}{v.built_change_pp} pts</strong><span>built-up share since {v.first_year}</span></div>
        <div><strong>{v.crops_change_pp > 0 ? '+' : ''}{v.crops_change_pp} pts</strong><span>cropland share since {v.first_year}</span></div>
      </div>
      <p className={`ld-callout${tone}`}><strong>{v.trend}.</strong> {v.summary}</p>
      <div className="ld-sub">What the land around the point is, {v.first_year}–{v.year} (~600 m square)</div>
      <ShareLines series={det.series} />
      <div className="ld-sub">Mix in {v.year}</div>
      <div className="ld-stack" role="img" aria-label={det.latest_mix.map((m) => `${m.class} ${m.pct}%`).join(', ')}>
        {det.latest_mix.filter((m) => m.pct > 0).map((m) => (
          <span key={m.class} style={{ width: `${m.pct}%`, background: mixCol[m.class] || '#948C80' }}
                title={`${m.class} ${m.pct}%`}>{m.pct >= 12 && `${m.class} ${m.pct}%`}</span>
        ))}
      </div>
      <Src>Esri / Impact Observatory Sentinel-2 10 m land cover, annual {v.first_year}–{v.year}, sampled at 49 points
        ~100 m apart. Machine-learning classification (~85% accurate overall).</Src>
    </>
  )
}

function FloodScreen({ f }) {
  if (!f?.available) return null
  const cls = f.level === 'Elevated' ? ' warn' : f.level === 'Moderate' ? ' mid' : ''
  return (
    <div className={`ld-flood${cls}`}>
      <div className="ld-flood__h">
        <strong>Flood screening: {f.level}</strong>
        <span className="faint">{f.points} of {f.max_points} risk signs</span>
      </div>
      <ul>{f.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
      <div className="faint">{f.note}</div>
    </div>
  )
}

// --- topic cards ----------------------------------------------------------------
function Terrain({ d, flood }) {
  if (!d?.value) return <Gap d={d} what="Terrain" />
  const v = d.value
  return (
    <>
      <div className="ld-stats">
        <div><strong>{v.elevation_m} m</strong><span>above sea level</span></div>
        <div><strong>{v.slope_deg}°</strong><span>{v.slope_class.toLowerCase()} slope ({v.slope_pct}%)</span></div>
        <div><strong>{v.aspect || '—'}</strong><span>{v.aspect ? 'faces (downhill)' : 'too flat for a direction'}</span></div>
        <div><strong>{v.relative_to_1km_m > 0 ? '+' : ''}{v.relative_to_1km_m} m</strong><span>vs land within 1 km</span></div>
      </div>
      <p className={`ld-callout${v.relative_position.startsWith('Lower') ? ' warn' : ''}`}>
        <strong>{v.relative_position}.</strong> {v.relative_position_note}
      </p>
      <FloodScreen f={flood} />
      {d.detail && <>
        <div className="ld-sub">Ground cross-sections through the site (2 km each way)</div>
        <Profile we={d.detail.profile_west_east} sn={d.detail.profile_south_north} />
      </>}
      <Src>Copernicus DEM GLO-90 via Open-Meteo · 90 m grid, includes buildings/trees · relief within 1 km: {v.relief_within_1km_m} m</Src>
    </>
  )
}

function Soil({ d }) {
  if (!d?.value) return <Gap d={d} what="Modelled soil data" />
  const v = d.value
  const parts = [['Sand', v.sand_pct, '#D9B26F'], ['Silt', v.silt_pct, '#A89A85'], ['Clay', v.clay_pct, '#8A5A3C']]
  const total = parts.reduce((a, p) => a + (p[1] || 0), 0) || 100
  const phPos = v.ph == null ? null : ((Math.min(10, Math.max(4, v.ph)) - 4) / 6) * 100
  return (
    <>
      <div className="ld-lead">{v.texture_class}</div>
      {v.sampled_at && v.sampled_at !== 'at the site' && (
        <p className="ld-callout warn"><strong>Sampled nearby.</strong> Values are from the {v.sampled_at}.</p>
      )}
      <p className="muted" style={{ margin: '0 0 10px' }}>{v.texture_note}</p>
      <div className="ld-sub">Topsoil make-up (0–5 cm)</div>
      <div className="ld-stack" role="img" aria-label={parts.map((p) => `${p[0]} ${p[1]}%`).join(', ')}>
        {parts.map(([n, pct, col]) => (
          <span key={n} style={{ width: `${(pct / total) * 100}%`, background: col }} title={`${n} ${pct}%`}>
            {pct >= 12 && `${n} ${Math.round(pct)}%`}
          </span>
        ))}
      </div>
      {v.ph != null && <>
        <div className="ld-sub">Acidity (pH {v.ph} — {v.ph_note?.toLowerCase()})</div>
        <div className="ld-ph">
          <div className="ld-ph__bar" />
          <i style={{ left: `${phPos}%` }} />
          <div className="ld-ph__lab"><span>4 acidic</span><span>7 neutral</span><span>10 alkaline</span></div>
        </div>
      </>}
      <div className="ld-stats ld-stats--sm">
        <div><strong>{v.organic_carbon_g_per_kg ?? '—'}</strong><span>organic carbon g/kg ({v.organic_carbon_note?.toLowerCase()})</span></div>
        <div><strong>{v.nitrogen_g_per_kg ?? '—'}</strong><span>nitrogen g/kg</span></div>
        <div><strong>{v.cec_cmol_per_kg ?? '—'}</strong><span>CEC cmol/kg (nutrient holding)</span></div>
        <div><strong>{v.bulk_density_kg_per_dm3 ?? '—'}</strong><span>bulk density kg/dm³</span></div>
      </div>
      <Src>ISRIC SoilGrids 2.0 — a 250 m model, not a field survey. A soil test / NBSS&amp;LUP survey is still needed for a capability class.</Src>
    </>
  )
}

// --- live weather (current + forecast + measured cross-check) ------------------
function LiveWeather({ loc }) {
  const [w, setW] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [view, setView] = useState('24h')

  const load = useCallback(() => {
    if (!loc) return
    setBusy(true)
    api.liveWeather(loc.latitude, loc.longitude)
      .then((r) => { setW(r); setErr(null) })
      .catch(setErr)
      .finally(() => setBusy(false))
  }, [loc?.latitude, loc?.longitude]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    load()
    const t = setInterval(load, 10 * 60 * 1000) // matches the server-side cache
    return () => clearInterval(t)
  }, [load])

  if (err) return <div className="ld-gap"><strong>Live weather unavailable.</strong> {String(err.message || err)}</div>
  if (!w) return <div className="lw lw--loading"><div className="skeleton" style={{ height: 120 }} /></div>
  if (w.error) return <div className="ld-gap">{w.error}</div>
  const m = w.model
  if (!m?.available) return <div className="ld-gap"><strong>Live weather unavailable.</strong> {m?.reason}</div>
  const c = m.current, obs = w.observed, air = w.air_now, agree = w.agreement, norm = w.vs_normal

  return (
    <div className="lw">
      <div className="lw__head">
        <span className="lw__live"><i />Live now</span>
        <span className="faint">model time {c.time_local?.slice(11)} · fetched {w.fetched_at} · refreshes every 10 min</span>
        <button className="btn ghost lw__btn" onClick={load} disabled={busy}>{busy ? 'Refreshing…' : '↻ Refresh'}</button>
      </div>

      <div className="lw__now">
        <div className="lw__big">
          <span className="lw__icon" aria-hidden>{c.sky.icon}</span>
          <div>
            <strong>{c.temperature_c}°C</strong>
            <span>{c.sky.label} · feels like {c.feels_like_c}°C</span>
          </div>
        </div>
        <div className="lw__grid">
          <div><em>Humidity</em>{c.humidity_pct}%</div>
          <div><em>Wind</em>{c.wind_kmh} km/h {c.wind_from}{c.wind_gust_kmh ? ` · gusts ${c.wind_gust_kmh}` : ''}</div>
          <div><em>Rain now</em>{c.precipitation_mm} mm</div>
          <div><em>Cloud</em>{c.cloud_cover_pct}%</div>
          <div><em>UV index</em>{c.uv_index ?? '—'}{c.uv_note ? ` (${c.uv_note.toLowerCase()})` : ''}</div>
          <div><em>Pressure (sea level)</em>{c.pressure_hpa ? Math.round(c.pressure_hpa) : '—'} hPa</div>
          {air?.available && <div><em>Air now (US AQI)</em>{air.us_aqi} · {air.aqi_note}</div>}
          {air?.available && <div><em>PM2.5 now</em>{air.pm2_5} µg/m³</div>}
        </div>
      </div>

      {obs?.available ? (
        <div className={`lw__check${agree && agree.level !== 'close agreement' ? ' warn' : ''}`} title={obs.raw}>
          <strong>{agree ? `✓ Checked against a measured reading — ${agree.level}` : 'Nearest measured reading'}</strong>
          <span>
            {obs.station} ({obs.distance_km} km away) measured <b>{obs.temperature_c}°C</b>
            {obs.humidity_pct != null && <>, {obs.humidity_pct}% humidity</>}
            {obs.wind_kmh != null && <>, wind {obs.wind_kmh} km/h {obs.wind_from || ''}</>}
            {obs.visibility_km != null && <>, visibility {obs.visibility_km} km</>}
            {obs.weather && <>, {obs.weather}</>} — at {obs.observed_local}
            {obs.stale ? ' (older than 3 h)' : ` (${obs.age_minutes} min ago)`}.
            {agree && <> Difference from the model: {agree.difference_c > 0 ? '+' : ''}{agree.difference_c} °C.</>}
          </span>
        </div>
      ) : (
        <div className="lw__check warn"><strong>No measured cross-check.</strong> <span>{obs?.reason}</span></div>
      )}

      {norm?.available && <p className="lw__norm">📅 {norm.summary}</p>}

      <div className="lr-seg ld-seg" role="tablist">
        {[['24h', 'Next 24 hours'], ['7d', 'Next 7 days']].map(([k, l]) => (
          <button key={k} role="tab" aria-selected={view === k} className={view === k ? 'on' : ''} onClick={() => setView(k)}>{l}</button>
        ))}
      </div>
      {view === '24h' && <>
        <Columns data={m.next_24h} valueKey="temp_c" labelKey="time" unit="°C" color={C.second} height={140}
                 fmt={(t) => `${t} °C`} />
        <div className="ld-sub">Chance of rain</div>
        <Columns data={m.next_24h} valueKey="rain_chance_pct" labelKey="time" unit="%" height={110}
                 fmt={(p) => `${p}% chance of rain`} />
      </>}
      {view === '7d' && (
        <div className="lw__week">
          {m.forecast_7d.map((d) => (
            <div key={d.date} className="lw__day">
              <b>{d.weekday}</b>
              <span className="lw__dicon" title={d.sky.label}>{d.sky.icon}</span>
              <span className="lw__hi">{Math.round(d.max_c)}°</span>
              <span className="lw__lo">{Math.round(d.min_c)}°</span>
              <span className="lw__rain">💧 {d.rain_chance_pct ?? '—'}%</span>
              <span className="faint">{d.rain_mm} mm</span>
              <span className="faint">UV {d.uv_max ?? '—'}</span>
            </div>
          ))}
        </div>
      )}
      <Src>
        Current & forecast: Open-Meteo best-match weather models (a ~km grid value, not a site thermometer).
        Measured: NOAA Aviation Weather Center METAR (IMD airport stations). Live air: CAMS via Open-Meteo.
      </Src>
    </div>
  )
}

function Climate({ d, loc }) {
  const [view, setView] = useState('rain')
  const normals = !d?.value || !d.detail ? null : d
  return (
    <>
      <LiveWeather loc={loc} />
      <div className="ld-divider">10-year climate normals</div>
      {normals ? <ClimateNormals d={normals} view={view} setView={setView} /> : <Gap d={d} what="Climate normals" />}
    </>
  )
}

function ClimateNormals({ d, view, setView }) {
  const v = d.value, det = d.detail
  const avgRain = det.yearly_rain.length
    ? Math.round(det.yearly_rain.reduce((a, y) => a + y.rain_mm, 0) / det.yearly_rain.length) : null
  return (
    <>
      <div className="ld-stats">
        <div><strong>{det.wettest_month}</strong><span>wettest month</span></div>
        <div><strong>{det.hottest_month}</strong><span>hottest month</span></div>
        <div><strong>{v.days_above_40c_per_year ?? '—'}</strong><span>days ≥ 40 °C a year</span></div>
        <div><strong>{v.solar_kwh_m2_day ?? '—'}</strong><span>kWh/m² sunshine per day</span></div>
      </div>
      <div className="lr-seg ld-seg" role="tablist">
        {[['rain', 'Monthly rain'], ['temp', 'Monthly heat'], ['years', 'Rain by year'], ['sun', 'Sunshine']].map(([k, l]) => (
          <button key={k} role="tab" aria-selected={view === k} className={view === k ? 'on' : ''} onClick={() => setView(k)}>{l}</button>
        ))}
      </div>
      {view === 'rain' && <Columns data={det.monthly} valueKey="rain_mm" labelKey="month" unit="mm" />}
      {view === 'temp' && <Columns data={det.monthly} valueKey="temp_max_c" labelKey="month" unit="°C" color={C.second}
                                   fmt={(t) => `${t} °C average daily high`} />}
      {view === 'years' && <Columns data={det.yearly_rain} valueKey="rain_mm" labelKey="year" unit="mm"
                                    refs={avgRain ? [{ value: avgRain, label: `average ${avgRain} mm` }] : []} />}
      {view === 'sun' && <Columns data={det.monthly} valueKey="solar_kwh_m2_day" labelKey="month" unit="kWh/m²/day" color="#C98500" />}
      <p className="faint" style={{ margin: '6px 0 0', fontSize: '.8rem' }}>
        {det.dry_months} dry month{det.dry_months === 1 ? '' : 's'} (&lt; 30 mm) a year on average ·
        {' '}{v.wet_days_per_year} wet days a year.
      </p>
      <Src>ERA5 reanalysis via Open-Meteo, {v.period} · ~9 km grid.</Src>
    </>
  )
}

// --- live air (Indian AQI, all six pollutants, trend, stations) ------------------
const AQI_SCALE = [[50, 'Good', '#2F7D4A'], [100, 'Satisfactory', '#7BAF3F'], [200, 'Moderate', '#D1A20A'],
  [300, 'Poor', '#E07B24'], [400, 'Very poor', '#C0392B'], [500, 'Severe', '#7B1F1F']]
const catColour = (name) => (AQI_SCALE.find((s) => s[1] === name) || [0, '', '#948C80'])[2]

function LiveAir({ loc }) {
  const [a, setA] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!loc) return
    setBusy(true)
    api.liveAir(loc.latitude, loc.longitude)
      .then((r) => { setA(r); setErr(null) })
      .catch(setErr)
      .finally(() => setBusy(false))
  }, [loc?.latitude, loc?.longitude]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    load()
    const t = setInterval(load, 10 * 60 * 1000)
    return () => clearInterval(t)
  }, [load])

  if (err) return <div className="ld-gap"><strong>Live air unavailable.</strong> {String(err.message || err)}</div>
  if (!a) return <div className="lw"><div className="skeleton" style={{ height: 140 }} /></div>
  if (a.error) return <div className="ld-gap">{a.error}</div>
  const m = a.model
  if (!m?.available) return <div className="ld-gap"><strong>Live air unavailable.</strong> {m?.reason}</div>
  const idx = m.india_aqi, st = a.stations
  const col = idx.available ? idx.category.colour : '#948C80'

  return (
    <div className="lw">
      <div className="lw__head">
        <span className="lw__live"><i />Live air now</span>
        <span className="faint">model hour {m.time_local?.slice(11)} · fetched {a.fetched_at} · refreshes every 10 min</span>
        <button className="btn ghost lw__btn" onClick={load} disabled={busy}>{busy ? 'Refreshing…' : '↻ Refresh'}</button>
      </div>

      {idx.available ? (
        <div className="la__top">
          <div className="la__aqi" style={{ borderColor: col }}>
            <strong style={{ color: col }}>{idx.aqi}</strong>
            <span>Indian AQI</span>
          </div>
          <div className="la__txt">
            <div className="la__cat" style={{ color: col }}>{idx.category.name}</div>
            <div className="muted">Main pollutant: <b>{idx.prominent_pollutant}</b>. {idx.category.health}</div>
            <div className="la__scale" role="img" aria-label={`Indian AQI ${idx.aqi} on a 0 to 500 scale`}>
              {AQI_SCALE.map(([top, name, c], i) => (
                <span key={name} style={{ background: c }} title={`${i ? AQI_SCALE[i - 1][0] + 1 : 0}–${top} ${name}`} />
              ))}
              <i style={{ left: `${Math.min(100, idx.aqi / 5)}%` }} />
            </div>
            <div className="la__scalelab"><span>0</span><span>100</span><span>200</span><span>300</span><span>400</span><span>500</span></div>
          </div>
        </div>
      ) : <div className="ld-gap">{idx.reason}</div>}

      <div className="la__pols">
        {m.pollutants.map((p) => (
          <div key={p.key} className="la__pol" title={p.what}>
            <div className="la__pn"><b>{p.name}</b><span>{p.what}</span></div>
            <div className="la__pv"><b>{p.now ?? '—'}</b> <small>{p.unit} now</small></div>
            <div className="la__pa">{p.average ?? '—'} <small>{p.average_window} avg</small></div>
            <div className="la__pb">
              <span style={{ width: `${Math.min(100, (p.sub_index || 0) / 5)}%`, background: catColour(p.category) }} />
            </div>
            <div className="la__ps" style={{ color: catColour(p.category) }}>{p.sub_index ?? '—'} · {p.category || '—'}</div>
          </div>
        ))}
      </div>

      <div className="ld-sub">PM2.5 — last 24 hours and next 24 hours</div>
      <Columns data={m.pm2_5_series} valueKey="pm2_5" labelKey="label" unit="µg/m³" height={150} labelEvery={4}
               colorFn={(d) => (d.now ? '#1C1A17' : d.past ? '#7A6F62' : '#C9C0B2')}
               refs={[{ value: 60, label: 'India 24-h limit 60' }]}
               fmt={(v) => `${v} µg/m³`} />
      <p className="faint" style={{ margin: '4px 0 0', fontSize: '.8rem' }}>
        Dark bars = past hours, black = now, light = forecast.
        {m.trend_next_24h && <> PM2.5 is <b>{m.trend_next_24h}</b> over the next 24 h (peak {m.next_24h_peak_pm2_5} µg/m³).</>}
        {m.dust != null && <> Dust now {m.dust} µg/m³.</>}
        {m.us_aqi != null && <> US AQI {m.us_aqi}.</>}
      </p>

      {st?.available ? (
        <div className="lw__check">
          <strong>✓ Measured by nearby monitoring stations</strong>
          {st.stations.map((s) => (
            <div key={s.name}>
              <b>{s.name}</b> ({s.distance_km} km{s.provider ? `, ${s.provider}` : ''}):{' '}
              {s.readings.length ? s.readings.map((r) => `${r.parameter} ${r.value} ${r.unit}`).join(' · ') : 'no recent readings'}
            </div>
          ))}
        </div>
      ) : (
        <div className="lw__check warn"><strong>Measured station readings</strong><span>{st?.reason}</span></div>
      )}
      <Src>
        Copernicus CAMS model via Open-Meteo (~45 km regional estimate). Indian AQI computed with CPCB National
        AQI breakpoints — 24-h averages for PM2.5, PM10, NO₂, SO₂ and 8-h for O₃, CO; the AQI is the highest sub-index.
      </Src>
    </div>
  )
}

function Air({ d, loc }) {
  return (
    <>
      <LiveAir loc={loc} />
      <div className="ld-divider">12-month average</div>
      <AirYear d={d} />
    </>
  )
}

function AirYear({ d }) {
  if (!d?.value) return <Gap d={d} what="Air quality" />
  const v = d.value, refs = d.detail?.references?.pm2_5
  const scaleMax = Math.max(60, v.pm2_5_annual_mean * 1.3)
  const pos = (x) => `${Math.min(100, (x / scaleMax) * 100)}%`
  return (
    <>
      <div className="ld-lead">{v.pm2_5_annual_mean} µg/m³ <small>PM2.5, 12-month average</small></div>
      <p className="muted" style={{ margin: '0 0 10px' }}>{v.summary}</p>
      <div className="ld-bullet" role="img" aria-label={`PM2.5 ${v.pm2_5_annual_mean}; WHO guideline 5; India annual standard 40`}>
        <div className="ld-bullet__fill" style={{ width: pos(v.pm2_5_annual_mean) }} />
        {refs && <>
          <i style={{ left: pos(refs.who_annual) }}><em>WHO {refs.who_annual}</em></i>
          <i style={{ left: pos(refs.naaqs_annual) }}><em>India limit {refs.naaqs_annual}</em></i>
        </>}
      </div>
      {d.detail?.monthly_pm2_5 && <>
        <div className="ld-sub">Monthly average PM2.5</div>
        <Columns data={d.detail.monthly_pm2_5.map((m) => ({ ...m, label: m.month.slice(5) + '/' + m.month.slice(2, 4) }))}
                 valueKey="pm2_5" labelKey="label" unit="µg/m³" color="#7A6F62" height={150}
                 refs={refs ? [{ value: refs.naaqs_annual, label: 'India annual limit 40' }] : []} />
      </>}
      <div className="ld-stats ld-stats--sm">
        <div><strong>{v.pm10_annual_mean}</strong><span>PM10 µg/m³ average (limit 60)</span></div>
        <div><strong>{v.days_pm2_5_above_naaqs_24h}</strong><span>days PM2.5 above the 24-hour limit (60)</span></div>
      </div>
      <Src>CAMS global model via Open-Meteo (~45 km) — a regional background level, not a street-side reading.</Src>
    </>
  )
}

function Amenities({ a }) {
  if (!a?.available) return <Gap d={a} what="Amenity data" />
  const rows = a.groups
  const max = Math.max(1, ...rows.map((g) => g.within_1km))
  return (
    <>
      <div className="ld-stats ld-stats--sm">
        <div><strong>{a.total_within_500m}</strong><span>within 500 m</span></div>
        <div><strong>{a.total_within_1km}</strong><span>within 1 km</span></div>
        <div><strong>{a.groups_within_1km}</strong><span>kinds within 1 km</span></div>
      </div>
      {rows.length === 0 && <p className="muted">Nothing of these kinds is mapped within 5 km.</p>}
      <div className="ld-amen">
        <div className="ld-amen__legend">
          <span><i style={{ background: C.dark }} />within 500 m</span>
          <span><i style={{ background: '#9EC5F4' }} />within 1 km</span>
        </div>
        {rows.map((g) => (
          <div key={g.group} className="ld-amen__row">
            <span className="ld-amen__n">{g.group}</span>
            <span className="ld-amen__t">
              <span style={{ width: `${(g.within_1km / max) * 100}%`, background: '#9EC5F4' }} />
              <span style={{ width: `${(g.within_500m / max) * 100}%`, background: C.dark }} />
            </span>
            <span className="ld-amen__c">{g.within_1km}</span>
            <span className="ld-amen__near">
              nearest {fmtDist(g.nearest_m)}{g.nearest_name ? ` · ${g.nearest_name}` : ''}
            </span>
          </div>
        ))}
      </div>
      <Src>{a.note}</Src>
    </>
  )
}

function Locality({ d }) {
  if (!d?.value) return <Gap d={d} what="Locality" />
  const v = d.value
  const rows = [['Road', v.road], ['Neighbourhood', v.neighbourhood], ['Ward / village', v.suburb_or_village],
    ['City / town', v.city], ['Taluk / sub-district', v.sub_district], ['District', v.district],
    ['State', v.state], ['PIN code', v.postcode]].filter((r) => r[1])
  return (
    <>
      <table className="kv"><tbody>
        {rows.map(([k, val]) => <tr key={k}><td>{k}</td><td><strong>{val}</strong></td></tr>)}
      </tbody></table>
      <Src>Nominatim (OpenStreetMap) — names as mapped, not an official revenue-village lookup.</Src>
    </>
  )
}

const TABS = [
  ['terrain', '⛰ Terrain & flood'], ['landcover', '🛰 Land cover'], ['soil', '🟫 Soil'], ['climate', '🌦 Climate & live weather'],
  ['air', '💨 Air (live)'], ['amenities', '🏪 Amenities'], ['locality', '📍 Locality'],
]

export default function LandDetails({ details, location }) {
  // remembered for the session, so switching locations keeps the tab you were reading
  const [tab, setTabState] = useState(() => {
    try { return sessionStorage.getItem('ndp.detailsTab') || 'terrain' } catch { return 'terrain' }
  })
  const setTab = (k) => {
    setTabState(k)
    try { sessionStorage.setItem('ndp.detailsTab', k) } catch { /* storage blocked */ }
  }
  if (!details) return null
  const ok = {
    terrain: !!details.terrain?.value, soil: !!details.soil?.value, landcover: !!details.land_cover?.value,
    climate: !!details.climate?.value, air: !!details.air_quality?.value,
    amenities: !!details.amenities?.available, locality: !!details.locality?.value,
  }
  return (
    <Reveal className="card ld">
      <div className="card__head">
        <div>
          <h3>Land details</h3>
          <span className="faint">Ground, soil, weather, air and what's around — each from a named open dataset.</span>
        </div>
      </div>
      <div className="ld-tabs" role="tablist">
        {TABS.map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`${tab === k ? 'on' : ''}${ok[k] ? '' : ' off'}`}
                  onClick={() => setTab(k)}>
            {l}{!ok[k] && <em>gap</em>}
          </button>
        ))}
      </div>
      <div className="ld-body">
        {tab === 'terrain' && <Terrain d={details.terrain} flood={details.flood_screening} />}
        {tab === 'landcover' && <LandCover d={details.land_cover} />}
        {tab === 'soil' && <Soil d={details.soil} />}
        {tab === 'climate' && <Climate d={details.climate} loc={location} />}
        {tab === 'air' && <Air d={details.air_quality} loc={location} />}
        {tab === 'amenities' && <Amenities a={details.amenities} />}
        {tab === 'locality' && <Locality d={details.locality} />}
      </div>
    </Reveal>
  )
}
