import { useCallback, useEffect, useRef, useState } from 'react'

// Minimal async-state hook. Returns { data, error, loading, run }.
// `run` re-invokes the function (useful for buttons / retries).
export default function useAsync(fn, deps = [], { immediate = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: immediate })
  const mounted = useRef(true)
  useEffect(() => {
    // Restore on (re)mount — StrictMode double-invokes effects, and without
    // this the simulated unmount would leave mounted.current false forever.
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  const run = useCallback((...args) => {
    setState((s) => ({ ...s, loading: true, error: null }))
    return Promise.resolve()
      .then(() => fn(...args))
      .then((data) => { if (mounted.current) setState({ data, error: null, loading: false }) })
      .catch((error) => { if (mounted.current) setState({ data: null, error, loading: false }) })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    if (immediate) run()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { ...state, run }
}
