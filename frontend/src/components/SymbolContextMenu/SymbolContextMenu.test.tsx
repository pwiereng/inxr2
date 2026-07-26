import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SymbolContextMenu, type SymbolContextMenuState } from './SymbolContextMenu'

describe('SymbolContextMenu', () => {
  const defaultHandlers = {
    onCopyName: vi.fn(),
    onSearchSymbol: vi.fn(),
    onGoToDefinition: vi.fn(),
    onClose: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when contextMenu is null', () => {
    const { container } = render(<SymbolContextMenu contextMenu={null} {...defaultHandlers} />)
    expect(container.textContent).toBe('')
  })

  it('renders menu items when contextMenu is provided', () => {
    const menu: SymbolContextMenuState = {
      mouseX: 100,
      mouseY: 200,
      symbolName: 'MyClass',
      hasDefinition: true,
    }
    render(<SymbolContextMenu contextMenu={menu} {...defaultHandlers} />)
    expect(screen.getByText('Copy name')).toBeInTheDocument()
    expect(screen.getByText('Search symbol')).toBeInTheDocument()
    expect(screen.getByText('Go to definition')).toBeInTheDocument()
  })

  it('hides "Go to definition" when hasDefinition is false', () => {
    const menu: SymbolContextMenuState = {
      mouseX: 100,
      mouseY: 200,
      symbolName: 'orphan_func',
      hasDefinition: false,
    }
    render(<SymbolContextMenu contextMenu={menu} {...defaultHandlers} />)
    expect(screen.getByText('Copy name')).toBeInTheDocument()
    expect(screen.getByText('Search symbol')).toBeInTheDocument()
    expect(screen.queryByText('Go to definition')).not.toBeInTheDocument()
  })

  it('calls onCopyName and onClose when "Copy name" is clicked', () => {
    const menu: SymbolContextMenuState = {
      mouseX: 100,
      mouseY: 200,
      symbolName: 'MyClass',
      hasDefinition: false,
    }
    render(<SymbolContextMenu contextMenu={menu} {...defaultHandlers} />)
    fireEvent.click(screen.getByText('Copy name'))
    expect(defaultHandlers.onClose).toHaveBeenCalledOnce()
    expect(defaultHandlers.onCopyName).toHaveBeenCalledOnce()
  })

  it('calls onSearchSymbol and onClose when "Search symbol" is clicked', () => {
    const menu: SymbolContextMenuState = {
      mouseX: 100,
      mouseY: 200,
      symbolName: 'MyClass',
      hasDefinition: false,
    }
    render(<SymbolContextMenu contextMenu={menu} {...defaultHandlers} />)
    fireEvent.click(screen.getByText('Search symbol'))
    expect(defaultHandlers.onClose).toHaveBeenCalledOnce()
    expect(defaultHandlers.onSearchSymbol).toHaveBeenCalledOnce()
  })

  it('calls onGoToDefinition and onClose when "Go to definition" is clicked', () => {
    const menu: SymbolContextMenuState = {
      mouseX: 100,
      mouseY: 200,
      symbolName: 'MyClass',
      hasDefinition: true,
    }
    render(<SymbolContextMenu contextMenu={menu} {...defaultHandlers} />)
    fireEvent.click(screen.getByText('Go to definition'))
    expect(defaultHandlers.onClose).toHaveBeenCalledOnce()
    expect(defaultHandlers.onGoToDefinition).toHaveBeenCalledOnce()
  })

  // Regression cover for #531: the conditional "Go to definition" entry used to be
  // wrapped in a Fragment, which MenuList cannot clone focus props onto — it logged
  // "MUI: The Menu component doesn't accept a Fragment as a child." on every render
  // with hasDefinition. The fix hands MenuList a keyed array instead.
  describe('conditional "Go to definition" entry', () => {
    const menuWithDefinition: SymbolContextMenuState = {
      mouseX: 100,
      mouseY: 200,
      symbolName: 'MyClass',
      hasDefinition: true,
    }

    it('renders without MUI complaining about a Fragment child', () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      render(<SymbolContextMenu contextMenu={menuWithDefinition} {...defaultHandlers} />)
      expect(screen.getByText('Go to definition')).toBeInTheDocument()

      const fragmentWarnings = consoleError.mock.calls.filter((args) =>
        args.some((arg) => typeof arg === 'string' && arg.includes('Fragment'))
      )
      expect(fragmentWarnings).toEqual([])
    })

    it('is reachable by arrow keys and activates on Enter', async () => {
      const user = userEvent.setup()
      render(<SymbolContextMenu contextMenu={menuWithDefinition} {...defaultHandlers} />)

      // Focus the first entry, then walk down: "Search symbol", then past the
      // Divider (not focusable) onto "Go to definition".
      screen.getByRole('menuitem', { name: 'Copy name' }).focus()
      await user.keyboard('{ArrowDown}')
      expect(document.activeElement).toBe(screen.getByRole('menuitem', { name: 'Search symbol' }))
      await user.keyboard('{ArrowDown}')
      expect(document.activeElement).toBe(
        screen.getByRole('menuitem', { name: 'Go to definition' })
      )

      await user.keyboard('{Enter}')
      expect(defaultHandlers.onClose).toHaveBeenCalledOnce()
      expect(defaultHandlers.onGoToDefinition).toHaveBeenCalledOnce()
    })

    it('keeps the divider above it inside the menu list', () => {
      const { rerender } = render(
        <SymbolContextMenu contextMenu={menuWithDefinition} {...defaultHandlers} />
      )
      const list = screen.getByRole('menu')
      expect(list.querySelectorAll('hr')).toHaveLength(1)
      expect(list.children[2]?.tagName).toBe('HR')

      rerender(
        <SymbolContextMenu
          contextMenu={{ ...menuWithDefinition, hasDefinition: false }}
          {...defaultHandlers}
        />
      )
      expect(screen.getByRole('menu').querySelectorAll('hr')).toHaveLength(0)
    })
  })

  it('closes on Escape key', () => {
    const menu: SymbolContextMenuState = {
      mouseX: 100,
      mouseY: 200,
      symbolName: 'MyClass',
      hasDefinition: false,
    }
    render(<SymbolContextMenu contextMenu={menu} {...defaultHandlers} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(defaultHandlers.onClose).toHaveBeenCalledOnce()
  })
})
