import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import { ErrorBoundary } from './ErrorBoundary'

// Suppress console.error from ErrorBoundary.componentDidCatch during tests
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

function ProblemChild({ shouldThrow = true }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error message')
  }
  return <div>Child rendered successfully</div>
}

describe('ErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={false} />
      </ErrorBoundary>
    )

    expect(screen.getByText('Child rendered successfully')).toBeInTheDocument()
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
  })

  it('shows fallback UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <ProblemChild />
      </ErrorBoundary>
    )

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
    expect(screen.queryByText('Child rendered successfully')).not.toBeInTheDocument()
  })

  it('resets error state when Try Again is clicked', () => {
    let shouldThrow = true

    function ToggleChild() {
      if (shouldThrow) {
        throw new Error('Temporary error')
      }
      return <div>Recovered</div>
    }

    render(
      <ErrorBoundary>
        <ToggleChild />
      </ErrorBoundary>
    )

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()

    // Fix the child before resetting
    shouldThrow = false
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))

    expect(screen.getByText('Recovered')).toBeInTheDocument()
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
  })

  it('shows error details when Show Details is clicked', () => {
    render(
      <ErrorBoundary>
        <ProblemChild />
      </ErrorBoundary>
    )

    const hiddenDetails = screen.queryByText(/Test error message/)
    expect(hiddenDetails).toBeInTheDocument()
    expect(hiddenDetails).not.toBeVisible()

    fireEvent.click(screen.getByRole('button', { name: /show details/i }))

    const visibleDetails = screen.queryByText(/Test error message/)
    expect(visibleDetails).toBeInTheDocument()
    expect(visibleDetails).toBeVisible()
  })

  it('toggles details button text between Show and Hide', () => {
    render(
      <ErrorBoundary>
        <ProblemChild />
      </ErrorBoundary>
    )

    const detailsButton = screen.getByRole('button', { name: /show details/i })
    expect(detailsButton).toHaveTextContent('Show Details')

    fireEvent.click(detailsButton)
    expect(screen.getByRole('button', { name: /hide details/i })).toHaveTextContent('Hide Details')

    fireEvent.click(screen.getByRole('button', { name: /hide details/i }))
    expect(screen.getByRole('button', { name: /show details/i })).toHaveTextContent('Show Details')
  })
})
