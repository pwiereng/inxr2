import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { ApiClient, createApiClient } from '@/lib/api-client'

/**
 * Theme mode type
 */
export type ThemeMode = 'light' | 'dark'

/**
 * App-wide state and services
 */
interface AppContextValue {
  // Services (injected dependencies)
  apiClient: ApiClient

  // State
  themeMode: ThemeMode
  setThemeMode: (mode: ThemeMode) => void
  toggleThemeMode: () => void
}

/**
 * Read initial theme from localStorage, falling back to system preference, then 'dark'
 */
function getInitialThemeMode(): ThemeMode {
  const stored = localStorage.getItem('themeMode')
  if (stored === 'light' || stored === 'dark') return stored

  if (window.matchMedia?.('(prefers-color-scheme: light)').matches) return 'light'

  return 'dark'
}

/**
 * App Context for dependency injection and app-wide state
 */
const AppContext = createContext<AppContextValue | undefined>(undefined)

/**
 * Props for AppProvider
 */
interface AppProviderProps {
  children: ReactNode
  // Allow injecting custom API client for testing
  apiClient?: ApiClient
}

/**
 * App Provider component
 * Provides app-wide services and state via context (dependency injection)
 */
export function AppProvider({ children, apiClient }: AppProviderProps) {
  const [themeMode, setThemeMode] = useState<ThemeMode>(getInitialThemeMode)

  // Persist to localStorage and sync body class for Prism CSS
  useEffect(() => {
    localStorage.setItem('themeMode', themeMode)
    document.body.className = themeMode === 'dark' ? 'prism-dark' : 'prism-light'
  }, [themeMode])

  const toggleThemeMode = () => {
    setThemeMode((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  // Use injected API client or create default one
  const client = apiClient ?? createApiClient()

  const value: AppContextValue = {
    apiClient: client,
    themeMode,
    setThemeMode,
    toggleThemeMode,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

/**
 * Hook to access app context
 * Throws error if used outside AppProvider
 */
export function useApp(): AppContextValue {
  const context = useContext(AppContext)

  if (context === undefined) {
    throw new Error('useApp must be used within AppProvider')
  }

  return context
}
