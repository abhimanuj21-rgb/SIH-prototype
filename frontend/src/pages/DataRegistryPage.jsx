import { useMemo, useState } from 'react'
import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'
import { Loading, ErrorBox, StatusBadge } from '../components/Bits.jsx'
import Reveal from '../components/Reveal.jsx'

const STATUSES = [
  'AVAILABLE', 'OFFICIAL_ACCESS_REQUIRED', 'DATA_UNAVAILABLE',
  'DOCUMENT_ONLY', 'DEMO_ONLY',
]

export default function DataRegistryPage() {
  const { data, error, loading } = useAsync(() => api.registry(), [])
  const [filter, setFilter] = useState('ALL')
  const [selected, setSelected] = useState(null)

  const rows = useMemo(() => {
    const all = data?.datasets || []
    return filter === 'ALL' ? all : all.filter((d) => d.status === filter)
  }, [data, filter])

  return (
    <div className="page">
      <h1>Data Registry</h1>
      <p className="page__lead">
        Every dataset the platform knows about, with provenance and a single
        analytical gate: a dataset is usable for analysis only when its status is
        <code> AVAILABLE </code> and it is flagged analytically eligible.
      </p>

      {loading && <Loading what="registry" />}
      <ErrorBox error={error} />

      {data && (
        <>
          <div className="row" style={{ marginBottom: 12 }}>
            <button className={filter === 'ALL' ? '' : 'secondary'} onClick={() => setFilter('ALL')}>
              All ({data.datasets.length})
            </button>
            {STATUSES.map((s) => {
              const n = data.datasets.filter((d) => d.status === s).length
              return (
                <button key={s} className={filter === s ? '' : 'secondary'} onClick={() => setFilter(s)}>
                  {s.replaceAll('_', ' ')} ({n})
                </button>
              )
            })}
          </div>

          <Reveal className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table>
              <thead>
                <tr>
                  <th>Dataset</th><th>Category</th><th>Status</th>
                  <th>Analytical</th><th>Authority</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id} onClick={() => setSelected(d)} style={{ cursor: 'pointer' }}>
                    <td><strong>{d.name}</strong><br /><code>{d.id}</code></td>
                    <td>{d.category}</td>
                    <td><StatusBadge status={d.status} /></td>
                    <td>{d.analytical_eligible ? '✅ eligible' : '—'}</td>
                    <td>{d.authority}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Reveal>

          {selected && (
            <Reveal className="card">
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <h3 style={{ margin: 0 }}>{selected.name}</h3>
                <button className="secondary" onClick={() => setSelected(null)}>close</button>
              </div>
              <p><StatusBadge status={selected.status} />{' '}
                {selected.analytical_eligible
                  ? <span className="badge badge--AVAILABLE">analytically eligible</span>
                  : <span className="badge badge--DEMO_ONLY">not analytically eligible</span>}
              </p>
              <table>
                <tbody>
                  {['id', 'category', 'source', 'authority', 'license',
                    'acquisition_date', 'last_updated', 'limitations', 'acquisition',
                  ].map((k) => (
                    <tr key={k}><td style={{ width: 160 }}>{k.replaceAll('_', ' ')}</td>
                      <td>{selected[k] || <span className="muted">—</span>}</td></tr>
                  ))}
                </tbody>
              </table>
            </Reveal>
          )}
        </>
      )}
    </div>
  )
}
