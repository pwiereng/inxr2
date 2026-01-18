import { useEffect, useRef } from 'react'
import { Box, Typography, Tooltip } from '@mui/material'
import Prism from 'prismjs'
import 'prismjs/themes/prism-tomorrow.css'
// Import common languages
import 'prismjs/components/prism-python'
import 'prismjs/components/prism-typescript'
import 'prismjs/components/prism-javascript'
import 'prismjs/components/prism-jsx'
import 'prismjs/components/prism-tsx'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-yaml'
import 'prismjs/components/prism-bash'
import 'prismjs/components/prism-markdown'
import 'prismjs/components/prism-css'
import 'prismjs/components/prism-sql'

import type { FileSymbol, FileReference } from '@/lib/api'

interface CodeViewerProps {
  content: string
  language: string | null
  symbols?: FileSymbol[]
  references?: FileReference[]
  highlightLine?: number
  highlightRange?: [number, number]
  onSymbolClick?: (symbol: FileSymbol) => void
  onReferenceClick?: (reference: FileReference) => void
  onLineClick?: (line: number) => void
}

// Map our language names to Prism language names
const languageMap: Record<string, string> = {
  python: 'python',
  typescript: 'typescript',
  javascript: 'javascript',
  tsx: 'tsx',
  jsx: 'jsx',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  bash: 'bash',
  sh: 'bash',
  markdown: 'markdown',
  md: 'markdown',
  css: 'css',
  sql: 'sql',
}

// Represents a clickable segment in a line
interface ClickableSegment {
  start: number
  end: number
  type: 'symbol' | 'reference'
  symbol?: FileSymbol
  reference?: FileReference
}

