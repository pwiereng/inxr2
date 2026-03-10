import { useRef, useEffect, useCallback } from 'react'
import {
  Popper,
  Paper,
  MenuList,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  ClickAwayListener,
} from '@mui/material'
import type { VirtualElement } from '@popperjs/core'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import SearchIcon from '@mui/icons-material/Search'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'

export interface SymbolContextMenuState {
  mouseX: number
  mouseY: number
  symbolName: string
  hasDefinition: boolean
}

interface SymbolContextMenuProps {
  contextMenu: SymbolContextMenuState | null
  onCopyName: () => void
  onSearchSymbol: () => void
  onGoToDefinition: () => void
  onClose: () => void
}

/**
 * Right-click context menu for symbols in the LogicalView.
 * Uses Popper (same pattern as CodeContextMenu) to avoid MUI Modal aria-hidden issues.
 */
export function SymbolContextMenu({
  contextMenu,
  onCopyName,
  onSearchSymbol,
  onGoToDefinition,
  onClose,
}: SymbolContextMenuProps): React.ReactElement {
  const open = contextMenu !== null

  const anchorRef = useRef<VirtualElement>({
    getBoundingClientRect: () => new DOMRect(0, 0, 0, 0),
  })

  if (contextMenu) {
    anchorRef.current = {
      getBoundingClientRect: () => new DOMRect(contextMenu.mouseX, contextMenu.mouseY, 0, 0),
    }
  }

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    },
    [onClose]
  )

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, handleKeyDown])

  return (
    <Popper
      open={open}
      anchorEl={anchorRef.current}
      placement="bottom-start"
      style={{ zIndex: 1300 }}
    >
      <ClickAwayListener onClickAway={onClose}>
        <Paper elevation={8} sx={{ minWidth: 200 }}>
          <MenuList autoFocusItem={false}>
            <MenuItem
              onClick={() => {
                onClose()
                onCopyName()
              }}
            >
              <ListItemIcon>
                <ContentCopyIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Copy name</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={() => {
                onClose()
                onSearchSymbol()
              }}
            >
              <ListItemIcon>
                <SearchIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Search symbol</ListItemText>
            </MenuItem>
            {contextMenu?.hasDefinition && (
              <>
                <Divider />
                <MenuItem
                  onClick={() => {
                    onClose()
                    onGoToDefinition()
                  }}
                >
                  <ListItemIcon>
                    <OpenInNewIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText>Go to definition</ListItemText>
                </MenuItem>
              </>
            )}
          </MenuList>
        </Paper>
      </ClickAwayListener>
    </Popper>
  )
}
