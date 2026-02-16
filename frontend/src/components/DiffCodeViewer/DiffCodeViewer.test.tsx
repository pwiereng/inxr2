import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent, act } from '@/test/utils'
import { DiffCodeViewer } from './DiffCodeViewer'

// jsdom doesn't implement scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

// Minimal props for DiffCodeViewer
const defaultProps = {
  leftContent: `line 1
line 2
line 3
line 4
line 5`,
  rightContent: `line 1
CHANGED line 2
line 3
ADDED line
line 4
line 5`,
  leftHeader: <span>Left</span>,
  rightHeader: <span>Right</span>,
  language: 'text',
  activePanel: 'left' as const,
  onPanelClick: vi.fn(),
  onClosePanel: vi.fn(),
}

describe('DiffCodeViewer', () => {
  describe('arrow navigation', () => {
    it('should show change counter when there are diff changes', () => {
      render(<DiffCodeViewer {...defaultProps} />)

      // Should display a change counter like "1 / N"
      const counter = screen.getByText(/1\s*\/\s*\d+/)
      expect(counter).toBeInTheDocument()
    })

    it('should navigate to next change when clicking down arrow', async () => {
      // Use content with 2 clearly separated change blocks
      const leftContent = `line 1
line 2
line 3
line 4
line 5
line 6
line 7
line 8
line 9
line 10`
      const rightContent = `line 1
CHANGED
line 3
line 4
line 5
line 6
line 7
line 8
ALSO CHANGED
line 10`

      render(
        <DiffCodeViewer {...defaultProps} leftContent={leftContent} rightContent={rightContent} />
      )

      // Should start at change 1 / 2
      expect(screen.getByText(/1\s*\/\s*2/)).toBeInTheDocument()

      // Find and click the down arrow button (next change)
      const downButton = screen
        .getByTestId('KeyboardArrowDownIcon')
        .closest('button') as HTMLButtonElement
      expect(downButton).not.toBeNull()
      expect(downButton).not.toBeDisabled()

      // Click the down arrow
      await act(async () => {
        fireEvent.click(downButton)
      })

      // Should now show 2 / 2
      expect(screen.getByText(/2\s*\/\s*2/)).toBeInTheDocument()
    })

    it('should navigate back to previous change when clicking up arrow', async () => {
      const leftContent = `line 1
line 2
line 3
line 4
line 5
line 6
line 7
line 8
line 9
line 10`
      const rightContent = `line 1
CHANGED
line 3
line 4
line 5
line 6
line 7
line 8
ALSO CHANGED
line 10`

      render(
        <DiffCodeViewer {...defaultProps} leftContent={leftContent} rightContent={rightContent} />
      )

      // Navigate to change 2
      const downButton = screen
        .getByTestId('KeyboardArrowDownIcon')
        .closest('button') as HTMLButtonElement

      await act(async () => {
        fireEvent.click(downButton)
      })

      expect(screen.getByText(/2\s*\/\s*2/)).toBeInTheDocument()

      // Navigate back to change 1
      const upButton = screen
        .getByTestId('KeyboardArrowUpIcon')
        .closest('button') as HTMLButtonElement
      expect(upButton).not.toBeDisabled()

      await act(async () => {
        fireEvent.click(upButton)
      })

      expect(screen.getByText(/1\s*\/\s*2/)).toBeInTheDocument()
    })
  })

  describe('context menu', () => {
    it('should show menu on right-click when text is selected and onSearchText provided', () => {
      const onSearchText = vi.fn()
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => 'diffText',
      } as Selection)

      render(<DiffCodeViewer {...defaultProps} onSearchText={onSearchText} />)

      // Right-click on a code area in the left panel
      const tables = document.querySelectorAll('table')
      expect(tables.length).toBeGreaterThan(0)
      fireEvent.contextMenu(tables[0]!)

      // Menu item should appear
      expect(screen.getByText(/Search for/)).toBeInTheDocument()
      expect(screen.getByText(/diffText/)).toBeInTheDocument()
    })

    it('should call onSearchText with selected text when menu item is clicked', () => {
      const onSearchText = vi.fn()
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => 'myDiffVar',
      } as Selection)

      render(<DiffCodeViewer {...defaultProps} onSearchText={onSearchText} />)

      const tables = document.querySelectorAll('table')
      fireEvent.contextMenu(tables[0]!)

      fireEvent.click(screen.getByText(/Search for/))

      expect(onSearchText).toHaveBeenCalledWith('myDiffVar')
    })

    it('should NOT show menu when no text is selected', () => {
      const onSearchText = vi.fn()
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => '',
      } as Selection)

      render(<DiffCodeViewer {...defaultProps} onSearchText={onSearchText} />)

      const tables = document.querySelectorAll('table')
      fireEvent.contextMenu(tables[0]!)

      expect(screen.queryByText(/Search for/)).not.toBeInTheDocument()
    })
  })
})
