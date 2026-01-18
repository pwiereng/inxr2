import { describe, it, expect, vi } from 'vitest'
import { ApiClient, type FetchFunction } from './api-client'
import type { HealthResponse, HelloResponse } from '@/types/api'

describe('ApiClient', () => {
  describe('health', () => {
    it('should call the health endpoint and return response', async () => {
      // Create a mock fetch function (dependency injection, not mocking)
      const mockFetch: FetchFunction = async () => {
        return new Response(JSON.stringify({ message: 'healthy', version: '0.1.0' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      // Inject the mock fetch into ApiClient
      const client = new ApiClient('/api', mockFetch)
      const result = await client.health()

      expect(result).toEqual<HealthResponse>({
        message: 'healthy',
        version: '0.1.0',
      })
    })

    it('should throw error when request fails', async () => {
      // Suppress expected console.error during this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      // Inject a fetch that returns an error
      const mockFetch: FetchFunction = async () => {
        return new Response('Not Found', { status: 404 })
      }

      const client = new ApiClient('/api', mockFetch)

      await expect(client.health()).rejects.toThrow('HTTP error! status: 404')
      expect(consoleSpy).toHaveBeenCalledWith('API request failed:', expect.any(Error))

      consoleSpy.mockRestore()
    })
  })

  describe('hello', () => {
    it('should call hello endpoint with encoded name', async () => {
      const mockFetch: FetchFunction = async (input) => {
        const url = input.toString()
        expect(url).toContain('/hello?name=')
        expect(url).toContain(encodeURIComponent('Test User'))

        return new Response(JSON.stringify({ message: 'Hello, Test User!', from: 'INXR2' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      const client = new ApiClient('/api', mockFetch)
      const result = await client.hello('Test User')

      expect(result).toEqual<HelloResponse>({
        message: 'Hello, Test User!',
        from: 'INXR2',
      })
    })
  })

  describe('constructor', () => {
    it('should use default baseUrl when not provided', () => {
      const client = new ApiClient()
      expect(client).toBeInstanceOf(ApiClient)
    })

    it('should use custom baseUrl when provided', () => {
      const client = new ApiClient('http://localhost:8080/api')
      expect(client).toBeInstanceOf(ApiClient)
    })
  })
})
