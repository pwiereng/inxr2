import { useState, useCallback, useEffect, useRef } from 'react'

export interface SelectionToolbarState {
  anchorX: number
  anchorY: number
  selectedText: string
  displayText: string
}

function truncateAndCollapse(text: string, maxLength: number = 40): string {
  const collapsed = text.replace(/\s+/g, ' ').trim()
  if (collapsed.length <= maxLength) return collapsed
  return collapsed.substring(0, maxLength) + '...'
}

interface UseSelectionToolbarResult {
  toolbar: SelectionToolbarState | null
  containerRef: React.MutableRefObject<HTMLDivElement | null>
  handleClose: () => void
}

/**
 * Shows a floating toolbar when text is selected within a container.
 * Does NOT intercept right-click — the native browser context menu still works.
 */
export function useSelectionToolbar(): UseSelectionToolbarResult {
  const [toolbar, setToolbar] = useState<SelectionToolbarState | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)

  const handleClose = useCallback(() => setToolbar(null), [])

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const onMouseUp = () => {
      // Clear any previously scheduled timeout to avoid stale updates
      if (timeoutId !== null) clearTimeout(timeoutId)
      // Small delay to let the browser finalize the selection
      timeoutId = setTimeout(() => {
        const container = containerRef.current
        if (!container) return

        const selection = window.getSelection()
        const selectedText = selection?.toString().trim() ?? ''

        if (!selectedText) {
          setToolbar(null)
          return
        }

        if (selection && selection.rangeCount > 0) {
          const range = selection.getRangeAt(0)
          if (!container.contains(range.commonAncestorContainer)) {
            setToolbar(null)
            return
          }
          const rect = range.getBoundingClientRect()
          setToolbar({
            anchorX: rect.left + rect.width / 2,
            anchorY: rect.top,
            selectedText,
            displayText: truncateAndCollapse(selectedText),
          })
        }
      }, 10)
    }

    const onSelectionChange = () => {
      const sel = window.getSelection()
      if (!sel || sel.toString().trim() === '') {
        setToolbar(null)
      }
    }

    const onMouseDown = (e: MouseEvent) => {
      const target = e.target
      if (target instanceof Element && target.closest('[data-selection-toolbar]')) return
      setToolbar(null)
    }

    document.addEventListener('mouseup', onMouseUp)
    document.addEventListener('selectionchange', onSelectionChange)
    document.addEventListener('mousedown', onMouseDown)

    return () => {
      if (timeoutId !== null) clearTimeout(timeoutId)
      document.removeEventListener('mouseup', onMouseUp)
      document.removeEventListener('selectionchange', onSelectionChange)
      document.removeEventListener('mousedown', onMouseDown)
    }
  }, [])

  return { toolbar, containerRef, handleClose }
}
