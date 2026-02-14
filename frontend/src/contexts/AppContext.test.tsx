import { describe, it, expect } from 'vitest'
import { render, screen, renderHook } from '@/test/utils'
import { AppProvider, useApp } from './AppContext'
import { ApiClient } from '@/lib/api-client'

describe('AppContext', () => {
  describe('AppProvider', () => {
    it('should provide app context to children', () => {
      const TestComponent = () => {
        const { themeMode } = useApp()
        return <div>Theme: {themeMode}</div>
      }

      render(
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

      render(
        <AppProvider apiClient={testApiClient}>
          <TestComponent />
        </AppProvider>
      )

      expect(screen.getByText('Has client')).toBeInTheDocument()
    })
  })

  describe('useApp', () => {
    it('should throw error when used outside AppProvider', () => {
      const { result } = renderHook(() => {
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
      const { result } = renderHook(() => useApp(), {
        wrapper: ({ children }) => <AppProvider>{children}</AppProvider>,
      })

      expect(result.current).toHaveProperty('apiClient')
      expect(result.current).toHaveProperty('themeMode')
      expect(result.current).toHaveProperty('setThemeMode')
    })
  })
})
