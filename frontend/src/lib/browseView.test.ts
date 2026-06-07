import { describe, it, expect } from 'vitest'
import { getShortHash, getVersionDisplay, getTabNavTarget } from './browseView'

describe('getShortHash', () => {
  it('truncates a full 40-char hash to 7 characters', () => {
    expect(getShortHash('abcdef1234567890abcdef1234567890abcdef12')).toBe('abcdef1')
  })

  it('returns a short hash unchanged when already <= 7 chars', () => {
    expect(getShortHash('abc')).toBe('abc')
    expect(getShortHash('abcdef1')).toBe('abcdef1')
  })

  it("returns 'latest' for null/undefined/empty", () => {
    expect(getShortHash(null)).toBe('latest')
    expect(getShortHash(undefined)).toBe('latest')
    expect(getShortHash('')).toBe('latest')
  })
})

describe('getVersionDisplay', () => {
  it('truncates a hash to 7 characters', () => {
    expect(getVersionDisplay('1234567890abcdef')).toBe('1234567')
  })

  it("returns '...' placeholder for null/undefined/empty", () => {
    expect(getVersionDisplay(null)).toBe('...')
    expect(getVersionDisplay(undefined)).toBe('...')
    expect(getVersionDisplay('')).toBe('...')
  })
})

describe('getTabNavTarget', () => {
  const ctx = { repoName: 'myrepo', selectedBranch: 'main', selectedCommit: 'deadbeef' }

  it('returns null for the browse tab (already on browse)', () => {
    expect(getTabNavTarget('browse', ctx)).toBeNull()
  })

  it('threads repo/branch/commit into each destination tab', () => {
    const cases: Array<[Parameters<typeof getTabNavTarget>[0], string]> = [
      ['search', '/search'],
      ['history', '/history'],
      ['logical-view', '/logical-view'],
      ['dependencies', '/dependencies'],
      ['help', '/help'],
    ]
    for (const [tab, path] of cases) {
      const target = getTabNavTarget(tab, ctx)
      expect(target).not.toBeNull()
      expect(target).toContain(path)
      expect(target).toContain('repo=myrepo')
      expect(target).toContain('branch=main')
      expect(target).toContain('commit=deadbeef')
    }
  })

  it('omits params that are absent', () => {
    expect(getTabNavTarget('search', {})).toBe('/search?')
    expect(getTabNavTarget('history', { repoName: 'r' })).toBe('/history?repo=r')
  })

  it('omits branch/commit when only repo is set', () => {
    const target = getTabNavTarget('dependencies', { repoName: 'r' })
    expect(target).toBe('/dependencies?repo=r')
  })

  it('treats null fields the same as missing', () => {
    expect(
      getTabNavTarget('help', { repoName: null, selectedBranch: null, selectedCommit: null })
    ).toBe('/help?')
  })
})
