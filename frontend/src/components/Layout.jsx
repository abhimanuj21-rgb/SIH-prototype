import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import api from '../services/api.js'

const NAV = [
  { group: 'Explore', items: [
    ['/', 'Dashboard', '▚', true],
    ['/explorer', 'Explorer', '🗺'],
    ['/intelligence', 'Land Intelligence', '◎'],
  ]},
  { group: 'Context', items: [
    ['/history', 'History', '↺'],
    ['/climate', 'Climate', '☁'],
  ]},
  { group: 'Data governance', items: [
    ['/data-registry', 'Data Registry', '▤'],
    ['/data-quality', 'Data Quality', '✓'],
    ['/official-data-access', 'Official Data Access', '⚿'],
  ]},
]

const TITLES = {
  '/': 'Dashboard', '/explorer': 'Explorer', '/intelligence': 'Land Intelligence',
  '/history': 'History', '/climate': 'Climate', '/data-registry': 'Data Registry',
  '/data-quality': 'Data Quality', '/official-data-access': 'Official Data Access',
}

export default function Layout() {
  const [health, setHealth] = useState('unknown')
  const { pathname } = useLocation()

  useEffect(() => {
    let alive = true
    api.health().then(() => alive && setHealth('ok')).catch(() => alive && setHealth('bad'))
    return () => { alive = false }
  }, [])

  return (
    <div className="app">
      <aside className="app__sidebar">
        <div className="app__brand">
          <span className="mark">◧</span>
          <span>
            National Digital Platform
            <small>Land governance &amp; research · Madurai prototype</small>
          </span>
        </div>
        <nav className="nav">
          {NAV.map((sec) => (
            <div key={sec.group}>
              <div className="nav__group">{sec.group}</div>
              {sec.items.map(([to, label, ic, end]) => (
                <NavLink key={to} to={to} end={end}>
                  <span className="ic">{ic}</span>{label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <header className="app__header">
        <div className="crumb">
          {TITLES[pathname] || 'Land Intelligence'} <span>· evidence-first · descriptive only</span>
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
