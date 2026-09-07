// Thin API client. Base URL is same-origin '/api' (Vite proxies to :8000 in
// dev). Every call has a timeout and returns parsed JSON or throws an Error
// with a useful message — no silent failures, no fabricated fallbacks.

const BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const DEFAULT_TIMEOUT = 30000

async function request(path, { method = 'GET', body, timeout = DEFAULT_TIMEOUT } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)
  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    })
    const text = await res.text()
    const data = text ? JSON.parse(text) : null
    if (!res.ok) {
      const detail = data?.detail || data?.error || res.statusText
      throw new Error(`${res.status} ${detail}`)
    }
    return data
  } catch (err) {
    if (err.name === 'AbortError') throw new Error(`Request timed out: ${path}`)
    if (err.message === 'Failed to fetch')
      throw new Error('Cannot reach the API. Is the backend running on :8000?')
    throw err
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  health: () => request('/health'),

  // data registry
  registry: (params = '') => request(`/data-registry/${params}`),
  registrySummary: () => request('/data-registry/summary'),
  dataset: (id) => request(`/data-registry/${id}`),

  // data quality
  qualityAudit: () => request('/data-quality/audit'),

  // evidence
  evidenceLocation: (latitude, longitude) =>
    request('/evidence/location', { method: 'POST', body: { latitude, longitude } }),
  evidenceReport: (latitude, longitude) =>
    request('/evidence/report', { method: 'POST', body: { latitude, longitude } }),
  exportUrl: (kind, latitude, longitude) =>
    `${BASE}/evidence/export/${kind}?latitude=${latitude}&longitude=${longitude}`,
  manifestUrl: () => `${BASE}/evidence/export/manifest`,

  // analytics
  features: (latitude, longitude) =>
    request('/analytics/features', { method: 'POST', body: { latitude, longitude } }),
  suitability: (latitude, longitude, type) =>
    request('/analytics/suitability', { method: 'POST', body: { latitude, longitude, type } }),

  // gis
  boundary: () => request('/gis/madurai/boundary'),
  infrastructure: () => request('/gis/madurai/infrastructure/osm', { timeout: 180000 }),
  terrain: () => request('/gis/madurai/terrain'),
  lulc: () => request('/gis/madurai/lulc'),
  lulcHistory: () => request('/gis/madurai/lulc/history'),
  lulcChange: () => request('/gis/madurai/lulc/change'),
  demoGrid: () => request('/gis/madurai/demo-cadastral-grid'),
}

export default api
