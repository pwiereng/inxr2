import React from 'react'
import { validateRegexPattern } from './regexValidation'

/**
 * Sanitize a ts_headline snippet from PostgreSQL for safe rendering via dangerouslySetInnerHTML.
 *
 * PostgreSQL ts_headline returns plain text with <mark>...</mark> tags around matched terms.
 * This function:
 * 1. Replaces <mark>/<\/mark> with placeholders
 * 2. Escapes all remaining HTML (< and >) to prevent XSS
 * 3. Restores <mark> tags with inline styling matching the existing highlight style
 */
export function sanitizeHeadline(headline: string): string {
  const MARK_OPEN = '{{MARK_OPEN}}'
  const MARK_CLOSE = '{{MARK_CLOSE}}'

  // Step 1: Replace <mark> and </mark> with unique placeholders
  let result = headline.replace(/<mark>/g, MARK_OPEN).replace(/<\/mark>/g, MARK_CLOSE)

  // Step 2: Escape all remaining HTML characters
  result = result.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // Step 3: Restore <mark> tags with inline styling
  result = result
    .split(MARK_OPEN)
    .join('<mark style="background-color:#fff176;border-radius:2px;padding:0 1px">')
    .split(MARK_CLOSE)
    .join('</mark>')

  return result
}

/**
 * Highlight matching text in a string by wrapping matches in <mark> elements.
 * For keyword mode, highlights each query word independently.
 * For phrase/regex mode, highlights the full pattern.
 */
export function highlightMatches(
  text: string,
  searchQuery: string,
  searchMode: string
): React.ReactNode {
  if (!searchQuery.trim() || !text) return text

  let pattern: RegExp
  try {
    if (searchMode === 'regex') {
      const validation = validateRegexPattern(searchQuery)
      if (!validation.valid) return text
      pattern = new RegExp(`(${searchQuery})`, 'gi')
    } else if (searchMode === 'phrase') {
      const escaped = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      pattern = new RegExp(`(${escaped})`, 'gi')
    } else {
      // Keyword: highlight each word
      const words = searchQuery
        .split(/\s+/)
        .filter(Boolean)
        .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      if (words.length === 0) return text
      pattern = new RegExp(`(${words.join('|')})`, 'gi')
    }
  } catch {
    return text
  }

  const parts = text.split(pattern)
  if (parts.length === 1) return text

  // After split with a capturing group, odd indices are the matched parts.
  // Skip empty strings that occur at split boundaries.
  const elements: React.ReactNode[] = []
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i]
    if (part === '') continue
    if (i % 2 === 1) {
      elements.push(
        <mark key={i} style={{ backgroundColor: '#fff176', borderRadius: 2, padding: '0 1px' }}>
          {part}
        </mark>
      )
    } else {
      elements.push(part)
    }
  }
  return elements
}
