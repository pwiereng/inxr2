import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCodeContextMenu } from './useCodeContextMenu'

describe('useCodeContextMenu', () => {
  beforeEach(() => {
    // Reset window.getSelection mock
    vi.restoreAllMocks()
  })

  it('should return null contextMenu initially', () => {
    const { result } = renderHook(() => useCodeContextMenu())
    expect(result.current.contextMenu).toBeNull()
  })

  it('should open menu with correct coordinates when text is selected', () => {
    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => 'selectedText',
    } as Selection)

    const { result } = renderHook(() => useCodeContextMenu())

    const event = {
      clientX: 100,
      clientY: 200,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent

    act(() => {
      result.current.handleContextMenu(event)
    })

    expect(event.preventDefault).toHaveBeenCalled()
    expect(result.current.contextMenu).toEqual({
      mouseX: 100,
      mouseY: 200,
      selectedText: 'selectedText',
      displayText: 'selectedText',
    })
  })

  it('should NOT open menu when no text is selected', () => {
    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => '',
    } as Selection)

    const { result } = renderHook(() => useCodeContextMenu())

    const event = {
      clientX: 100,
      clientY: 200,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent

    act(() => {
      result.current.handleContextMenu(event)
    })

    expect(event.preventDefault).not.toHaveBeenCalled()
    expect(result.current.contextMenu).toBeNull()
  })

  it('should NOT open menu when selection is only whitespace', () => {
    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => '   \n\t  ',
    } as Selection)

    const { result } = renderHook(() => useCodeContextMenu())

    const event = {
      clientX: 100,
      clientY: 200,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent

    act(() => {
      result.current.handleContextMenu(event)
    })

    expect(event.preventDefault).not.toHaveBeenCalled()
    expect(result.current.contextMenu).toBeNull()
  })

  it('should truncate long selections in displayText but preserve raw selectedText', () => {
    const longText = 'a'.repeat(60)
    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => longText,
    } as Selection)

    const { result } = renderHook(() => useCodeContextMenu())

    const event = {
      clientX: 0,
      clientY: 0,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent

    act(() => {
      result.current.handleContextMenu(event)
    })

    expect(result.current.contextMenu!.selectedText).toBe(longText)
    expect(result.current.contextMenu!.displayText).toBe('a'.repeat(40) + '...')
  })

  it('should collapse multi-line whitespace in displayText', () => {
    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => 'hello\n  world\t\tfoo',
    } as Selection)

    const { result } = renderHook(() => useCodeContextMenu())

    const event = {
      clientX: 0,
      clientY: 0,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent

    act(() => {
      result.current.handleContextMenu(event)
    })

    expect(result.current.contextMenu!.displayText).toBe('hello world foo')
  })

  it('should reset state when handleClose is called', () => {
    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => 'text',
    } as Selection)

    const { result } = renderHook(() => useCodeContextMenu())

    const event = {
      clientX: 50,
      clientY: 50,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent

    act(() => {
      result.current.handleContextMenu(event)
    })
    expect(result.current.contextMenu).not.toBeNull()

    act(() => {
      result.current.handleClose()
    })
    expect(result.current.contextMenu).toBeNull()
  })
})
