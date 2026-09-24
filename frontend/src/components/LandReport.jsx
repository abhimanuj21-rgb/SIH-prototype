// The plain-language "outcome" view of a location: verdict, access vs the
// city core, indicative use fit, and how much of the picture is verified.
// Everything rendered here comes from /evidence/land-profile — no values are
// computed or invented client-side beyond formatting.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Reveal from './Reveal.jsx'

export function fmtDist(d) {
  if (d == null) return 'not mapped'
  return d >= 1000 ? `${(d / 1000).toFixed(1)} km` : `${Math.round(d)} m`
}

const TONE = {
  Excellent: 'good', 'Strong fit': 'good', Good: 'ok', 'Possible fit': 'warn',
  Fair: 'warn', 'Weak fit': 'bad', Poor: 'bad', 'Not scored': 'none',
}
const ICON = { good: '●', ok: '●', warn: '◐', bad: '○', none: '–' }

export function ToneBadge({ label }) {
  const t = TONE[label] || 'none'
  return <span className={`lr-tone lr-tone--${t}`}><span aria-hidden>{ICON[t]}</span>{label}</span>
}

// --- verdict ---------------------------------------------------------------
function Gauge({ score, label }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    if (score == null) return
    let raf, start
    const step = (t) => {
      start ??= t
      const k = Math.min(1, (t - start) / 900)
      setShown(Math.round(score * (1 - Math.pow(1 - k, 3))))
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [score])
  const r = 52, c = 2 * Math.PI * r
  const tone = TONE[label] || 'none'
  return (
    <div className={`lr-gauge lr-gauge--${tone}`} role="img"
         aria-label={`Access score ${score ?? 'not available'} out of 100, ${label}`}>
      <svg viewBox="0 0 128 128">
        <circle cx="64" cy="64" r={r} className="lr-gauge__track" />
        <circle cx="64" cy="64" r={r} className="lr-gauge__arc"
                strokeDasharray={c} strokeDashoffset={c * (1 - (score == null ? 0 : shown / 100))}
                transform="rotate(-90 64 64)" />
      </svg>
      <div className="lr-gauge__label">
        <strong>{score == null ? '—' : shown}</strong>
        <span>out of 100</span>
      </div>
    </div>
  )
}

// Fetches the PDF as a file so the button can show progress (the server
// gathers live weather + air first, which takes a few seconds).
function PdfButton({ url, filename }) {
  const [state, setState] = useState('idle') // idle | busy | error
  async function download() {
    setState('busy')
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(res.statusText)
      const blob = await res.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(a.href), 10000)
      setState('idle')
    } catch {
      setState('error')
    }
  }
  return (
    <button className="btn" onClick={download} disabled={state === 'busy'}>
      {state === 'busy' ? '⏳ Preparing PDF…' : state === 'error' ? '⚠ Retry PDF download' : '⬇ Download PDF report'}
    </button>
  )
}

