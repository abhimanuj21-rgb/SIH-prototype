import useAsync from '../hooks/useAsync.js'
import api from '../services/api.js'
import { Loading, ErrorBox } from '../components/Bits.jsx'

export default function HistoryPage() {
  const hist = useAsync(() => api.lulcHistory(), [])
  const change = useAsync(() => api.lulcChange(), [])

  return (
    <div className="page">
      <h1>History</h1>
      <p className="page__lead">
        Historical land-cover and change detection for Madurai. These layers
        depend on the Esri / Sentinel-2 classified rasters, which are open data
        but have not yet been acquired to local storage.
      </p>

      <div className="card">
        <h3>Land-cover history (2017)</h3>
        {hist.loading && <Loading what="history layer" />}
        <ErrorBox error={hist.error} />
        {hist.data && !hist.data.available && (
          <>
            <p className="badge badge--DATA_UNAVAILABLE">{hist.data.status?.replaceAll('_', ' ')}</p>
            <p>{hist.data.reason}</p>
            <p className="muted"><em>Acquisition:</em> {hist.data.acquisition}</p>
          </>
        )}
      </div>

      <div className="card">
        <h3>Change detection (2017 → 2024)</h3>
        {change.loading && <Loading what="change layer" />}
        <ErrorBox error={change.error} />
        {change.data && !change.data.available && (
          <>
            <p className="badge badge--DATA_UNAVAILABLE">{change.data.status?.replaceAll('_', ' ')}</p>
            <p>{change.data.reason}</p>
            <p className="muted"><em>Acquisition:</em> {change.data.acquisition}</p>
          </>
        )}
      </div>

      <div className="card">
        <h3>What will appear here</h3>
        <p className="muted">
          Once both Esri epochs are stored: 2017 and 2024 classified layers, a
          transition matrix (Crops→Built, etc.), and per-class area change — all
          with provenance. No change figures are shown until the source rasters
          exist.
        </p>
      </div>
    </div>
  )
}
