import { ReactElement } from 'react'
import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { AppProvider, useApp } from '@/contexts/AppContext'
import { ROUTER_FUTURE_FLAGS } from '@/lib/routerFuture'
import { darkTheme, lightTheme } from '@/theme'

interface AllProvidersProps {
  children: React.ReactNode
}

/**
 * Inner wrapper that selects the MUI theme based on AppContext themeMode,
 * mirroring the same pattern used in App.tsx (AppProvider > useApp > ThemeProvider).
 */
function ThemeWrapper({ children }: { children: React.ReactNode }) {
  const { themeMode } = useApp()
  const theme = themeMode === 'dark' ? darkTheme : lightTheme

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  )
}

/**
 * Wrapper component that provides all necessary providers for testing
 */
function AllProviders({ children }: AllProvidersProps) {
  return (
    <BrowserRouter future={ROUTER_FUTURE_FLAGS}>
      <AppProvider>
        <ThemeWrapper>{children}</ThemeWrapper>
      </AppProvider>
    </BrowserRouter>
  )
}

/**
 * Custom render function that wraps components with all necessary providers
 */
function customRender(ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>): RenderResult {
  return render(ui, { wrapper: AllProviders, ...options })
}

// Re-export everything from @testing-library/react
export * from '@testing-library/react'

// Override the default render with our custom one
export { customRender as render }
