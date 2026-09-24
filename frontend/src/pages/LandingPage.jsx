import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'
import Reveal from '../components/Reveal.jsx'
import useTilt from '../hooks/useTilt.js'

const PIPELINE = [
  ['Real data', 'Only sources we can actually pull or cite'],
  ['Verified evidence', 'What holds up for a specific location', true],
  ['Analytical features', 'Terrain, climate, access — with provenance'],
  ['Validated models', 'Tested against history first'],
  ['Prediction', 'Only after validation'],
  ['Policy simulation', 'The end goal'],
]

const CHECKS = [
  ['🛣️', 'Access & comparison', 'Distance to roads, hospitals, schools, rail — vs the rest of the city', 'verified'],
  ['🌦️', 'Live weather', 'Current conditions and 7-day forecast, checked against the nearest airport station', 'verified'],
  ['💨', 'Live air (Indian AQI)', 'Six pollutants, CPCB AQI method, past and next 24 hours', 'verified'],
  ['🌡️', 'Climate normals', '10 years of ERA5 — monthly rain, heat, sunshine', 'verified'],
  ['⛰️', 'Terrain', 'Elevation, slope, low-spot check and cross-sections (Copernicus DEM)', 'verified'],
  ['🟫', 'Soil (modelled)', 'Texture, pH, organic carbon from ISRIC SoilGrids', 'verified'],
  ['💧', 'Water & land use', 'Nearest river / tank, farmland vs built-up, development level', 'verified'],
  ['🏪', 'Everyday amenities', 'Banks, shops, bus stops, pharmacies within 500 m / 1 km', 'verified'],
  ['📄', 'Cadastre, ownership, flood, zoning', 'Named as explicit gaps until official data is obtained', 'gap'],
]

export default function LandingPage() {
  const { data } = useAsync(() => api.registrySummary(), [])
  const heroBgRef = useRef(null)
  const miniRef = useTilt(6)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let raf = null
    const onScroll = () => {
      if (raf) return
      raf = requestAnimationFrame(() => {
        raf = null
        const offset = Math.min(window.scrollY * 0.12, 40)
        if (heroBgRef.current) heroBgRef.current.style.transform = `translateY(${offset}px)`
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

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
        <div className="lp-hero__bg" ref={heroBgRef} />
        <div className="lp-hero__fade" />
        <div className="lp-hero__text">
          <div className="lp-kicker">Evidence-first · Madurai, Bhopal &amp; Kovilpatti prototypes</div>
          <h1><em>Land intelligence</em><br />you can defend, one location at a time.</h1>
          <p>
            A national digital platform for land governance and research. It reports
            only what real data can substantiate — access, live weather and air, terrain,
            soil, water, land use — and names every gap instead of guessing.
          </p>
          <div className="lp-cta">
            <Link to="/app/explorer" className="btn lg">Explore the map</Link>
            <Link to="/app/intelligence" className="btn secondary lg">See a sample report</Link>
          </div>
          <div className="lp-trust">Real sources only · Provenance on every value · Not for statutory use</div>
        </div>

        <div className="lp-hero__card">
          <div className="lp-mini" ref={miniRef}>
            <div className="lp-mini__head">Evidence report · 9.9252, 78.1198</div>
            <div className="lp-mini__row"><span className="chip water">💧 Vaigai ~483 m</span><span className="chip">Potramarai Kulam ~680 m</span></div>
            <div className="lp-mini__row"><span className="chip built">🏗️ Urban / built-up</span><span className="chip">28.7 °C · 1186 mm/yr</span></div>
            <div className="lp-mini__row"><span className="chip">🛣️ road ~24 m · hospital ~91 m</span></div>
            <div className="lp-mini__gap">Gaps: cadastre · ownership · flood hazard · zoning</div>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <Reveal className="section-title">The pipeline — and where this build is</Reveal>
        <div className="lp-pipeline">
          {PIPELINE.map(([step, desc, here], i) => (
            <Reveal as="div" key={step} delay={i * 70} className={`lp-step${here ? ' here' : ''}`}>
              <div className="lp-step__n">{i + 1}</div>
              <div className="lp-step__name">{step}{here && <span className="lp-here">you are here</span>}</div>
              <div className="lp-step__desc">{desc}</div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-stats">
          {[
            [data?.total ?? '—', 'datasets registered'],
            [data?.analytically_usable_count ?? '—', 'usable for analysis now'],
            [data?.by_status?.OFFICIAL_ACCESS_REQUIRED ?? '—', 'need government access'],
            [data?.by_status?.DATA_UNAVAILABLE ?? '—', 'open, acquisition pending'],
          ].map(([n, label], i) => (
            <Reveal as="div" key={label} delay={i * 70}>
              <b>{n}</b><span>{label}</span>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="lp-section">
        <Reveal className="section-title">What you can check for any point in Madurai, Bhopal or Kovilpatti</Reveal>
        <div className="lp-checks">
          {CHECKS.map(([ic, title, desc, tag], i) => (
            <Reveal as="div" key={title} delay={i * 60} className="lp-check">
              <div className="lp-check__ic">{ic}</div>
              <div>
                <div className="lp-check__t">{title} <span className={`badge badge--${tag === 'verified' ? 'AVAILABLE' : 'DATA_UNAVAILABLE'}`}>{tag}</span></div>
                <div className="lp-check__d">{desc}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="lp-section">
        <Reveal className="section-title">Data governance is the product</Reveal>
        <div className="lp-gov">
          <Reveal as={Link} to="/app/data-registry" delay={0} tilt={7} className="lp-gov__card">
            <h3>Data Registry</h3>
            <p>Every dataset with source, authority, licence, limitations and a single analytical gate.</p>
          </Reveal>
          <Reveal as={Link} to="/app/data-quality" delay={90} tilt={7} className="lp-gov__card">
            <h3>Quality audit</h3>
            <p>Automated checks — provenance completeness, status sanity, and proof no demo data reaches analysis.</p>
          </Reveal>
          <Reveal as={Link} to="/app/official-data-access" delay={180} tilt={7} className="lp-gov__card">
            <h3>Official access</h3>
            <p>Restricted layers (cadastre, ownership, flood, soil) with the authority and the request path.</p>
          </Reveal>
        </div>
      </section>

      <Reveal as="footer" className="lp-footer">
        <div>
          <strong>National Digital Platform</strong> — evidence-first prototype, Madurai, Bhopal &amp; Kovilpatti.
          Descriptive only. Not for legal, valuation or statutory use.
        </div>
        <div className="faint">
          React + Vite + Leaflet · FastAPI · OpenStreetMap / Overpass / Nominatim · Open-Meteo (ERA5,
          forecast, Copernicus DEM, CAMS air) · ISRIC SoilGrids · NOAA Aviation Weather Center ·
          Esri imagery · map data © OpenStreetMap contributors
        </div>
      </Reveal>
    </div>
  )
}
