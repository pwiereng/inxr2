import { describe, it, expect } from 'vitest'
import { getPrismLanguage, languageMap } from './prismLanguages'

describe('prismLanguages', () => {
  describe('languageMap', () => {
    it('maps common backend language names to Prism grammars', () => {
      expect(languageMap['python']).toBe('python')
      expect(languageMap['typescript']).toBe('typescript')
      expect(languageMap['javascript']).toBe('javascript')
      expect(languageMap['json']).toBe('json')
      expect(languageMap['yaml']).toBe('yaml')
      expect(languageMap['css']).toBe('css')
    })

    it('maps newly added languages', () => {
      expect(languageMap['go']).toBe('go')
      expect(languageMap['rust']).toBe('rust')
      expect(languageMap['ruby']).toBe('ruby')
      expect(languageMap['php']).toBe('php')
      expect(languageMap['toml']).toBe('toml')
      expect(languageMap['ini']).toBe('ini')
      expect(languageMap['dockerfile']).toBe('docker')
      expect(languageMap['makefile']).toBe('makefile')
      expect(languageMap['kotlin']).toBe('kotlin')
      expect(languageMap['scala']).toBe('scala')
      expect(languageMap['swift']).toBe('swift')
      expect(languageMap['cpp']).toBe('cpp')
    })

    it('maps markup-based languages to markup grammar', () => {
      expect(languageMap['html']).toBe('markup')
      expect(languageMap['xml']).toBe('markup')
      expect(languageMap['svg']).toBe('markup')
    })

    it('maps aliases correctly', () => {
      expect(languageMap['yml']).toBe('yaml')
      expect(languageMap['sh']).toBe('bash')
      expect(languageMap['shell']).toBe('bash')
      expect(languageMap['cs']).toBe('csharp')
      expect(languageMap['md']).toBe('markdown')
    })
  })

  describe('getPrismLanguage', () => {
    it('returns the mapped Prism grammar for known languages', () => {
      expect(getPrismLanguage('python')).toBe('python')
      expect(getPrismLanguage('typescript')).toBe('typescript')
      expect(getPrismLanguage('dockerfile')).toBe('docker')
      expect(getPrismLanguage('toml')).toBe('toml')
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
})
