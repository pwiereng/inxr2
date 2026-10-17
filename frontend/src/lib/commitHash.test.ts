import { describe, it, expect } from 'vitest'
import { hashMatches, getByHash } from './commitHash'

const FULL = '306df25a1b2c3d4e5f60718293a4b5c6d7e8f901'

describe('hashMatches', () => {
  it('matches the full hash exactly', () => {
    expect(hashMatches(FULL, FULL)).toBe(true)
  })

  it('matches an abbreviated hash by prefix (#555)', () => {
    expect(hashMatches(FULL, '306df25')).toBe(true)
    expect(hashMatches(FULL, '306d')).toBe(true)
  })

  it('matches case-insensitively', () => {
    expect(hashMatches(FULL, '306DF25')).toBe(true)
  })

  it('does not match prefixes shorter than git’s 4-character minimum', () => {
    expect(hashMatches(FULL, '306')).toBe(false)
  })

  it('matches a short full value exactly even below the minimum prefix length', () => {
    expect(hashMatches('abc', 'abc')).toBe(true)
  })

  it('does not match a different hash', () => {
    expect(hashMatches(FULL, '306df26')).toBe(false)
  })

  it('does not match empty or missing values', () => {
    expect(hashMatches(FULL, '')).toBe(false)
    expect(hashMatches(FULL, null)).toBe(false)
    expect(hashMatches(FULL, undefined)).toBe(false)
  })
})

describe('getByHash', () => {
  const map = new Map([
    [FULL, '2024-01-01'],
    ['aaaa1111', '2024-02-02'],
  ])

  it('returns the exact entry', () => {
    expect(getByHash(map, FULL)).toBe('2024-01-01')
  })

  it('returns the entry for an abbreviated hash', () => {
    expect(getByHash(map, '306df25')).toBe('2024-01-01')
  })

  it('returns undefined when nothing matches', () => {
    expect(getByHash(map, 'ffff')).toBeUndefined()
    expect(getByHash(map, null)).toBeUndefined()
  })
})
