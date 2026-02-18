import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import { Box, Typography, Tooltip, IconButton } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import CloseIcon from '@mui/icons-material/Close'
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import Prism from 'prismjs'
import * as Diff from 'diff'
import { getPrismLanguage } from '@/lib/prismLanguages'

import type { FileSymbol, FileReference } from '@/lib/api'
import { useCodeContextMenu } from '@/hooks/useCodeContextMenu'
import { CodeContextMenu } from '@/components/CodeContextMenu'

interface DiffCodeViewerProps {
  leftContent: string
  rightContent: string
  leftHeader: React.ReactNode
  rightHeader: React.ReactNode
  language: string | null
  leftSymbols?: FileSymbol[]
  rightSymbols?: FileSymbol[]
  leftReferences?: FileReference[]
  rightReferences?: FileReference[]
  highlightLine?: number
  activePanel: 'left' | 'right'
  onPanelClick: (panel: 'left' | 'right') => void
  onSymbolClick?: (symbol: FileSymbol, panel: 'left' | 'right') => void
  onReferenceClick?: (reference: FileReference, panel: 'left' | 'right') => void
  onLineClick?: (line: number, panel: 'left' | 'right') => void
  onClosePanel: (panel: 'left' | 'right') => void
  onSearchText?: (text: string) => void
}

interface DiffLine {
  leftLineNum: number | null
  rightLineNum: number | null
  leftContent: string
  rightContent: string
  type: 'unchanged' | 'added' | 'removed' | 'modified'
}

// Compute side-by-side diff
function computeSideBySideDiff(leftContent: string, rightContent: string): DiffLine[] {
  const leftLines = leftContent.split('\n')
  const rightLines = rightContent.split('\n')

  // Use line-by-line diff
  const changes = Diff.diffArrays(leftLines, rightLines)

  const result: DiffLine[] = []
  let leftLineNum = 1
  let rightLineNum = 1

  for (const change of changes) {
    if (!change.added && !change.removed) {
      // Unchanged lines
      for (const line of change.value) {
        result.push({
          leftLineNum: leftLineNum++,
          rightLineNum: rightLineNum++,
          leftContent: line,
          rightContent: line,
          type: 'unchanged',
        })
      }
    } else if (change.added) {
      // Added lines (only on right)
      for (const line of change.value) {
        result.push({
          leftLineNum: null,
          rightLineNum: rightLineNum++,
          leftContent: '',
          rightContent: line,
          type: 'added',
        })
      }
    } else if (change.removed) {
      // Removed lines (only on left)
      for (const line of change.value) {
        result.push({
          leftLineNum: leftLineNum++,
          rightLineNum: null,
          leftContent: line,
          rightContent: '',
          type: 'removed',
        })
      }
    }
  }

  return result
}

// Represents a clickable segment in a line
interface ClickableSegment {
  start: number
  end: number
  type: 'symbol' | 'reference'
  symbol?: FileSymbol
  reference?: FileReference
}

