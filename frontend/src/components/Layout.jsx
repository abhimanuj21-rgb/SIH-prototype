import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import api from '../services/api.js'

const NAV = [
  ['/', 'Dashboard', true],
  ['/explorer', 'Explorer'],
  ['/intelligence', 'Land Intelligence'],
  ['/history', 'History'],
  ['/climate', 'Climate'],
  ['/data-registry', 'Data Registry'],
  ['/data-quality', 'Data Quality'],
  ['/official-data-access', 'Official Data Access'],
]

export default function Layout() {
  const [health, setHealth] = useState('unknown')

  useEffect(() => {
    let alive = true
    api.health()
      .then(() => alive && setHealth('ok'))
      .catch(() => alive && setHealth('bad'))
    return () => { alive = false }
  }, [])

  return (
    <div className="app">
      <aside className="app__sidebar">
        <div className="app__brand">
          National Digital Platform
          <small>Land governance & research — Madurai prototype</small>
        </div>
        <nav className="nav">
          {NAV.map(([to, label, end]) => (
            <NavLink key={to} to={to} end={end}>{label}</NavLink>
          ))}
        </nav>
      </aside>

      <header className="app__header">
        <div className="muted">Evidence-first · Descriptive only · No fabricated data</div>
        <div className="row">
          <span>
            <span className={`status-dot ${health}`} />
            API {health === 'ok' ? 'connected' : health === 'bad' ? 'unreachable' : '…'}
          </span>
        </div>
      </header>

      <main className="app__main">
        <Outlet />
      </main>
    </div>
  )
}
