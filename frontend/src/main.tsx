import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ROUTER_FUTURE_FLAGS } from './lib/routerFuture'
import './index.css'
import './prism-themes.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter future={ROUTER_FUTURE_FLAGS}>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
