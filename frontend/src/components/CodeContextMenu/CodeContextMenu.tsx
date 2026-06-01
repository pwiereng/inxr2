import { useMemo, useEffect, useCallback } from 'react'
import {
  Popper,
  Paper,
  MenuList,
  MenuItem,
  ListItemIcon,
  ListItemText,
  ClickAwayListener,
} from '@mui/material'
import type { VirtualElement } from '@popperjs/core'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import SearchIcon from '@mui/icons-material/Search'

import type { ContextMenuState } from '@/hooks/useCodeContextMenu'

interface CodeContextMenuProps {
  contextMenu: ContextMenuState | null
  onSearch: () => void
  onClose: () => void
  /** When provided, shows a "Copy" menu item that copies selected text to clipboard. */
  onCopy?: () => void
}

/**
 * A context menu that uses Popper + MenuList instead of MUI's Menu component.
 *
 * MUI's Menu uses Popover -> Modal -> FocusTrap. When the menu closes, Modal
 * sets aria-hidden on its root while the Paper element still has focus, causing
 * a browser warning: "Blocked aria-hidden on an element because its descendant
 * retained focus." This is a known timing issue in MUI's Modal focus management.
 *
 * By using Popper directly, we bypass the Modal/FocusTrap layer entirely,
 * eliminating the aria-hidden warning while preserving the same visual behavior.
 */
export function CodeContextMenu({
  contextMenu,
  onSearch,
  onClose,
  onCopy,
}: CodeContextMenuProps): React.ReactElement {
  const open = contextMenu !== null

  // Virtual anchor element for Popper positioning at mouse coordinates.
  // Derived with useMemo (not a ref written during render) so Popper gets a fresh
  // reference whenever the coordinates change, which triggers it to reposition.
  const anchorEl = useMemo<VirtualElement>(
    () => ({
      getBoundingClientRect: () =>
        new DOMRect(contextMenu?.mouseX ?? 0, contextMenu?.mouseY ?? 0, 0, 0),
    }),
    [contextMenu?.mouseX, contextMenu?.mouseY]
  )

  // Close on Escape key
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
    <Popper open={open} anchorEl={anchorEl} placement="bottom-start" style={{ zIndex: 1300 }}>
      <ClickAwayListener onClickAway={onClose}>
        <Paper elevation={8} sx={{ minWidth: 180 }}>
          <MenuList autoFocusItem={false}>
            {onCopy && (
              <MenuItem
                onClick={() => {
                  onClose()
                  onCopy()
                }}
              >
                <ListItemIcon>
                  <ContentCopyIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Copy &apos;{contextMenu?.displayText}&apos;</ListItemText>
              </MenuItem>
            )}
            <MenuItem
              onClick={() => {
                // Close first, then navigate: onSearch() triggers React Router
                // navigation which unmounts this component. Closing the Popper
                // before navigation prevents stale DOM state during unmount.
                onClose()
                onSearch()
              }}
            >
              <ListItemIcon>
                <SearchIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Search for &apos;{contextMenu?.displayText}&apos;</ListItemText>
            </MenuItem>
          </MenuList>
        </Paper>
      </ClickAwayListener>
    </Popper>
  )
}
