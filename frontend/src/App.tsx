import { useState, useEffect } from 'react'
import './App.css'

interface ApiResponse {
  message: string
  from?: string
  version?: string
  docs?: string
}

function App() {
  const [message, setMessage] = useState<string>('Loading...')
  const [backendStatus, setBackendStatus] = useState<string>('checking...')
  const [name, setName] = useState<string>('')
  const [greeting, setGreeting] = useState<string>('')

  // Check backend health on mount
  useEffect(() => {
    fetch('http://localhost:8000/api/health')
      .then(res => res.json())
      .then((data: ApiResponse) => {
        setBackendStatus(data.message || 'connected')
      })
      .catch(() => {
        setBackendStatus('disconnected')
      })

    // Get root message
    fetch('http://localhost:8000/')
      .then(res => res.json())
      .then((data: ApiResponse) => {
        setMessage(data.message)
      })
      .catch(() => {
        setMessage('Could not connect to backend')
      })
  }, [])

  const handleGreeting = async () => {
    if (!name.trim()) return

    try {
      const res = await fetch(`http://localhost:8000/api/hello?name=${encodeURIComponent(name)}`)
      const data: ApiResponse = await res.json()
      setGreeting(data.message)
    } catch {
      setGreeting('Error calling API')
    }
  }

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 INXR2</h1>
        <p className="subtitle">Cross-Reference Code Browser</p>
      </header>

      <main className="App-main">
        <div className="status-card">
          <h2>Backend Status</h2>
          <p className={`status ${backendStatus === 'checking...' ? 'checking' : backendStatus === 'connected' || backendStatus === 'healthy' ? 'connected' : 'disconnected'}`}>
            {backendStatus}
          </p>
        </div>

        <div className="message-card">
          <h2>API Message</h2>
          <p>{message}</p>
        </div>

        <div className="interactive-card">
          <h2>Try the API</h2>
          <div className="input-group">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter your name"
              onKeyPress={(e) => e.key === 'Enter' && handleGreeting()}
            />
            <button onClick={handleGreeting}>Say Hello</button>
          </div>
          {greeting && <p className="greeting">{greeting}</p>}
        </div>

        <div className="info-card">
          <h3>✅ Stack Verified</h3>
          <ul>
            <li>React + TypeScript + Vite (Frontend)</li>
            <li>FastAPI + Python (Backend)</li>
            <li>PostgreSQL (Database)</li>
            <li>Docker Dev Containers</li>
          </ul>
        </div>
      </main>

      <footer className="App-footer">
        <p>INXR2 v0.1.0 - Development Environment</p>
      </footer>
    </div>
  )
}

export default App
