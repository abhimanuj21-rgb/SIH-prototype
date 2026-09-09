import { Link } from 'react-router-dom'
import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'

const PIPELINE = [
  ['Real data', 'Only sources we can actually pull or cite'],
  ['Verified evidence', 'What holds up for a specific location', true],
  ['Analytical features', 'Terrain, climate, access — with provenance'],
  ['Validated models', 'Tested against history first'],
  ['Prediction', 'Only after validation'],
  ['Policy simulation', 'The end goal'],
]

const CHECKS = [
  ['🌡️', 'Climate', 'ERA5 normals — temperature, rainfall, wet days', 'verified'],
  ['💧', 'Water & water bodies', 'Nearest river, tank, canal; counts within 2.5 km', 'verified'],
  ['🌾', 'Land use', 'Agricultural vs built-up, from OSM land-use polygons', 'verified'],
  ['🏗️', 'Development level', 'Urban / peri-urban / rural, from an OSM density proxy', 'verified'],
  ['🛣️', 'Infrastructure access', 'Distance to roads, hospitals, schools, rail', 'verified'],
  ['⛰️', 'Terrain, cadastre, flood, soil', 'Named as explicit gaps until the data is acquired', 'gap'],
]

export default function LandingPage() {
  const { data } = useAsync(() => api.registrySummary(), [])

  return (
    <div className="lp">
      <header className="lp-nav">
        <Link to="/" className="lp-brand"><span className="mark">◧</span> National Digital Platform</Link>
        <nav className="lp-nav__links">
          <Link to="/app/explorer">Explorer</Link>
          <Link to="/app/data-registry">Data Registry</Link>
          <Link to="/app/data-quality">Data Quality</Link>
          <Link to="/app/dashboard" className="btn">Open platform →</Link>
        </nav>
      </header>

      <section className="lp-hero">
        <div className="lp-hero__text">
          <div className="lp-kicker">Evidence-first · Madurai prototype</div>
          <h1>Land intelligence you can defend, one location at a time.</h1>
          <p>
            A national digital platform for land governance and research. It reports
            only what real data can substantiate — climate, water, land use, access,
            development — and names every gap instead of guessing.
          </p>
          <div className="lp-cta">
            <Link to="/app/explorer" className="btn lg">Explore the map</Link>
            <Link to="/app/intelligence" className="btn secondary lg">See a sample report</Link>
          </div>
          <div className="lp-trust">Real sources only · Provenance on every value · Not for statutory use</div>
        </div>

        <div className="lp-hero__card">
          <div className="lp-mini">
            <div className="lp-mini__head">Evidence report · 9.9252, 78.1198</div>
            <div className="lp-mini__row"><span className="chip water">💧 Vaigai ~483 m</span><span className="chip">Potramarai Kulam ~680 m</span></div>
            <div className="lp-mini__row"><span className="chip built">🏗️ Urban / built-up</span><span className="chip">28.7 °C · 1178 mm/yr</span></div>
            <div className="lp-mini__row"><span className="chip">🛣️ road ~3 m · hospital ~91 m</span></div>
            <div className="lp-mini__gap">Gaps: terrain · cadastre · flood hazard · soil · zoning</div>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="section-title">The pipeline — and where this build is</div>
        <div className="lp-pipeline">
          {PIPELINE.map(([step, desc, here], i) => (
            <div key={step} className={`lp-step${here ? ' here' : ''}`}>
              <div className="lp-step__n">{i + 1}</div>
              <div className="lp-step__name">{step}{here && <span className="lp-here">you are here</span>}</div>
              <div className="lp-step__desc">{desc}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-stats">
          <div><b>{data?.total ?? '26'}</b><span>datasets registered</span></div>
          <div><b>{data?.analytically_usable_count ?? '—'}</b><span>usable for analysis now</span></div>
          <div><b>{data?.by_status?.OFFICIAL_ACCESS_REQUIRED ?? '—'}</b><span>need government access</span></div>
          <div><b>{data?.by_status?.DATA_UNAVAILABLE ?? '—'}</b><span>open, acquisition pending</span></div>
        </div>
      </section>

      <section className="lp-section">
        <div className="section-title">What you can check for any point in Madurai</div>
        <div className="lp-checks">
          {CHECKS.map(([ic, title, desc, tag]) => (
            <div className="lp-check" key={title}>
              <div className="lp-check__ic">{ic}</div>
              <div>
                <div className="lp-check__t">{title} <span className={`badge badge--${tag === 'verified' ? 'AVAILABLE' : 'DATA_UNAVAILABLE'}`}>{tag}</span></div>
                <div className="lp-check__d">{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section">
        <div className="section-title">Data governance is the product</div>
        <div className="lp-gov">
          <Link to="/app/data-registry" className="lp-gov__card">
            <h3>Data Registry</h3>
            <p>Every dataset with source, authority, licence, limitations and a single analytical gate.</p>
          </Link>
          <Link to="/app/data-quality" className="lp-gov__card">
            <h3>Quality audit</h3>
            <p>Automated checks — provenance completeness, status sanity, and proof no demo data reaches analysis.</p>
          </Link>
          <Link to="/app/official-data-access" className="lp-gov__card">
            <h3>Official access</h3>
            <p>Restricted layers (cadastre, ownership, flood, soil) with the authority and the request path.</p>
          </Link>
        </div>
      </section>

      <footer className="lp-footer">
        <div>
          <strong>National Digital Platform</strong> — evidence-first prototype, Madurai.
          Descriptive only. Not for legal, valuation or statutory use.
        </div>
        <div className="faint">
          React + Vite + Leaflet · FastAPI · OpenStreetMap / Overpass · Open-Meteo (ERA5) ·
          Esri imagery · boundary © OpenStreetMap contributors
        </div>
      </footer>
    </div>
  )
}
