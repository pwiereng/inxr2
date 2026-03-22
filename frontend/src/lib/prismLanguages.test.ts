import { describe, it, expect } from 'vitest'
import { getPrismLanguage } from './prismLanguages'

describe('getPrismLanguage', () => {
  it('returns the mapped Prism grammar for known languages', () => {
    expect(getPrismLanguage('python')).toBe('python')
    expect(getPrismLanguage('typescript')).toBe('typescript')
    expect(getPrismLanguage('dockerfile')).toBe('docker')
    expect(getPrismLanguage('toml')).toBe('toml')
    expect(getPrismLanguage('swift')).toBe('swift')
  })

  it('is case-insensitive', () => {
    expect(getPrismLanguage('Python')).toBe('python')
    expect(getPrismLanguage('TYPESCRIPT')).toBe('typescript')
    expect(getPrismLanguage('Dockerfile')).toBe('docker')
    expect(getPrismLanguage('TOML')).toBe('toml')
  })

  it('returns text for unknown languages', () => {
    expect(getPrismLanguage('fortran')).toBe('text')
    expect(getPrismLanguage('cobol')).toBe('text')
    expect(getPrismLanguage('unknown')).toBe('text')
  })

  it('returns text for null', () => {
    expect(getPrismLanguage(null)).toBe('text')
  })

  it('returns text for empty string', () => {
    expect(getPrismLanguage('')).toBe('text')
  })
})
