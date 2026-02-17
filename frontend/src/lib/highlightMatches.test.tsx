import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { highlightMatches } from './highlightMatches'

/** Render the result to a container and return its innerHTML for assertion. */
function renderToHTML(node: React.ReactNode): string {
  const { container } = render(<span>{node}</span>)
  return container.querySelector('span')!.innerHTML
}

describe('highlightMatches', () => {
  describe('keyword mode', () => {
    it('highlights a single matching word', () => {
      const html = renderToHTML(highlightMatches('TODO refactor this code', 'TODO', 'keyword'))
      expect(html).toContain('<mark')
      expect(html).toContain('TODO')
      expect(html).toContain('refactor this code')
    })

    it('highlights multiple query words independently', () => {
      const html = renderToHTML(
        highlightMatches('Initialize the rich console for output', 'rich console', 'keyword')
      )
      expect(html).toMatch(/<mark[^>]*>rich<\/mark>/)
      expect(html).toMatch(/<mark[^>]*>console<\/mark>/)
    })

    it('is case-insensitive', () => {
      const html = renderToHTML(highlightMatches('Hello World', 'hello', 'keyword'))
      expect(html).toMatch(/<mark[^>]*>Hello<\/mark>/)
    })

    it('returns plain text when no match', () => {
      const result = highlightMatches('no match here', 'xyz', 'keyword')
      expect(result).toBe('no match here')
    })

    it('returns plain text for empty query', () => {
      const result = highlightMatches('some text', '', 'keyword')
      expect(result).toBe('some text')
    })

    it('returns plain text for whitespace-only query', () => {
      const result = highlightMatches('some text', '   ', 'keyword')
      expect(result).toBe('some text')
    })

    it('returns plain text when input text is empty', () => {
      const result = highlightMatches('', 'query', 'keyword')
      expect(result).toBe('')
    })
  })

  describe('phrase mode', () => {
    it('highlights the exact phrase', () => {
      const html = renderToHTML(
        highlightMatches('call the rich console now', 'rich console', 'phrase')
      )
      expect(html).toMatch(/<mark[^>]*>rich console<\/mark>/)
    })

    it('does not highlight individual words from the phrase', () => {
      const result = highlightMatches('rich but no console', 'rich console', 'phrase')
      // No match found — should return plain string
      expect(result).toBe('rich but no console')
    })

    it('escapes special regex characters in phrase', () => {
      const html = renderToHTML(highlightMatches('TODO: fix this (now)', 'TODO:', 'phrase'))
      expect(html).toMatch(/<mark[^>]*>TODO:<\/mark>/)
    })
  })

  describe('regex mode', () => {
    it('highlights regex pattern matches', () => {
      const html = renderToHTML(highlightMatches('TODO: fix bug', '^TODO:', 'regex'))
      expect(html).toMatch(/<mark[^>]*>TODO:<\/mark>/)
    })

    it('returns plain text for invalid regex', () => {
      const result = highlightMatches('some text', '[invalid(', 'regex')
      expect(result).toBe('some text')
    })

    it('highlights all occurrences', () => {
      const html = renderToHTML(highlightMatches('foo bar foo baz foo', 'foo', 'regex'))
      const markCount = (html.match(/<mark/g) || []).length
      expect(markCount).toBe(3)
    })
  })
})
