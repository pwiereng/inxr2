// Polyfill ResizeObserver for react-resizable-panels in jsdom
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

import '@testing-library/jest-dom'
import { expect, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers)

afterEach(() => {
  cleanup()
  // Restore real timers between tests. Under React 19 + RTL 16, a test that calls
  // vi.useFakeTimers() but times out before its own vi.useRealTimers() would leave
  // fake timers active and hang every subsequent test's waitFor with a 5s timeout.
  vi.useRealTimers()
  // Prevent theme state from leaking between tests
  localStorage.removeItem('themeMode')
  document.body.classList.remove('prism-dark', 'prism-light')
})
