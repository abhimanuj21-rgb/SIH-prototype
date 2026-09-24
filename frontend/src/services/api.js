// Thin API client. Base URL is same-origin '/api' (Vite proxies to :8000 in
// dev). Every call has a timeout and returns parsed JSON or throws an Error
// with a useful message — no silent failures, no fabricated fallbacks.

const BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const DEFAULT_TIMEOUT = 60000 // free hosting can take ~a minute to wake up
const API_MISSING = 'This website is not connected to its data server. If this is a Netlify ' +
  'deploy, set VITE_API_BASE (e.g. https://<your-render-service>.onrender.com/api/v1) under ' +
  'Site configuration → Environment variables, then redeploy.'

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
    // A web page instead of JSON means this site has no API behind /api —
    // e.g. a static host (Netlify) built without VITE_API_BASE.
    if (/^\s*</.test(text)) throw new Error(API_MISSING)
    const data = text ? JSON.parse(text) : null
    if (!res.ok) {
      const detail = data?.detail || data?.error || res.statusText
      throw new Error(`${res.status} ${detail}`)
    }
    return data
  } catch (err) {
    if (err.name === 'AbortError')
      throw new Error(`The server took too long to answer (${path}). If it was asleep it is waking up — try again in a minute.`)
    if (err.message === 'Failed to fetch')
      throw new Error(import.meta.env.VITE_API_BASE
        ? `Cannot reach the API at ${BASE}. It may be waking up (free hosting sleeps when idle) — try again in a minute.`
        : 'Cannot reach the API. Is the backend running on :8000?')
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
  registryByCity: (city) => request(`/data-registry/?city=${city}`),

  // data quality
  qualityAudit: () => request('/data-quality/audit'),

  // evidence
  evidenceLocation: (latitude, longitude) =>
    request('/evidence/location', { method: 'POST', body: { latitude, longitude } }),
  evidenceReport: (latitude, longitude) =>
    request('/evidence/report', { method: 'POST', body: { latitude, longitude } }),
  siteContext: (latitude, longitude) =>
    request('/evidence/site-context', { method: 'POST', body: { latitude, longitude }, timeout: 150000 }),
  landProfile: (latitude, longitude) =>
    request('/evidence/land-profile', { method: 'POST', body: { latitude, longitude }, timeout: 60000 }),
  liveWeather: (latitude, longitude) =>
    request(`/evidence/live-weather?latitude=${latitude}&longitude=${longitude}`, { timeout: 45000 }),
  liveAir: (latitude, longitude) =>
    request(`/evidence/live-air?latitude=${latitude}&longitude=${longitude}`, { timeout: 45000 }),
  exportUrl: (kind, latitude, longitude) =>
    `${BASE}/evidence/export/${kind}?latitude=${latitude}&longitude=${longitude}`,
  manifestUrl: () => `${BASE}/evidence/export/manifest`,

  // analytics
  features: (latitude, longitude) =>
    request('/analytics/features', { method: 'POST', body: { latitude, longitude } }),
  suitability: (latitude, longitude, type) =>
    request('/analytics/suitability', { method: 'POST', body: { latitude, longitude, type } }),

  // gis — every layer is scoped to a prototype city (default: madurai)
  cities: () => request('/gis/cities'),
  boundary: (city = 'madurai') => request(`/gis/${city}/boundary`),
  infrastructure: (city = 'madurai') => request(`/gis/${city}/infrastructure/osm`, { timeout: 180000 }),
  hydrology: (city = 'madurai') => request(`/gis/${city}/hydrology/osm`, { timeout: 180000 }),
  landuse: (city = 'madurai') => request(`/gis/${city}/landuse/osm`, { timeout: 200000 }),
  terrain: (city = 'madurai') => request(`/gis/${city}/terrain`),
  lulc: (city = 'madurai') => request(`/gis/${city}/lulc`),
  lulcHistory: (city = 'madurai') => request(`/gis/${city}/lulc/history`),
  lulcChange: (city = 'madurai') => request(`/gis/${city}/lulc/change`),
  demoGrid: (city = 'madurai', parcels = 60, seed = 1) =>
    request(`/gis/${city}/demo-cadastral-grid?parcels=${parcels}&seed=${seed}`),
}

export default api
