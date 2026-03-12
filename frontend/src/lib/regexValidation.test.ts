import { describe, it, expect } from 'vitest'
import { validateRegexPattern } from './regexValidation'

describe('validateRegexPattern', () => {
  describe('valid patterns', () => {
    it('accepts a simple pattern', () => {
      expect(validateRegexPattern('foo')).toEqual({ valid: true })
    })

    it('accepts a pattern with quantifiers', () => {
      expect(validateRegexPattern('foo.*bar')).toEqual({ valid: true })
    })

    it('accepts a pattern with character classes', () => {
      expect(validateRegexPattern('[a-z]+')).toEqual({ valid: true })
    })

    it('accepts an empty pattern', () => {
      expect(validateRegexPattern('')).toEqual({ valid: true })
    })
  })

  describe('length limit', () => {
    it('accepts a pattern at the length limit', () => {
      const pattern = 'a'.repeat(500)
      expect(validateRegexPattern(pattern)).toEqual({ valid: true })
    })

    it('rejects a pattern exceeding the length limit', () => {
      const pattern = 'a'.repeat(501)
      const result = validateRegexPattern(pattern)
      expect(result.valid).toBe(false)
      expect(result.error).toContain('too long')
      expect(result.error).toContain('501')
    })
  })

  describe('dangerous patterns (ReDoS)', () => {
    it('rejects (.*)+', () => {
      const result = validateRegexPattern('(.*)+')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('dangerous nested quantifiers')
    })

    it('rejects (.+)+', () => {
      const result = validateRegexPattern('(.+)+')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('dangerous nested quantifiers')
    })

    it('rejects (a+)+', () => {
      const result = validateRegexPattern('(a+)+')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('dangerous nested quantifiers')
    })

    it('rejects (a*)+', () => {
      const result = validateRegexPattern('(a*)+')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('dangerous nested quantifiers')
    })

    it('rejects (a+)*', () => {
      const result = validateRegexPattern('(a+)*')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('dangerous nested quantifiers')
    })

    it('rejects (a*)*', () => {
      const result = validateRegexPattern('(a*)*')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('dangerous nested quantifiers')
    })

    it('rejects dangerous pattern embedded in larger regex', () => {
      const result = validateRegexPattern('foo(a+)+bar')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('dangerous nested quantifiers')
    })
  })

  describe('invalid syntax', () => {
    it('rejects unclosed group', () => {
      const result = validateRegexPattern('(foo')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('Invalid regex pattern')
    })

    it('rejects unclosed character class', () => {
      const result = validateRegexPattern('[abc')
      expect(result.valid).toBe(false)
      expect(result.error).toContain('Invalid regex pattern')
    })
  })
})
