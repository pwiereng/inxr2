/**
 * Basic API client for communicating with the FastAPI backend
 * This is a minimal implementation for Phase 1.2
 *
 * Designed for dependency injection - can be provided via context or props
 * and easily tested by injecting a mock fetch function
 */

import type { HealthResponse, ApiInfoResponse, HelloResponse } from '@/types/api'

export interface FetchFunction {
  (input: RequestInfo | URL, init?: RequestInit): Promise<Response>
}

export class ApiClient {
  private baseUrl: string
  private fetchFn: FetchFunction

  constructor(baseUrl = '/api', fetchFn: FetchFunction = fetch) {
    this.baseUrl = baseUrl
    this.fetchFn = fetchFn
  }

  /**
   * Generic fetch wrapper with error handling
   * Uses injected fetch function for testability
   */
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = endpoint.startsWith('http') ? endpoint : `${this.baseUrl}${endpoint}`

    try {
      const response = await this.fetchFn(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error('API request failed:', error)
      throw error
    }
  }

  /**
   * Health check endpoint
   */
  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health')
  }

  /**
   * Get API info from root endpoint
   */
  async getInfo(): Promise<ApiInfoResponse> {
    // Root endpoint is at /api not /api/api
    return this.request<ApiInfoResponse>('/')
  }

  /**
   * Hello endpoint for testing
   */
  async hello(name: string): Promise<HelloResponse> {
    return this.request<HelloResponse>(`/hello?name=${encodeURIComponent(name)}`)
  }
}

/**
 * Create a default API client instance
 * This can be overridden by providing a different instance via context
 */
export function createApiClient(baseUrl = '/api', fetchFn?: FetchFunction): ApiClient {
  return new ApiClient(baseUrl, fetchFn)
}
