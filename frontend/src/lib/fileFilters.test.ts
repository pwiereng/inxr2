import { describe, it, expect } from 'vitest'
import { getLanguageColor, getUniqueLanguages, filterFiles } from './fileFilters'
import type { FileInfo } from './api'

function makeFile(overrides: Partial<FileInfo> = {}): FileInfo {
  return {
    id: 1,
    repository_id: 1,
    commit_id: 1,
    path: 'src/main.py',
    language: 'python',
    size_bytes: 100,
    line_count: 10,
    ...overrides,
  }
}

describe('getLanguageColor', () => {
  it('returns default for null language', () => {
    expect(getLanguageColor(null)).toBe('default')
  })

  it('returns default for empty string', () => {
    expect(getLanguageColor('')).toBe('default')
  })

  it('maps known languages to their colors', () => {
    expect(getLanguageColor('python')).toBe('primary')
    expect(getLanguageColor('javascript')).toBe('secondary')
    expect(getLanguageColor('typescript')).toBe('primary')
    expect(getLanguageColor('java')).toBe('secondary')
    expect(getLanguageColor('go')).toBe('primary')
    expect(getLanguageColor('rust')).toBe('secondary')
  })

  it('is case-insensitive', () => {
    expect(getLanguageColor('Python')).toBe('primary')
    expect(getLanguageColor('JAVASCRIPT')).toBe('secondary')
  })

  it('returns default for unknown languages', () => {
    expect(getLanguageColor('cobol')).toBe('default')
    expect(getLanguageColor('haskell')).toBe('default')
  })
})

describe('getUniqueLanguages', () => {
  it('returns empty array for no files', () => {
    expect(getUniqueLanguages([])).toEqual([])
  })

  it('returns distinct languages sorted alphabetically', () => {
    const files = [
      makeFile({ language: 'python' }),
      makeFile({ language: 'go' }),
      makeFile({ language: 'python' }),
      makeFile({ language: 'rust' }),
    ]
    expect(getUniqueLanguages(files)).toEqual(['go', 'python', 'rust'])
  })

  it('excludes null and empty languages', () => {
    const files = [
      makeFile({ language: 'python' }),
      makeFile({ language: null }),
      makeFile({ language: '' }),
      makeFile({ language: 'go' }),
    ]
    expect(getUniqueLanguages(files)).toEqual(['go', 'python'])
  })

  it('returns empty array when all languages are null', () => {
    const files = [makeFile({ language: null }), makeFile({ language: null })]
    expect(getUniqueLanguages(files)).toEqual([])
  })
})

describe('filterFiles', () => {
  const files = [
    makeFile({ id: 1, path: 'src/main.py', language: 'python' }),
    makeFile({ id: 2, path: 'src/utils.ts', language: 'typescript' }),
    makeFile({ id: 3, path: 'README.md', language: 'markdown' }),
    makeFile({ id: 4, path: 'src/Main.GO', language: 'go' }),
  ]

  it('returns all files when no filters applied', () => {
    expect(filterFiles(files, '', '')).toHaveLength(4)
  })

  it('filters by path substring case-insensitively', () => {
    const result = filterFiles(files, 'main', '')
    expect(result.map((f) => f.id)).toEqual([1, 4])
  })

  it('filters by exact language match', () => {
    const result = filterFiles(files, '', 'typescript')
    expect(result.map((f) => f.id)).toEqual([2])
  })

  it('combines search term and language filter', () => {
    const result = filterFiles(files, 'src', 'python')
    expect(result.map((f) => f.id)).toEqual([1])
  })

  it('returns empty array when nothing matches', () => {
    expect(filterFiles(files, 'nonexistent', '')).toEqual([])
  })

  it('returns empty array when language has no matches', () => {
    expect(filterFiles(files, '', 'rust')).toEqual([])
  })

  it('matches uppercase paths against lowercase search', () => {
    const result = filterFiles(files, 'MAIN', '')
    expect(result.map((f) => f.id)).toEqual([1, 4])
  })
})
