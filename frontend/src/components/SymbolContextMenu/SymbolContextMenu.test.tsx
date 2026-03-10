import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
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
