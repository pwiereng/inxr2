import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSelectionToolbar } from './useSelectionToolbar'

describe('useSelectionToolbar', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should start with toolbar as null', () => {
    const { result } = renderHook(() => useSelectionToolbar())
    expect(result.current.toolbar).toBeNull()
  })

  it('should provide a containerRef', () => {
    const { result } = renderHook(() => useSelectionToolbar())
    expect(result.current.containerRef).toBeDefined()
    expect(result.current.containerRef.current).toBeNull()
  })

  it('should clear toolbar on handleClose', () => {
    const { result } = renderHook(() => useSelectionToolbar())
    act(() => {
      result.current.handleClose()
    })
    expect(result.current.toolbar).toBeNull()
  })
})