// Copies the current page address — the URL carries ?lat=&lon=, so whoever
// opens it lands on this same report.
function ShareButton() {
  const [copied, setCopied] = useState(false)
  async function share() {
    const url = window.location.href
    try {
      if (navigator.share && /Mobi|Android/i.test(navigator.userAgent)) {
        await navigator.share({ title: document.title, url })
        return
      }
      await navigator.clipboard.writeText(url)
    } catch {
      window.prompt('Copy this link:', url)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button className="btn secondary" onClick={share}>
      {copied ? '✓ Link copied' : '🔗 Copy share link'}
    </button>
  )
}

export function Verdict({ profile, pdfUrl }) {
  const { verdict: v, location: loc, site, evidence_coverage: cov } = profile
  const dev = v.development ?? site?.development?.level
  const land = v.land_label ?? site?.land_use?.effective_category
  return (
    <Reveal className="card lr-verdict">
      <div className="lr-verdict__main">
        <Gauge score={v.access_score} label={v.access_rating} />
        <div className="lr-verdict__text">
          <div className="lr-eyebrow">
            {loc.city_label}, {loc.state} · {loc.latitude}, {loc.longitude}
            {loc.in_city_core ? ' · city core' : ' · outside city core'}
          </div>
          <h2 className="lr-verdict__title">{v.title}</h2>
          <p className="lr-verdict__summary">{v.summary}</p>
          <div className="tag-list">
            <ToneBadge label={v.access_rating} />
            {dev && <span className="chip">{dev}</span>}
            {land && <span className="chip">{land}</span>}
            <span className="chip" title={v.confidence_note}>Confidence: {v.confidence}</span>
          </div>
        </div>
      </div>

      {v.facts?.length > 0 && (
        <dl className="lr-facts">
          {v.facts.map((f) => (
            <div key={f.label}><dt>{f.label}</dt><dd>{f.value}</dd></div>
          ))}
        </dl>
      )}

      <div className="lr-tiles">
        <div className="lr-tile">
          <div className="lr-tile__v">{v.access_score ?? '—'}<small>/100</small></div>
          <div className="lr-tile__l">This site's access</div>
        </div>
        <div className="lr-tile">
          <div className="lr-tile__v">{v.city_typical_access_score ?? '—'}<small>/100</small></div>
          <div className="lr-tile__l">Typical {loc.city_label} core spot</div>
        </div>
        <div className="lr-tile">
          <div className="lr-tile__v lr-tile__v--text">{v.best_use || '—'}</div>
          <div className="lr-tile__l">Best indicative fit</div>
        </div>
        <div className="lr-tile">
          <div className="lr-tile__v">{cov.pct}<small>%</small></div>
          <div className="lr-tile__l">Evidence coverage ({cov.known.length} of {cov.known.length + cov.unknown.length})</div>
        </div>
      </div>

      <div className="lr-actions">
        <PdfButton url={pdfUrl} filename={`land-report-${loc.city}-${loc.latitude}-${loc.longitude}.pdf`} />
        <ShareButton />
      </div>
    </Reveal>
  )
}

// --- facility comparison -----------------------------------------------------
export function FacilityChart({ facilities, cityLabel, samplePoints }) {
  const [mode, setMode] = useState('distance')
  const [hover, setHover] = useState(null)

  const vals = facilities.flatMap((f) => [f.distance_m, f.city_typical_m]).filter((v) => v != null)
  const vmax = Math.max(1000, ...vals) * 1.05
  const width = (v) => (mode === 'distance' ? (v / vmax) * 100 : v)
  const siteVal = (f) => (mode === 'distance' ? f.distance_m : f.score)
  const cityVal = (f) => (mode === 'distance' ? f.city_typical_m : f.city_typical_score)
  const fmt = (v) => (v == null ? '—' : mode === 'distance' ? fmtDist(v) : `${v}/100`)

  const ticks = mode === 'distance'
    ? (() => {
        const step = [250, 500, 1000, 2000, 2500, 5000, 10000].find((s) => vmax / s <= 5) || 20000
        const out = []
        for (let t = 0; t <= vmax; t += step) out.push(t)
        return out
      })()
    : [0, 25, 50, 75, 100]

  return (
    <Reveal className="card">
      <div className="card__head">
        <div>
          <h3>How close are the essentials?</h3>
          <span className="faint">
            This site compared with a typical spot in the {cityLabel} city core
            ({samplePoints} sample points). {mode === 'distance' ? 'Shorter bars are better.' : 'Longer bars are better.'}
          </span>
        </div>
        <div className="lr-seg" role="tablist" aria-label="Chart measure">
          <button role="tab" aria-selected={mode === 'distance'} className={mode === 'distance' ? 'on' : ''}
                  onClick={() => setMode('distance')}>Distance</button>
          <button role="tab" aria-selected={mode === 'score'} className={mode === 'score' ? 'on' : ''}
                  onClick={() => setMode('score')}>Score</button>
        </div>
      </div>

      <div className="lr-legend">
        <span><i className="lr-sw lr-sw--site" />This site</span>
        <span><i className="lr-sw lr-sw--city" />Typical {cityLabel} core spot (median)</span>
      </div>

      <div className="lr-bars">
        <div className="lr-grid" aria-hidden>
          {ticks.map((t) => (
            <span key={t} style={{ left: `${width(t)}%` }}>
              <em>{mode === 'distance' ? (t ? fmtDist(t) : '0') : t}</em>
            </span>
          ))}
        </div>
        {facilities.map((f) => {
          const on = hover === f.key
          return (
            <div key={f.key} className={`lr-row${on ? ' on' : ''}`} tabIndex={0}
                 onMouseEnter={() => setHover(f.key)} onMouseLeave={() => setHover(null)}
                 onFocus={() => setHover(f.key)} onBlur={() => setHover(null)}>
              <div className="lr-row__label">
                <strong>{f.label}</strong>
                <ToneBadge label={f.rating} />
              </div>
              <div className="lr-row__plot">
                <div className="lr-bar lr-bar--site" style={{ width: siteVal(f) == null ? 0 : `${Math.max(0.6, width(siteVal(f)))}%` }}>
                  <span className="lr-bar__val">{siteVal(f) == null ? 'not mapped' : fmt(siteVal(f))}</span>
                </div>
                <div className="lr-bar lr-bar--city" style={{ width: cityVal(f) == null ? 0 : `${Math.max(0.6, width(cityVal(f)))}%` }} />
              </div>
              {on && (
                <div className="lr-tip" role="tooltip">
                  <div className="lr-tip__h">{f.label}</div>
                  <div>Nearest: <strong>{f.nearest_name || 'unnamed in OSM'}</strong></div>
                  <div>This site: <strong>{fmtDist(f.distance_m)}</strong> · score {f.score ?? '—'}</div>
                  <div>City core median: {fmtDist(f.city_typical_m)}
                    {f.city_p25_m != null && <> (middle half {fmtDist(f.city_p25_m)}–{fmtDist(f.city_p75_m)})</>}</div>
                  {f.closer_than_pct_of_city != null && (
                    <div className="lr-tip__k">
                      {f.closer_than_pct_of_city === 0
                        ? 'Farther than every sampled city-core spot'
                        : `Closer than ${f.closer_than_pct_of_city}% of city-core spots`}
                    </div>
                  )}
                  <div className="faint">Bands: excellent ≤{fmtDist(f.bands_m.excellent)}, good ≤{fmtDist(f.bands_m.good)}, fair ≤{fmtDist(f.bands_m.fair)}</div>
                  {!f.weight && <div className="faint">Shown for context — not part of the access score.</div>}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <details className="lr-table-toggle">
        <summary>Show as table</summary>
        <table>
          <thead><tr><th>Facility</th><th>Nearest mapped</th><th>Distance</th><th>City median</th><th>Score</th><th>vs city core</th></tr></thead>
          <tbody>
            {facilities.map((f) => (
              <tr key={f.key}>
                <td>{f.label}</td><td>{f.nearest_name || <span className="faint">unnamed</span>}</td>
                <td>{fmtDist(f.distance_m)}</td><td>{fmtDist(f.city_typical_m)}</td>
                <td>{f.score ?? '—'}</td>
                <td>{f.closer_than_pct_of_city == null ? '—' : `closer than ${f.closer_than_pct_of_city}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Reveal>
  )
}

// --- use fit ------------------------------------------------------------------
export function UseFit({ uses, labelFor }) {
  const [open, setOpen] = useState(uses[0]?.key)
  return (
    <Reveal className="card" delay={60}>
      <div className="card__head">
        <div>
          <h3>What could this land be good for?</h3>
          <span className="faint">Indicative fit for common uses, from verified access and site character only.
            Click a use to see why.</span>
        </div>
      </div>
      <div className="lr-uses">
        {uses.map((u, i) => {
          const isOpen = open === u.key
          const tone = TONE[u.fit] || 'none'
          return (
            <div key={u.key} className={`lr-use${isOpen ? ' open' : ''}`}>
              <button className="lr-use__head" aria-expanded={isOpen}
                      onClick={() => setOpen(isOpen ? null : u.key)}>
                <span className="lr-use__rank">{i + 1}</span>
                <span className="lr-use__name">{u.label}</span>
                <span className="lr-use__track">
                  <span className={`lr-use__fill lr-fill--${tone}`} style={{ width: `${u.score ?? 0}%` }} />
                </span>
                <span className="lr-use__score">{u.score ?? '—'}</span>
                <ToneBadge label={u.fit} />
                <span className="lr-use__chev" aria-hidden>{isOpen ? '−' : '+'}</span>
              </button>
              {isOpen && (
                <div className="lr-use__body">
                  <p className="muted">{u.why}</p>
                  <div className="lr-factors">
                    {u.factors.map((f) => (
                      <div key={f.factor} className="lr-factor">
                        <span className="lr-factor__n">{f.factor}<em>weight {f.weight}%</em></span>
                        <span className="lr-factor__t">
                          <span style={{ width: `${f.points ?? 0}%` }} />
                        </span>
                        <span className="lr-factor__v">{f.points ?? 'not scored'}</span>
                      </div>
                    ))}
                  </div>
                  {u.verify_before_deciding.length > 0 && (
                    <div className="lr-verify">
                      <span className="faint">Check before deciding:</span>
                      {u.verify_before_deciding.map((t) => <span key={t} className="chip">{labelFor(t)}</span>)}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <p className="faint" style={{ margin: '12px 0 0' }}>
        A screening aid, not a zoning, valuation or legal determination.
      </p>
    </Reveal>
  )
}

// --- how sure are we --------------------------------------------------------------
const KIND_HELP = {
  Satellite: 'Measured from space (Copernicus / Sentinel-2)',
  Reanalysis: 'Weather-station and satellite observations blended into a consistent record (ERA5)',
  Model: 'A modelled estimate, not a measurement at the site',
  Derived: 'Computed here from other verified evidence',
  'Community-mapped': 'OpenStreetMap — mapped by people on the ground; completeness varies',
}

export function Coverage({ coverage, note }) {
  const statusLabel = (s) => (s || '').replaceAll('_', ' ').toLowerCase()
  return (
    <Reveal className="card lr-covcard" delay={80}>
      <div className="card__head">
        <div>
          <h3>How sure are we?</h3>
          <span className="faint">{note}</span>
        </div>
        <div className="lr-cov">
          <strong>{coverage.pct}%</strong>
          <span>verified</span>
        </div>
      </div>
      <div className="lr-covbar" role="img" aria-label={`${coverage.known.length} verified, ${coverage.unknown.length} open`}>
        {coverage.known.map((k) => <span key={k.topic} className="k" title={k.label} />)}
        {coverage.unknown.map((u) => <span key={u.topic} className="u" title={u.label} />)}
      </div>
      <div className="lr-know">
        <div>
          <h4>✓ Verified from real data</h4>
          {coverage.known.map((k) => (
            <div key={k.topic} className="lr-know__i lr-know__i--k">
              <span>{k.label}</span>
              {k.kind && <span className={`lr-kind lr-kind--${k.kind.toLowerCase().replace(/[^a-z]/g, '')}`}
                               title={KIND_HELP[k.kind]}>{k.kind}</span>}
            </div>
          ))}
        </div>
        <div>
          <h4>… Still open — needed before any decision</h4>
          {coverage.unknown.map((u) => (
            <div key={u.topic} className="lr-know__i lr-know__i--u" title={u.reason}>
              <span>{u.label}</span>
              {u.pending
                ? <span className="badge badge--DOCUMENT_ONLY">fetching…</span>
                : <span className={`badge badge--${u.status}`}>{statusLabel(u.status)}</span>}
            </div>
          ))}
        </div>
      </div>

      {coverage.cross_checks?.length > 0 && (
        <div className="lr-xchk">
          <h4>Cross-checks between independent sources</h4>
          {coverage.cross_checks.map((c) => (
            <div key={c.check} className={`lr-xchk__i lr-xchk__i--${c.result}`}>
              <b>{c.result === 'agree' ? '✓ Agree' : c.result === 'filled' ? '＋ Gap filled' : '⚠ Disagree'}</b>
              <span><strong>{c.check}.</strong> {c.note}</span>
            </div>
          ))}
        </div>
      )}
      <p className="faint lr-raise">
        The remaining gaps are government-held (parcel, ownership, official flood map, zoning,
        groundwater, soil survey) — only official access closes them. <Link to="/app/official-data-access">See how to request them →</Link>
      </p>
    </Reveal>
  )
}
