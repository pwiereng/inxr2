import '@testing-library/jest-dom'
import { expect, afterEach, beforeAll, afterAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers)

// Suppress React act() warnings from async hooks
// These are expected when testing hooks with async effects
const originalError = console.error
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    const message = args[0]
    if (
      typeof message === 'string' &&
      message.includes('not wrapped in act')
    ) {
      return // Suppress act() warnings
    }
    originalError.apply(console, args)
  }
})

afterAll(() => {
  console.error = originalError
})

// Cleanup after each test
afterEach(() => {
  cleanup()
})
