import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0', // Listen on all interfaces for Docker
    port: 5173,
    strictPort: true,
    allowedHosts: true, // Allow all hosts (dev containers, worktree containers, etc.)
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // Cap worker concurrency to half the cores. The default (one worker per
    // CPU) oversubscribes the CPU when each jsdom + v8-coverage worker pegs a
    // core — under the full-suite run (`run-all-tests.sh`, backend first) this
    // pushed total CPU demand to ~1900% on a 10-core VM, stretching individual
    // test wall-clock past the 5s default and causing intermittent
    // "Test timed out" failures (e.g. LogicalView load-more). Leaving cores
    // free is both reliable and faster (less thread thrashing). '50%' already
    // floors at one worker internally (Math.max(1, …)), so no minimum is set.
    // See #487.
    maxWorkers: '50%',
    // Headroom over the 5s default so legitimate scheduling latency under load
    // never trips the timeout. This is headroom, not a retry — assertions and
    // behaviour are unchanged.
    testTimeout: 15000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
      ],
    },
  },
})
