import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { CopyButton } from './CopyButton'

describe('CopyButton', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should render a copy icon button', () => {
    render(<CopyButton value="abc1234" />)
    expect(screen.getByLabelText('Copy')).toBeInTheDocument()
  })

  it('should copy value to clipboard on click', async () => {
    render(<CopyButton value="abc1234" />)

    // handleClick is async (awaits clipboard.writeText, then setCopied). Wrap in
    // an async act() so the post-await re-render is flushed inside act().
    await act(async () => {
      fireEvent.click(screen.getByLabelText('Copy'))
    })

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('abc1234')
  })

  it('should copy fullValue on shift+click', async () => {
    render(<CopyButton value="abc1234" fullValue="abc1234567890abcdef" />)

    await act(async () => {
      fireEvent.click(screen.getByLabelText('Copy'), { shiftKey: true })
    })

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('abc1234567890abcdef')
  })

  it('should copy short value on regular click even when fullValue is provided', async () => {
    render(<CopyButton value="abc1234" fullValue="abc1234567890abcdef" />)

    await act(async () => {
      fireEvent.click(screen.getByLabelText('Copy'))
    })

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('abc1234')
  })

  it('should show check icon after copying', async () => {
    render(<CopyButton value="abc1234" />)

    fireEvent.click(screen.getByLabelText('Copy'))

    await waitFor(() => {
      expect(screen.getByTestId('CheckIcon')).toBeInTheDocument()
    })
  })

  it('should revert to copy icon after timeout', async () => {
    vi.useFakeTimers()

    render(<CopyButton value="abc1234" />)

    fireEvent.click(screen.getByLabelText('Copy'))

    // Flush the clipboard promise microtask + the post-await setCopied re-render.
    // React 19 requires the state update that follows the awaited clipboard write
    // to be flushed inside act(); advanceTimersByTimeAsync alone no longer does it.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(screen.getByTestId('CheckIcon')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    expect(screen.getByTestId('ContentCopyIcon')).toBeInTheDocument()
  })

  it('should use custom tooltip text', () => {
    render(<CopyButton value="main" tooltip="Copy branch" />)
    expect(screen.getByLabelText('Copy branch')).toBeInTheDocument()
  })

  it('should stop event propagation on click', async () => {
    const parentClick = vi.fn()
    render(
      <div onClick={parentClick}>
        <CopyButton value="abc1234" />
      </div>
    )

    await act(async () => {
      fireEvent.click(screen.getByLabelText('Copy'))
    })

    expect(parentClick).not.toHaveBeenCalled()
  })
})
