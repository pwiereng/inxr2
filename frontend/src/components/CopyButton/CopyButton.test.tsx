import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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

  it('should render a copy icon button', () => {
    render(<CopyButton value="abc1234" />)
    expect(screen.getByLabelText('Copy')).toBeInTheDocument()
  })

  it('should copy value to clipboard on click', async () => {
    render(<CopyButton value="abc1234" />)

    fireEvent.click(screen.getByLabelText('Copy'))

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('abc1234')
  })

  it('should copy fullValue on shift+click', async () => {
    render(<CopyButton value="abc1234" fullValue="abc1234567890abcdef" />)

    fireEvent.click(screen.getByLabelText('Copy'), { shiftKey: true })

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('abc1234567890abcdef')
  })

  it('should copy short value on regular click even when fullValue is provided', async () => {
    render(<CopyButton value="abc1234" fullValue="abc1234567890abcdef" />)

    fireEvent.click(screen.getByLabelText('Copy'))

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

    // Flush the clipboard promise microtask
    await vi.advanceTimersByTimeAsync(0)

    expect(screen.getByTestId('CheckIcon')).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(1500)

    expect(screen.getByTestId('ContentCopyIcon')).toBeInTheDocument()

    vi.useRealTimers()
  })

  it('should use custom tooltip text', () => {
    render(<CopyButton value="main" tooltip="Copy branch" />)
    expect(screen.getByLabelText('Copy branch')).toBeInTheDocument()
  })

  it('should stop event propagation on click', () => {
    const parentClick = vi.fn()
    render(
      <div onClick={parentClick}>
        <CopyButton value="abc1234" />
      </div>
    )

    fireEvent.click(screen.getByLabelText('Copy'))

    expect(parentClick).not.toHaveBeenCalled()
  })
})
