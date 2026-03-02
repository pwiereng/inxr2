import { describe, expect, it } from 'vitest'
import { formatDuration } from '@/lib/dateUtils'

describe('formatDuration', () => {
  it('formats seconds under 60 as "Xs"', () => {
    expect(formatDuration(0)).toBe('0s')
    expect(formatDuration(5)).toBe('5s')
    expect(formatDuration(45.3)).toBe('45s')
  })

  it('rounds up to 1m 0s at the 60s boundary', () => {
    expect(formatDuration(59.9)).toBe('1m 0s')
  })

  it('formats 60+ seconds as "Xm Ys"', () => {
    expect(formatDuration(60)).toBe('1m 0s')
    expect(formatDuration(90)).toBe('1m 30s')
    expect(formatDuration(192.4)).toBe('3m 12s')
    expect(formatDuration(3600)).toBe('60m 0s')
  })

  it('does not produce 60s in the seconds component', () => {
    expect(formatDuration(119.9)).toBe('2m 0s')
    expect(formatDuration(179.5)).toBe('3m 0s')
  })
})