export function CodeViewer({
  content,
  language,
  symbols = [],
  references = [],
  highlightLine,
  highlightRange,
  onSymbolClick,
  onReferenceClick,
  onLineClick,
}: CodeViewerProps) {
  const codeRef = useRef<HTMLElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Map language to Prism language
  const prismLanguage = language ? languageMap[language.toLowerCase()] || 'text' : 'text'

  // Highlight code on mount and when content/language changes
  useEffect(() => {
    if (codeRef.current) {
      Prism.highlightElement(codeRef.current)
    }
  }, [content, prismLanguage])

  // Scroll to highlighted line when it changes
  useEffect(() => {
    if (highlightLine && containerRef.current) {
      const lineElement = containerRef.current.querySelector(`[data-line="${highlightLine}"]`)
      if (lineElement) {
        lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }, [highlightLine, content])

  // Split content into lines
  const lines = content.split('\n')

  // Check if a line is highlighted
  const isLineHighlighted = (lineNum: number): boolean => {
    if (highlightLine && lineNum === highlightLine) return true
    if (highlightRange && lineNum >= highlightRange[0] && lineNum <= highlightRange[1]) return true
    return false
  }

  // Get symbols that START on this line (definitions)
  const getSymbolDefinitionsOnLine = (lineNum: number): FileSymbol[] => {
    return symbols
      .filter((s) => s.start_line === lineNum)
      .sort((a, b) => a.start_column - b.start_column)
  }

  // Get references on this line (only those with resolved target_symbol_id)
  const getReferencesOnLine = (lineNum: number): FileReference[] => {
    return references
      .filter((r) => r.source_line === lineNum && r.target_symbol_id !== null)
      .sort((a, b) => a.source_column - b.source_column)
  }

  // Check if a substring at [start, end) is a complete word (not part of a larger identifier)
  // A word match requires:
  // 1. Character before start is non-word (or start is at beginning)
  // 2. Character at end is non-word (or end is at string end)
  const isWholeWordMatch = (text: string, start: number, end: number): boolean => {
    const charBefore = start > 0 ? (text[start - 1] ?? '') : ''
    const charAfter = end < text.length ? (text[end] ?? '') : ''
    const boundaryBefore = start === 0 || !/\w/.test(charBefore)
    const boundaryAfter = end >= text.length || !/\w/.test(charAfter)
    return boundaryBefore && boundaryAfter
  }

  // Build clickable segments for a line
  const getClickableSegments = (lineNum: number, lineText: string): ClickableSegment[] => {
    const segments: ClickableSegment[] = []

    // Add symbol definitions
    for (const sym of getSymbolDefinitionsOnLine(lineNum)) {
      // Find the symbol name in the line, starting search from symbol's start_column
      // (start_column might point to keyword like 'class' or 'def', not the name itself)
      // We need to find a whole-word match to avoid matching substrings
      let searchStart = sym.start_column
      let nameIndex = -1

      // Search for the symbol name, ensuring it's a whole word match
      while (searchStart < lineText.length) {
        const idx = lineText.indexOf(sym.name, searchStart)
        if (idx === -1) break

        // Check if this is a whole word match (not part of a larger identifier)
        if (isWholeWordMatch(lineText, idx, idx + sym.name.length)) {
          nameIndex = idx
          break
        }
        // Continue searching after this partial match
        searchStart = idx + 1
      }

      if (nameIndex !== -1) {
        segments.push({
          start: nameIndex,
          end: nameIndex + sym.name.length,
          type: 'symbol',
          symbol: sym,
        })
      }
    }

    // Add references
    for (const ref of getReferencesOnLine(lineNum)) {
      const startCol = ref.source_column
      const refEnd = startCol + ref.reference_text.length
      // Verify the reference text is at the expected position
      if (lineText.substring(startCol, refEnd) === ref.reference_text) {
        // Check if this overlaps with an existing segment (symbol definition takes priority)
        // Use standard interval overlap: two intervals [a,b) and [c,d) overlap iff a < d && b > c
        const overlaps = segments.some((seg) => startCol < seg.end && refEnd > seg.start)
        if (!overlaps) {
          segments.push({
            start: startCol,
            end: refEnd,
            type: 'reference',
            reference: ref,
          })
        }
      }
    }

    // Sort by start position
    segments.sort((a, b) => a.start - b.start)
    return segments
  }

  // Handle line number click
  const handleLineClick = (lineNum: number, event: React.MouseEvent) => {
    event.preventDefault()
    onLineClick?.(lineNum)
  }

  // Render a line with clickable segments
  const renderLineContent = (lineNum: number, lineText: string) => {
    const segments = getClickableSegments(lineNum, lineText)
    const langGrammar = Prism.languages[prismLanguage]

    // If no clickable segments, just render the highlighted line
    if (segments.length === 0) {
      const highlightedHtml = langGrammar
        ? Prism.highlight(lineText || ' ', langGrammar, prismLanguage)
        : (lineText || ' ').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      return <Box component="span" dangerouslySetInnerHTML={{ __html: highlightedHtml }} />
    }

    // Build parts: alternating between plain text and clickable segments
    const parts: React.ReactNode[] = []
    let lastEnd = 0

    segments.forEach((seg, i) => {
      // Add plain text before this segment
      if (seg.start > lastEnd) {
        const plainText = lineText.substring(lastEnd, seg.start)
        const plainHtml = langGrammar
          ? Prism.highlight(plainText, langGrammar, prismLanguage)
          : plainText.replace(/</g, '&lt;').replace(/>/g, '&gt;')
        parts.push(
          <Box
            key={`plain-${i}`}
            component="span"
            dangerouslySetInnerHTML={{ __html: plainHtml }}
          />
        )
      }

      // Add the clickable segment
      const segmentText = lineText.substring(seg.start, seg.end)
      const segmentHtml = langGrammar
        ? Prism.highlight(segmentText, langGrammar, prismLanguage)
        : segmentText.replace(/</g, '&lt;').replace(/>/g, '&gt;')

      if (seg.type === 'symbol' && seg.symbol) {
        const sym = seg.symbol
        parts.push(
          <Tooltip
            key={`sym-${i}`}
            title={
              <Box>
                <Typography variant="body2" fontWeight="bold">
                  {sym.name}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {sym.kind}
                  {sym.signature && <> - {sym.signature}</>}
                </Typography>
              </Box>
            }
            placement="top-start"
            arrow
          >
            <Box
              component="span"
              onClick={() => onSymbolClick?.(sym)}
              sx={{
                cursor: onSymbolClick ? 'pointer' : 'default',
                '&:hover': onSymbolClick
                  ? {
                      textDecoration: 'underline',
                      textDecorationColor: '#569cd6',
                    }
                  : {},
              }}
              dangerouslySetInnerHTML={{ __html: segmentHtml }}
            />
          </Tooltip>
        )
      } else if (seg.type === 'reference' && seg.reference && onReferenceClick) {
        const ref = seg.reference
        parts.push(
          <Tooltip
            key={`ref-${i}`}
            title={
              <Box>
                <Typography variant="body2" fontWeight="bold">
                  {ref.reference_text}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {ref.reference_type} - Click to see references
                </Typography>
              </Box>
            }
            placement="top-start"
            arrow
          >
            <Box
              component="span"
              onClick={() => onReferenceClick(ref)}
              sx={{
                cursor: 'pointer',
                '&:hover': {
                  textDecoration: 'underline',
                  textDecorationColor: '#4ec9b0',
                },
              }}
              dangerouslySetInnerHTML={{ __html: segmentHtml }}
            />
          </Tooltip>
        )
      }

      lastEnd = seg.end
    })

    // Add any remaining plain text after the last segment
    if (lastEnd < lineText.length) {
      const plainText = lineText.substring(lastEnd)
      const plainHtml = langGrammar
        ? Prism.highlight(plainText, langGrammar, prismLanguage)
        : plainText.replace(/</g, '&lt;').replace(/>/g, '&gt;')
      parts.push(
        <Box key="plain-end" component="span" dangerouslySetInnerHTML={{ __html: plainHtml }} />
      )
    }

    // Handle empty line
    if (parts.length === 0) {
      return <Box component="span">&nbsp;</Box>
    }

    return <>{parts}</>
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        fontFamily: 'monospace',
        fontSize: '13px',
        lineHeight: '1.5',
        overflow: 'auto',
        bgcolor: '#1e1e1e',
        borderRadius: 1,
      }}
    >
      {/* Render line by line for line numbers and highlighting */}
      <Box component="table" sx={{ borderCollapse: 'collapse', width: '100%', textAlign: 'left' }}>
        <Box component="tbody">
          {lines.map((line, index) => {
            const lineNum = index + 1
            const isHighlighted = isLineHighlighted(lineNum)

            return (
              <Box
                component="tr"
                key={lineNum}
                data-line={lineNum}
                sx={{
                  bgcolor: isHighlighted ? 'rgba(255, 255, 0, 0.1)' : 'transparent',
                  '&:hover': {
                    bgcolor: isHighlighted
                      ? 'rgba(255, 255, 0, 0.15)'
                      : 'rgba(255, 255, 255, 0.05)',
                  },
                }}
              >
                {/* Line number */}
                <Box
                  component="td"
                  onClick={(e) => handleLineClick(lineNum, e)}
                  sx={{
                    width: '50px',
                    minWidth: '50px',
                    textAlign: 'right',
                    pr: 2,
                    pl: 1,
                    color: isHighlighted ? '#ffeb3b' : '#6e7681',
                    userSelect: 'none',
                    cursor: 'pointer',
                    borderRight: '1px solid #333',
                    '&:hover': {
                      color: '#fff',
                    },
                  }}
                >
                  {lineNum}
                </Box>

                {/* Code content */}
                <Box
                  component="td"
                  sx={{
                    pl: 2,
                    pr: 2,
                    whiteSpace: 'pre',
                    color: '#d4d4d4',
                    textAlign: 'left',
                  }}
                >
                  {renderLineContent(lineNum, line)}
                </Box>
              </Box>
            )
          })}
        </Box>
      </Box>
    </Box>
  )
}

export default CodeViewer
