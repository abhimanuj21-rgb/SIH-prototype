import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import api from '../services/api.js'

const NAV = [
  { group: 'Explore', items: [
    ['/app/dashboard', 'Dashboard', '▚'],
    ['/app/explorer', 'Explorer', '🗺'],
    ['/app/intelligence', 'Land Intelligence', '◎'],
  ]},
  { group: 'Context', items: [
    ['/app/history', 'History', '↺'],
    ['/app/climate', 'Climate', '☁'],
  ]},
  { group: 'Data governance', items: [
    ['/app/data-registry', 'Data Registry', '▤'],
    ['/app/data-quality', 'Data Quality', '✓'],
    ['/app/official-data-access', 'Official Data Access', '⚿'],
  ]},
]

const TITLES = {
  dashboard: 'Dashboard', explorer: 'Explorer', intelligence: 'Land Intelligence',
  history: 'History', climate: 'Climate', 'data-registry': 'Data Registry',
  'data-quality': 'Data Quality', 'official-data-access': 'Official Data Access',
}

export default function Layout() {
  const [health, setHealth] = useState('unknown')
  const { pathname } = useLocation()
  const slug = pathname.split('/').pop()

  useEffect(() => {
    let alive = true
    api.health().then(() => alive && setHealth('ok')).catch(() => alive && setHealth('bad'))
    return () => { alive = false }
  }, [])

  return (
    <div className="app">
      <aside className="app__sidebar">
        <Link to="/" className="app__brand">
          <span className="mark">◧</span>
          <span>
            National Digital Platform
            <small>Land governance &amp; research · Madurai, Bhopal &amp; Kovilpatti prototypes</small>
          </span>
        </Link>
        <nav className="nav">
          {NAV.map((sec) => (
            <div key={sec.group}>
              <div className="nav__group">{sec.group}</div>
              {sec.items.map(([to, label, ic]) => (
                <NavLink key={to} to={to}>
                  <span className="ic">{ic}</span>{label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <header className="app__header">
        <div className="crumb">
          {TITLES[slug] || 'Land Intelligence'} <span>· evidence-first · descriptive only</span>
        </div>
        <span className="pill">
          <span className={`status-dot ${health}`} />
          API {health === 'ok' ? 'connected' : health === 'bad' ? 'unreachable' : '…'}
        </span>
      </header>

      <main className="app__main">
        <Outlet />
      </main>
    </div>
  )
}
