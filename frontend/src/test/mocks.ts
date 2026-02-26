/**
 * Mock data helpers for testing
 */

/**
 * Mock API response for health check
 */
export const mockHealthResponse = {
  message: 'healthy',
  version: '0.1.0',
}

/**
 * Mock API response for root endpoint
 */
export const mockRootResponse = {
  message: 'INXR2 API',
  version: '0.1.0',
  docs: '/docs',
}

/**
 * Mock API response for hello endpoint
 */
export const mockHelloResponse = (name: string): { message: string; from: string } => ({
  message: `Hello, ${name}!`,
  from: 'INXR2',
})
