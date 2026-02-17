import React from 'react'

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

  return parts.map((part, i) =>
    pattern.test(part) ? (
      <mark key={i} style={{ backgroundColor: '#fff176', borderRadius: 2, padding: '0 1px' }}>
        {part}
      </mark>
    ) : (
      part
    )
  )
}
