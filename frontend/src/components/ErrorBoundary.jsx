import React from 'react'

// Catches render-time crashes so a broken page shows a message instead of a
// blank screen.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Render error:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, fontFamily: 'system-ui', color: '#e6ecf5', background: '#0b1220', minHeight: '100vh' }}>
          <h1>Something broke while rendering</h1>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#fca5a5', background: '#131c2e', padding: 16, borderRadius: 8 }}>
            {String(this.state.error?.stack || this.state.error)}
          </pre>
          <button onClick={() => this.setState({ error: null })}>Try again</button>
        </div>
      )
    }
    return this.props.children
  }
}
