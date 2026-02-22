import type { SelectProps } from '@mui/material'

// Workaround for MUI Select aria-hidden warning:
// When a Select menu closes, the Popover sets aria-hidden on its container
// while a MenuItem descendant still has focus, triggering a browser warning.
// Preventing default on mousedown stops focus from moving to the MenuItem
// on click, while the click event still fires normally for selection.
export const MENU_PROPS: Partial<SelectProps['MenuProps']> = {
  MenuListProps: {
    onMouseDown: (e: React.MouseEvent) => {
      e.preventDefault()
    },
  },
}
