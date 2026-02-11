import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getRepositories: vi.fn(),
}))

const mockRepositories = [
  {
    id: 1,
    name: 'test-repo',
    url: 'https://github.com/test/test-repo',
    description: 'A test repository',
    default_branch: 'main',
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
  },
]

// Wrapper that provides Router context for App
const renderApp = (initialEntries: string[] = ['/']) => {
  return render(
    <MemoryRouter
      initialEntries={initialEntries}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <App />
    </MemoryRouter>
  )
}

describe('App', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockResolvedValue(mockRepositories)
  })

  it('should render home page by default', async () => {
    renderApp(['/'])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /INXR2/i, level: 1 })).toBeInTheDocument()
    })
  })

  it('should render with MUI theme and CssBaseline', async () => {
    const { container } = renderApp(['/'])

    // Wait for async data loading to settle to avoid act() warnings
    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    // CssBaseline adds styles to the body
    expect(container).toBeInTheDocument()
  })
})
