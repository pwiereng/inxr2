import { Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { AppProvider, useApp } from '@/contexts/AppContext'
import { darkTheme, lightTheme } from '@/theme'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Home } from '@/components/Home'
import { NotFound } from '@/components/NotFound'
import Repositories from '@/pages/Repositories'
import Files from '@/pages/Files'
import Browse from '@/pages/Browse'
import Search from '@/pages/Search'
import History from '@/pages/History'

/**
 * App content with routing
 * Separated from App to allow access to AppContext
 */
function AppContent() {
  const { themeMode } = useApp()

  const theme = themeMode === 'dark' ? darkTheme : lightTheme

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ErrorBoundary>
        <Routes>
          <Route
            path="/"
            element={
              <ErrorBoundary>
                <Home />
              </ErrorBoundary>
            }
          />
          <Route
            path="/repositories"
            element={
              <ErrorBoundary>
                <Repositories />
              </ErrorBoundary>
            }
          />
          <Route
            path="/repositories/:repositoryId/files"
            element={
              <ErrorBoundary>
                <Files />
              </ErrorBoundary>
            }
          />
          {/* Main code navigation routes */}
          <Route
            path="/browse/:repoName/*"
            element={
              <ErrorBoundary>
                <Browse />
              </ErrorBoundary>
            }
          />
          <Route
            path="/search"
            element={
              <ErrorBoundary>
                <Search />
              </ErrorBoundary>
            }
          />
          <Route
            path="/history"
            element={
              <ErrorBoundary>
                <History />
              </ErrorBoundary>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </ErrorBoundary>
    </ThemeProvider>
  )
}

/**
 * Main App component
 * Provides app-wide context and routing
 */
function App(): React.ReactElement {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  )
}

export default App
