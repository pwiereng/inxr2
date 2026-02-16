import { Menu, MenuItem, ListItemIcon, ListItemText } from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'

import type { ContextMenuState } from '@/hooks/useCodeContextMenu'

interface CodeContextMenuProps {
  contextMenu: ContextMenuState | null
  onSearch: () => void
  onClose: () => void
}

export function CodeContextMenu({ contextMenu, onSearch, onClose }: CodeContextMenuProps) {
  return (
    <Menu
      open={contextMenu !== null}
      onClose={onClose}
      anchorReference="anchorPosition"
      anchorPosition={
        contextMenu !== null ? { top: contextMenu.mouseY, left: contextMenu.mouseX } : undefined
      }
    >
      <MenuItem
        onClick={() => {
          onSearch()
          onClose()
        }}
      >
        <ListItemIcon>
          <SearchIcon fontSize="small" />
        </ListItemIcon>
        <ListItemText>Search for &apos;{contextMenu?.displayText}&apos;</ListItemText>
      </MenuItem>
    </Menu>
  )
}
