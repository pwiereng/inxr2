import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@/test/utils'
import { render as rtlRender, renderHook as rtlRenderHook } from '@testing-library/react'
import { AppProvider, useApp } from './AppContext'
import { ApiClient } from '@/lib/api-client'

describe('AppContext', () => {
  beforeEach(() => {
    localStorage.removeItem('themeMode')
  })

  describe('AppProvider', () => {
    it('should provide app context to children', () => {
      const TestComponent = () => {
        const { themeMode } = useApp()
        return <div>Theme: {themeMode}</div>
      }

      // render() from @/test/utils already wraps with AppProvider, so
      // we use the raw RTL render to test AppProvider in isolation.
      rtlRender(
        <AppProvider>
          <TestComponent />
        </AppProvider>
      )

      expect(screen.getByText('Theme: dark')).toBeInTheDocument()
    })

    it('should allow injecting custom API client', () => {
      // Create custom API client with test base URL
      const testApiClient = new ApiClient('http://test.api')

      const TestComponent = () => {
        const { apiClient } = useApp()
        return <div>{apiClient ? 'Has client' : 'No client'}</div>
      }

      rtlRender(
        <AppProvider apiClient={testApiClient}>
          <TestComponent />
        </AppProvider>
      )

      expect(screen.getByText('Has client')).toBeInTheDocument()
    })
  })

  describe('useApp', () => {
    it('should throw error when used outside AppProvider', () => {
      const { result } = rtlRenderHook(() => {
        try {
          return useApp()
        } catch (error) {
          return error as Error
        }
      })

      expect(result.current).toBeInstanceOf(Error)
      expect((result.current as Error).message).toBe('useApp must be used within AppProvider')
    })

    it('should return app context when used inside AppProvider', () => {
      const { result } = rtlRenderHook(() => useApp(), {
        wrapper: ({ children }) => <AppProvider>{children}</AppProvider>,
      })

      expect(result.current).toHaveProperty('apiClient')
      expect(result.current).toHaveProperty('themeMode')
      expect(result.current).toHaveProperty('setThemeMode')
      expect(result.current).toHaveProperty('toggleThemeMode')
    })
  })
})
