import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'
import { Loading, ErrorBox, Stat } from '../components/Bits.jsx'

export default function DataQualityPage() {
  const { data, error, loading } = useAsync(() => api.qualityAudit(), [])

  return (
    <div className="page">
      <h1>Data Quality</h1>
      <p className="page__lead">
        Automated audit of the data registry: provenance completeness, status
        sanity, and — most importantly — a check that no demo data can pass the
        analytical gate.
      </p>

      {loading && <Loading what="audit" />}
      <ErrorBox error={error} />

      {data && (
        <>
          <div className="grid-2">
            <Stat value={`${data.passed}/${data.total}`} label="Checks passed" />
            <Stat value={data.failed} label="Checks failed" />
            <Stat value={data.demo_data_leak ? 'YES ⚠️' : 'No'} label="Demo data leak" />
            <Stat value={data.provenance_complete_all ? 'Complete' : 'Incomplete'} label="Provenance" />
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table>
              <thead>
                <tr><th>Dataset</th><th>Status</th><th>Provenance</th><th>Gate</th><th>Result</th></tr>
              </thead>
              <tbody>
                {data.checks.map((c) => (
                  <tr key={c.dataset}>
                    <td><code>{c.dataset}</code></td>
                    <td>{c.status.replaceAll('_', ' ')}</td>
                    <td>{c.provenance_complete ? '✅' : '⚠️ incomplete'}</td>
                    <td>{c.analytical_gate ? 'open' : 'closed'}</td>
                    <td>
                      {c.pass ? <span className="badge badge--AVAILABLE">pass</span>
                        : <span className="badge badge--OFFICIAL_ACCESS_REQUIRED">{c.issues.join('; ')}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
