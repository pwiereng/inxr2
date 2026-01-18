import { useEffect, useRef, useState } from 'react'
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
  const [hoveredSymbol, setHoveredSymbol] = useState<FileSymbol | null>(null)
  const [hoveredReference, setHoveredReference] = useState<FileReference | null>(null)

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

  // Find symbols on a specific line, prioritizing those that start on this line
  const getSymbolsOnLine = (lineNum: number): FileSymbol[] => {
    return symbols
      .filter((s) => lineNum >= s.start_line && lineNum <= s.end_line)
      .sort((a, b) => {
        // Prioritize symbols that start on this line (definitions)
        const aStartsHere = a.start_line === lineNum
        const bStartsHere = b.start_line === lineNum
        if (aStartsHere && !bStartsHere) return -1
        if (!aStartsHere && bStartsHere) return 1
        // For symbols starting on this line, sort by column (leftmost first)
        if (aStartsHere && bStartsHere) {
          return a.start_column - b.start_column
        }
        // For enclosing symbols, prefer the most specific (larger start_line = smaller scope)
        return b.start_line - a.start_line
      })
  }

  // Find references on a specific line (only those with resolved target_symbol_id)
  const getReferencesOnLine = (lineNum: number): FileReference[] => {
    return references.filter((r) => r.source_line === lineNum && r.target_symbol_id !== null)
  }

  // Handle line number click
  const handleLineClick = (lineNum: number, event: React.MouseEvent) => {
    event.preventDefault()
    onLineClick?.(lineNum)
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
            const lineSymbols = getSymbolsOnLine(lineNum)
            const lineRefs = getReferencesOnLine(lineNum)

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
                  {(() => {
                    const firstSymbol = lineSymbols[0]
                    const firstRef = lineRefs[0]
                    // Get grammar for the language
                    const langGrammar = Prism.languages[prismLanguage]

                    const highlightedHtml = langGrammar
                      ? Prism.highlight(line || ' ', langGrammar, prismLanguage)
                      : (line || ' ').replace(/</g, '&lt;').replace(/>/g, '&gt;')

                    // Symbol definition takes priority (clickable to find usages)
                    if (firstSymbol && firstSymbol.start_line === lineNum) {
                      return (
                        <Tooltip
                          title={
                            <Box>
                              <Typography variant="body2" fontWeight="bold">
                                {hoveredSymbol?.name ?? firstSymbol.name}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {hoveredSymbol?.kind ?? firstSymbol.kind}
                                {(hoveredSymbol?.signature ?? firstSymbol.signature) && (
                                  <> - {hoveredSymbol?.signature ?? firstSymbol.signature}</>
                                )}
                              </Typography>
                            </Box>
                          }
                          placement="top-start"
                          arrow
                        >
                          <Box
                            component="span"
                            onClick={() => onSymbolClick?.(firstSymbol)}
                            onMouseEnter={() => setHoveredSymbol(firstSymbol)}
                            onMouseLeave={() => setHoveredSymbol(null)}
                            sx={{
                              cursor: onSymbolClick ? 'pointer' : 'default',
                              '&:hover': onSymbolClick
                                ? {
                                    textDecoration: 'underline',
                                    textDecorationColor: '#569cd6',
                                  }
                                : {},
                            }}
                            dangerouslySetInnerHTML={{ __html: highlightedHtml }}
                          />
                        </Tooltip>
                      )
                    }

                    // Reference with resolved target (clickable to find all usages of that symbol)
                    if (firstRef && onReferenceClick) {
                      return (
                        <Tooltip
                          title={
                            <Box>
                              <Typography variant="body2" fontWeight="bold">
                                {hoveredReference?.reference_text ?? firstRef.reference_text}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {hoveredReference?.reference_type ?? firstRef.reference_type} -
                                Click to see references
                              </Typography>
                            </Box>
                          }
                          placement="top-start"
                          arrow
                        >
                          <Box
                            component="span"
                            onClick={() => onReferenceClick(firstRef)}
                            onMouseEnter={() => setHoveredReference(firstRef)}
                            onMouseLeave={() => setHoveredReference(null)}
                            sx={{
                              cursor: 'pointer',
                              '&:hover': {
                                textDecoration: 'underline',
                                textDecorationColor: '#4ec9b0',
                              },
                            }}
                            dangerouslySetInnerHTML={{ __html: highlightedHtml }}
                          />
                        </Tooltip>
                      )
                    }

                    return (
                      <Box component="span" dangerouslySetInnerHTML={{ __html: highlightedHtml }} />
                    )
                  })()}
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
