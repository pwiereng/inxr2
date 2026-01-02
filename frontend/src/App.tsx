import { Routes, Route } from 'react-router-dom'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { AppProvider, useApp } from '@/contexts/AppContext'
import { Home } from '@/components/Home'
import { NotFound } from '@/components/NotFound'

/**
 * App content with routing
 * Separated from App to allow access to AppContext
 */
function AppContent() {
  const { themeMode } = useApp()

  const theme = createTheme({
    palette: {
      mode: themeMode,
    },
  })

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ThemeProvider>
  )
}

/**
 * Main App component
 * Provides app-wide context and routing
 */
function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  )
}

export default App
