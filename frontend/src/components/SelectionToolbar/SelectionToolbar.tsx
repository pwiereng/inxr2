import { useRef } from 'react'
import { Popper, Paper, IconButton, Tooltip } from '@mui/material'
import type { VirtualElement } from '@popperjs/core'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import SearchIcon from '@mui/icons-material/Search'

import type { SelectionToolbarState } from '@/hooks/useSelectionToolbar'

interface SelectionToolbarProps {
  toolbar: SelectionToolbarState | null
  onCopy: () => void
  onSearch: () => void
  onClose: () => void
}

/**
 * A small floating toolbar that appears above selected text.
 * Does not replace the native right-click context menu.
 */
export function SelectionToolbar({
  toolbar,
  onCopy,
  onSearch,
  onClose,
}: SelectionToolbarProps): React.ReactElement {
  const open = toolbar !== null

  const anchorRef = useRef<VirtualElement>({
    getBoundingClientRect: () => new DOMRect(0, 0, 0, 0),
  })

  if (toolbar) {
    anchorRef.current = {
      getBoundingClientRect: () => new DOMRect(toolbar.anchorX, toolbar.anchorY, 0, 0),
    }
  }

  return (
    <Popper
      open={open}
      anchorEl={anchorRef.current}
      placement="top"
      style={{ zIndex: 1300 }}
      modifiers={[{ name: 'offset', options: { offset: [0, 8] } }]}
    >
      <Paper
        data-selection-toolbar
        elevation={6}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.25,
          px: 0.5,
          py: 0.25,
          borderRadius: 1,
        }}
      >
        <Tooltip title={`Copy '${toolbar?.displayText}'`} placement="top">
          <IconButton
            size="small"
            aria-label="Copy selected text"
            onClick={() => {
              onClose()
              onCopy()
            }}
            sx={{ p: 0.5 }}
          >
            <ContentCopyIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title={`Search for '${toolbar?.displayText}'`} placement="top">
          <IconButton
            size="small"
            aria-label="Search selected text"
            onClick={() => {
              onClose()
              onSearch()
            }}
            sx={{ p: 0.5 }}
          >
            <SearchIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </Paper>
    </Popper>
  )
}
