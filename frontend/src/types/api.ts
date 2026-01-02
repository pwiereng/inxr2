/**
 * API type definitions
 * These are minimal types for Phase 1.2, will be expanded in Phase 5
 */

/**
 * Standard API response wrapper
 */
export interface ApiResponse<T = unknown> {
  data?: T
  error?: string
  message?: string
}

/**
 * Health check response
 */
export interface HealthResponse {
  message: string
  version?: string
}

/**
 * Root API info response
 */
export interface ApiInfoResponse {
  message: string
  version?: string
  docs?: string
}

/**
 * Hello endpoint response
 */
export interface HelloResponse {
  message: string
  from?: string
}
