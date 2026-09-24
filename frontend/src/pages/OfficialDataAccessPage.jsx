import { useMemo } from 'react'
import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'
import { Loading, ErrorBox, StatusBadge } from '../components/Bits.jsx'
import Reveal from '../components/Reveal.jsx'

export default function OfficialDataAccessPage() {
  const { data, error, loading } = useAsync(() => api.registry(), [])

  const groups = useMemo(() => {
    const all = data?.datasets || []
    return {
      OFFICIAL_ACCESS_REQUIRED: all.filter((d) => d.status === 'OFFICIAL_ACCESS_REQUIRED'),
      DOCUMENT_ONLY: all.filter((d) => d.status === 'DOCUMENT_ONLY'),
      DATA_UNAVAILABLE: all.filter((d) => d.status === 'DATA_UNAVAILABLE'),
    }
  }, [data])

  return (
    <div className="page">
      <h1>Official Data Access</h1>
      <p className="page__lead">
        The acquisition workflow. These datasets exist but are not in the
        platform — either restricted (need a government MoU / registered access),
        published only as documents, or open data still pending acquisition.
        Nothing here is used for analysis until it is genuinely obtained.
      </p>

      {loading && <Loading what="registry" />}
      <ErrorBox error={error} />

      {data && Object.entries(groups).map(([status, items], i) => (
        <Reveal className="card" key={status} delay={i * 90}>
          <h3><StatusBadge status={status} /> &nbsp; {items.length} dataset(s)</h3>
          <table>
            <thead><tr><th>Dataset</th><th>Authority</th><th>How to obtain</th></tr></thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td><strong>{d.name}</strong><br /><code>{d.id}</code></td>
                  <td>{d.authority}</td>
                  <td>{d.acquisition || <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Reveal>
      ))}

      <Reveal className="card" delay={270}>
        <h3>Principle</h3>
        <p className="muted">
          Restricted and document-only sources are never approximated with demo
          or synthetic values. Each remains an explicit gap in every evidence
          report until acquired through the proper channel and registered with
          full provenance.
        </p>
      </Reveal>
    </div>
  )
}
