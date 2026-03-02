import { describe, expect, it } from 'vitest'
import { formatDuration } from '@/lib/dateUtils'

describe('formatDuration', () => {
  it('formats seconds under 60 as "Xs"', () => {
    expect(formatDuration(0)).toBe('0s')
    expect(formatDuration(5)).toBe('5s')
    expect(formatDuration(45.3)).toBe('45s')
    expect(formatDuration(59.9)).toBe('60s')
  })

  it('formats 60+ seconds as "Xm Ys"', () => {
    expect(formatDuration(60)).toBe('1m 0s')
    expect(formatDuration(90)).toBe('1m 30s')
    expect(formatDuration(192.4)).toBe('3m 12s')
    expect(formatDuration(3600)).toBe('60m 0s')
  })
})
