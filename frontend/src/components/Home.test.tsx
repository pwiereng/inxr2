import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { Home } from './Home'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getRepositories: vi.fn(),
}))

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

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
  {
    id: 2,
    name: 'another-repo',
    url: 'https://github.com/test/another-repo',
    description: null,
    default_branch: 'master',
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
  },
]

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

describe('Home', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockResolvedValue(mockRepositories)
  })

  it('should render the home page with title', async () => {
    renderWithRouter(<Home />)

    expect(screen.getByRole('heading', { name: /INXR2/i, level: 1 })).toBeInTheDocument()
    expect(screen.getByText(/Cross-Reference Code Browser/i)).toBeInTheDocument()
  })

  it('should show loading state initially', async () => {
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockRepositories), 1000))
    )

    renderWithRouter(<Home />)

    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('should display repository cards when loaded', async () => {
    renderWithRouter(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
      expect(screen.getByText('another-repo')).toBeInTheDocument()
    })
  })

  it('should display repository description when available', async () => {
    renderWithRouter(<Home />)

    await waitFor(() => {
      expect(screen.getByText('A test repository')).toBeInTheDocument()
    })
  })

  it('should navigate to browse when clicking a repository card', async () => {
    renderWithRouter(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    const repoCard = screen.getByText('test-repo').closest('button')
    if (repoCard) {
      fireEvent.click(repoCard)
    }

    expect(mockNavigate).toHaveBeenCalledWith('/browse/test-repo?branch=main')
  })

  it('should show message when no repositories are indexed', async () => {
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockResolvedValue([])

    renderWithRouter(<Home />)

    await waitFor(() => {
      expect(screen.getByText(/No repositories indexed yet/i)).toBeInTheDocument()
    })
  })

  it('should show error message when API fails', async () => {
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockRejectedValue(new Error('API Error'))

    renderWithRouter(<Home />)

    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeInTheDocument()
    })
  })
})
