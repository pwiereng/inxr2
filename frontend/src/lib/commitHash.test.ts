import { describe, it, expect } from 'vitest'
import { hashMatches, findByHash, getByHash } from './commitHash'

const FULL = '306df25a1b2c3d4e5f60718293a4b5c6d7e8f901'

describe('hashMatches', () => {
  it('matches the full hash exactly', () => {
    expect(hashMatches(FULL, FULL)).toBe(true)
  })

  it('matches an abbreviated hash by prefix (#555)', () => {
    expect(hashMatches(FULL, '306df25')).toBe(true)
    expect(hashMatches(FULL, '306d')).toBe(true)
  })

  it('matches case-sensitively, like the backend', () => {
    expect(hashMatches(FULL, '306DF25')).toBe(false)
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

describe('findByHash', () => {
  const items = [
    { hash: 'aaaa1111111111111111111111111111111111aa', n: 1 },
    { hash: 'aaaa2222222222222222222222222222222222aa', n: 2 },
    { hash: FULL, n: 3 },
  ]
  const getHash = (i: { hash: string }) => i.hash

  it('finds the item for a unique abbreviated hash', () => {
    expect(findByHash(items, '306df25', getHash)?.n).toBe(3)
  })

  it('finds the item for a full hash', () => {
    expect(findByHash(items, items[1]!.hash, getHash)?.n).toBe(2)
  })

  it('returns undefined for an ambiguous prefix, like the backend', () => {
    expect(findByHash(items, 'aaaa', getHash)).toBeUndefined()
  })

  it('resolves a prefix that is long enough to be unique', () => {
    expect(findByHash(items, 'aaaa2', getHash)?.n).toBe(2)
  })

  it('returns undefined when nothing matches', () => {
    expect(findByHash(items, 'ffff', getHash)).toBeUndefined()
    expect(findByHash(items, null, getHash)).toBeUndefined()
  })
})

describe('getByHash', () => {
  const map = new Map([
    [FULL, '2024-01-01'],
    ['aaaa1111', '2024-02-02'],
    ['aaaa2222', '2024-03-03'],
  ])

  it('returns the exact entry', () => {
    expect(getByHash(map, FULL)).toBe('2024-01-01')
  })

  it('returns the entry for an abbreviated hash', () => {
    expect(getByHash(map, '306df25')).toBe('2024-01-01')
  })

  it('returns undefined for an ambiguous prefix', () => {
    expect(getByHash(map, 'aaaa')).toBeUndefined()
  })

  it('returns undefined when nothing matches', () => {
    expect(getByHash(map, 'ffff')).toBeUndefined()
    expect(getByHash(map, null)).toBeUndefined()
  })
})
