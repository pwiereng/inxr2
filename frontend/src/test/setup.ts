// Polyfill ResizeObserver for react-resizable-panels in jsdom
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

import '@testing-library/jest-dom'
import { expect, afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers)

afterEach(() => {
  cleanup()
  // Prevent theme state from leaking between tests
  localStorage.removeItem('themeMode')
  document.body.classList.remove('prism-dark', 'prism-light')
})
