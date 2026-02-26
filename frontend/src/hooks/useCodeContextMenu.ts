import { useState, useCallback } from 'react'

export interface ContextMenuState {
  mouseX: number
  mouseY: number
  selectedText: string
  displayText: string
}

function truncateAndCollapse(text: string, maxLength: number = 40): string {
  // Collapse whitespace (newlines, tabs, multiple spaces) into single spaces
  const collapsed = text.replace(/\s+/g, ' ').trim()
  if (collapsed.length <= maxLength) return collapsed
  return collapsed.substring(0, maxLength) + '...'
}

interface UseCodeContextMenuResult {
  contextMenu: ContextMenuState | null
  handleContextMenu: (event: React.MouseEvent) => void
  handleClose: () => void
}

export function useCodeContextMenu(): UseCodeContextMenuResult {
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)

  const handleContextMenu = useCallback((event: React.MouseEvent) => {
    const selection = window.getSelection()
    const selectedText = selection?.toString().trim() ?? ''

    if (!selectedText) {
      // No text selected — let the native context menu show
      return
    }

    event.preventDefault()

    setContextMenu({
      mouseX: event.clientX,
      mouseY: event.clientY,
      selectedText,
      displayText: truncateAndCollapse(selectedText),
    })
  }, [])

  const handleClose = useCallback(() => {
    setContextMenu(null)
  }, [])

  return { contextMenu, handleContextMenu, handleClose }
}