export function DiffCodeViewer({
  leftContent,
  rightContent,
  leftHeader,
  rightHeader,
  language,
  leftSymbols = [],
  rightSymbols = [],
  leftReferences = [],
  rightReferences = [],
  highlightLine,
  activePanel,
  onPanelClick,
  onSymbolClick,
  onReferenceClick,
  onLineClick,
  onClosePanel,
  onSearchText,
}: DiffCodeViewerProps) {
  const leftContainerRef = useRef<HTMLDivElement>(null)
  const rightContainerRef = useRef<HTMLDivElement>(null)
  const [syncScroll] = useState(true)
  const theme = useTheme()
  const { contextMenu, handleContextMenu, handleClose } = useCodeContextMenu()

  const prismLanguage = getPrismLanguage(language)
  const langGrammar = Prism.languages[prismLanguage]

  // Compute diff (memoized to prevent re-renders from resetting navigation state)
  const diffLines = useMemo(
    () => computeSideBySideDiff(leftContent, rightContent),
    [leftContent, rightContent]
  )

  // Find all change indices (for navigation)
  const changeIndices = useMemo(() => {
    const indices: number[] = []
    let inChangeBlock = false

    diffLines.forEach((line, index) => {
      const isChange = line.type === 'added' || line.type === 'removed' || line.type === 'modified'
      if (isChange && !inChangeBlock) {
        // Start of a new change block
        indices.push(index)
        inChangeBlock = true
      } else if (!isChange) {
        inChangeBlock = false
      }
    })

    return indices
  }, [diffLines])

  // Track current change index (use ref to avoid stale closures in keyboard handler)
  const [currentChangeIndex, setCurrentChangeIndex] = useState(0)
  const currentChangeIndexRef = useRef(currentChangeIndex)

  // Keep ref in sync with state
  useEffect(() => {
    currentChangeIndexRef.current = currentChangeIndex
  }, [currentChangeIndex])

  // Scroll to a specific change
  const scrollToChange = useCallback(
    (index: number) => {
      if (index < 0 || index >= changeIndices.length) return

      const rowIndex = changeIndices[index]
      if (rowIndex === undefined) return

      const leftEl = leftContainerRef.current
      if (!leftEl) return

      const rows = leftEl.querySelectorAll('tr')
      const targetRow = rows[rowIndex]
      if (targetRow) {
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' })
        setCurrentChangeIndex(index)
      }
    },
    [changeIndices]
  )

  // Navigate to previous change (use ref to always get current value)
  const goToPreviousChange = useCallback(() => {
    const newIndex = Math.max(0, currentChangeIndexRef.current - 1)
    scrollToChange(newIndex)
  }, [scrollToChange])

  // Navigate to next change (use ref to always get current value)
  const goToNextChange = useCallback(() => {
    const newIndex = Math.min(changeIndices.length - 1, currentChangeIndexRef.current + 1)
    scrollToChange(newIndex)
  }, [changeIndices.length, scrollToChange])

  // Keyboard navigation for diff changes
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle if not in an input/textarea
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      if (e.key === 'ArrowUp' && e.altKey) {
        e.preventDefault()
        goToPreviousChange()
      } else if (e.key === 'ArrowDown' && e.altKey) {
        e.preventDefault()
        goToNextChange()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [goToPreviousChange, goToNextChange])

  // Sync scrolling between panels
  useEffect(() => {
    if (!syncScroll) return

    const leftEl = leftContainerRef.current
    const rightEl = rightContainerRef.current
    if (!leftEl || !rightEl) return

    let isScrolling = false

    const handleLeftScroll = () => {
      if (isScrolling) return
      isScrolling = true
      rightEl.scrollTop = leftEl.scrollTop
      rightEl.scrollLeft = leftEl.scrollLeft
      requestAnimationFrame(() => {
        isScrolling = false
      })
    }

    const handleRightScroll = () => {
      if (isScrolling) return
      isScrolling = true
      leftEl.scrollTop = rightEl.scrollTop
      leftEl.scrollLeft = rightEl.scrollLeft
      requestAnimationFrame(() => {
        isScrolling = false
      })
    }

    leftEl.addEventListener('scroll', handleLeftScroll)
    rightEl.addEventListener('scroll', handleRightScroll)

    return () => {
      leftEl.removeEventListener('scroll', handleLeftScroll)
      rightEl.removeEventListener('scroll', handleRightScroll)
    }
  }, [syncScroll])

  // Auto-scroll to first change when diff loads
  useEffect(() => {
    if (changeIndices.length === 0) return

    // Reset to first change and scroll
    setCurrentChangeIndex(0)

    // Wait for DOM to render, then scroll
    const timeoutId = setTimeout(() => {
      const rowIndex = changeIndices[0]
      if (rowIndex === undefined) return

      const leftEl = leftContainerRef.current
      if (!leftEl) return

      const rows = leftEl.querySelectorAll('tr')
      const targetRow = rows[rowIndex]
      if (targetRow) {
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 100)

    return () => clearTimeout(timeoutId)
  }, [leftContent, rightContent, changeIndices])

  // Check if a substring at [start, end) is a complete word
  const isWholeWordMatch = (text: string, start: number, end: number): boolean => {
    const charBefore = start > 0 ? (text[start - 1] ?? '') : ''
    const charAfter = end < text.length ? (text[end] ?? '') : ''
    const boundaryBefore = start === 0 || !/\w/.test(charBefore)
    const boundaryAfter = end >= text.length || !/\w/.test(charAfter)
    return boundaryBefore && boundaryAfter
  }

  // Get symbols that START on this line (definitions)
  const getSymbolDefinitionsOnLine = (lineNum: number, symbols: FileSymbol[]): FileSymbol[] => {
    return symbols
      .filter((s) => s.start_line === lineNum)
      .sort((a, b) => a.start_column - b.start_column)
  }

  // Get references on this line
  const getReferencesOnLine = (lineNum: number, references: FileReference[]): FileReference[] => {
    return references
      .filter((r) => r.source_line === lineNum && r.target_symbol_id !== null)
      .sort((a, b) => a.source_column - b.source_column)
  }

  // Build clickable segments for a line
  const getClickableSegments = (
    lineNum: number,
    lineText: string,
    symbols: FileSymbol[],
    references: FileReference[]
  ): ClickableSegment[] => {
    const segments: ClickableSegment[] = []

    // Add symbol definitions
    for (const sym of getSymbolDefinitionsOnLine(lineNum, symbols)) {
      let searchStart = sym.start_column
      let nameIndex = -1

      while (searchStart < lineText.length) {
        const idx = lineText.indexOf(sym.name, searchStart)
        if (idx === -1) break

        if (isWholeWordMatch(lineText, idx, idx + sym.name.length)) {
          nameIndex = idx
          break
        }
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
    for (const ref of getReferencesOnLine(lineNum, references)) {
      const startCol = ref.source_column
      const refEnd = startCol + ref.reference_text.length
      if (lineText.substring(startCol, refEnd) === ref.reference_text) {
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

    segments.sort((a, b) => a.start - b.start)
    return segments
  }

  // Render line content with clickable segments
  const renderLineContent = (
    lineNum: number | null,
    lineText: string,
    symbols: FileSymbol[],
    references: FileReference[],
    panel: 'left' | 'right'
  ) => {
    if (lineNum === null || !lineText) {
      return <Box component="span">&nbsp;</Box>
    }

    const segments = getClickableSegments(lineNum, lineText, symbols, references)

    if (segments.length === 0) {
      const highlightedHtml = langGrammar
        ? Prism.highlight(lineText || ' ', langGrammar, prismLanguage)
        : (lineText || ' ').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      return <Box component="span" dangerouslySetInnerHTML={{ __html: highlightedHtml }} />
    }

    const parts: React.ReactNode[] = []
    let lastEnd = 0

    segments.forEach((seg, i) => {
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
              onClick={(e) => {
                e.stopPropagation()
                onSymbolClick?.(sym, panel)
              }}
              sx={{
                cursor: onSymbolClick ? 'pointer' : 'default',
                '&:hover': onSymbolClick
                  ? {
                      textDecoration: 'underline',
                      textDecorationColor: theme.palette.code.symbolUnderline,
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
              onClick={(e) => {
                e.stopPropagation()
                onReferenceClick(ref, panel)
              }}
              sx={{
                cursor: 'pointer',
                '&:hover': {
                  textDecoration: 'underline',
                  textDecorationColor: theme.palette.code.referenceUnderline,
                },
              }}
              dangerouslySetInnerHTML={{ __html: segmentHtml }}
            />
          </Tooltip>
        )
      }

      lastEnd = seg.end
    })

    if (lastEnd < lineText.length) {
      const plainText = lineText.substring(lastEnd)
      const plainHtml = langGrammar
        ? Prism.highlight(plainText, langGrammar, prismLanguage)
        : plainText.replace(/</g, '&lt;').replace(/>/g, '&gt;')
      parts.push(
        <Box key="plain-end" component="span" dangerouslySetInnerHTML={{ __html: plainHtml }} />
      )
    }

    if (parts.length === 0) {
      return <Box component="span">&nbsp;</Box>
    }

    return <>{parts}</>
  }

  // Get background color for diff type
  const getDiffBgColor = (type: DiffLine['type'], isLeft: boolean) => {
    switch (type) {
      case 'added':
        return isLeft ? 'transparent' : theme.palette.code.diffAddedBg
      case 'removed':
        return isLeft ? theme.palette.code.diffRemovedBg : 'transparent'
      case 'modified':
        return theme.palette.code.diffModifiedBg
      default:
        return 'transparent'
    }
  }

  // Render a panel
  const renderPanel = (
    panel: 'left' | 'right',
    header: React.ReactNode,
    containerRef: React.RefObject<HTMLDivElement | null>,
    symbols: FileSymbol[],
    references: FileReference[]
  ) => {
    const isActive = activePanel === panel

    return (
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          borderLeft: panel === 'right' ? 1 : 0,
          borderColor: 'divider',
          outline: isActive ? '1px solid' : 'none',
          outlineColor: 'primary.light',
          outlineOffset: '-1px',
        }}
        onClick={() => onPanelClick(panel)}
      >
        {/* Panel header */}
        <Box
          sx={{
            px: 2,
            py: 0.5,
            bgcolor: isActive ? 'action.selected' : 'background.paper',
            borderBottom: 1,
            borderColor: isActive ? 'primary.light' : 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              flex: 1,
              minWidth: 0, // Allow shrinking below content size
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {header}
          </Box>
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation()
              onClosePanel(panel)
            }}
            sx={{
              p: 0.25,
              flexShrink: 0, // Never shrink the close button
              color: isActive ? 'primary.main' : 'text.secondary',
              '&:hover': { bgcolor: 'action.hover' },
            }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>

        {/* Code content */}
        <Box
          ref={containerRef}
          onContextMenu={onSearchText ? handleContextMenu : undefined}
          sx={{
            flex: 1,
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: '13px',
            lineHeight: '1.5',
            bgcolor: 'background.default',
          }}
        >
          <Box
            component="table"
            sx={{ borderCollapse: 'collapse', width: '100%', textAlign: 'left' }}
          >
            <Box component="tbody">
              {diffLines.map((line, index) => {
                const lineNum = panel === 'left' ? line.leftLineNum : line.rightLineNum
                const content = panel === 'left' ? line.leftContent : line.rightContent
                const bgColor = getDiffBgColor(line.type, panel === 'left')
                const isHighlighted =
                  highlightLine !== undefined && lineNum === highlightLine && isActive

                return (
                  <Box
                    component="tr"
                    key={index}
                    sx={{
                      bgcolor: isHighlighted ? theme.palette.code.highlightBg : bgColor,
                      '&:hover': {
                        bgcolor: isHighlighted
                          ? theme.palette.code.highlightHoverBg
                          : theme.palette.code.hoverBg,
                      },
                    }}
                  >
                    {/* Line number */}
                    <Box
                      component="td"
                      onClick={(e) => {
                        e.stopPropagation()
                        if (lineNum !== null) {
                          onLineClick?.(lineNum, panel)
                        }
                      }}
                      sx={{
                        width: '40px',
                        minWidth: '40px',
                        textAlign: 'right',
                        pr: 1,
                        pl: 1,
                        color: lineNum === null ? 'transparent' : theme.palette.code.lineNumber,
                        userSelect: 'none',
                        cursor: lineNum !== null ? 'pointer' : 'default',
                        borderRight: `1px solid ${theme.palette.code.lineBorder}`,
                        '&:hover':
                          lineNum !== null ? { color: theme.palette.code.lineNumberHover } : {},
                      }}
                    >
                      {lineNum ?? ''}
                    </Box>

                    {/* Diff indicator */}
                    <Box
                      component="td"
                      sx={{
                        width: '16px',
                        minWidth: '16px',
                        textAlign: 'center',
                        color:
                          line.type === 'added'
                            ? theme.palette.code.diffAddedIndicator
                            : line.type === 'removed'
                              ? theme.palette.code.diffRemovedIndicator
                              : 'transparent',
                        fontWeight: 'bold',
                      }}
                    >
                      {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ''}
                    </Box>

                    {/* Code content */}
                    <Box
                      component="td"
                      sx={{
                        pl: 1,
                        pr: 2,
                        whiteSpace: 'pre',
                        color: theme.palette.code.text,
                        textAlign: 'left',
                      }}
                    >
                      {renderLineContent(lineNum, content, symbols, references, panel)}
                    </Box>
                  </Box>
                )
              })}
            </Box>
          </Box>
        </Box>
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* Diff navigation bar */}
      {changeIndices.length > 0 && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 1,
            py: 0.5,
            px: 2,
            bgcolor: 'background.paper',
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Tooltip title="Previous change (↑)">
            <span>
              <IconButton
                size="small"
                onClick={goToPreviousChange}
                disabled={currentChangeIndex === 0}
              >
                <KeyboardArrowUpIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Typography
            variant="caption"
            sx={{ fontFamily: 'monospace', minWidth: 60, textAlign: 'center' }}
          >
            {currentChangeIndex + 1} / {changeIndices.length}
          </Typography>
          <Tooltip title="Next change (↓)">
            <span>
              <IconButton
                size="small"
                onClick={goToNextChange}
                disabled={currentChangeIndex === changeIndices.length - 1}
              >
                <KeyboardArrowDownIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      )}

      {/* Diff panels */}
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {renderPanel('left', leftHeader, leftContainerRef, leftSymbols, leftReferences)}
        {renderPanel('right', rightHeader, rightContainerRef, rightSymbols, rightReferences)}
      </Box>
      {onSearchText && (
        <CodeContextMenu
          contextMenu={contextMenu}
          onSearch={() => onSearchText(contextMenu?.selectedText ?? '')}
          onClose={handleClose}
        />
      )}
    </Box>
  )
}

export default DiffCodeViewer
