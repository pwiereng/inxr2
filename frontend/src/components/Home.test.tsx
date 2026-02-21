import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { Home } from './Home'
import type { RepositoryStats } from '@/lib/api'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getRepositories: vi.fn(),
  getAllRepositoryStats: vi.fn(),
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

const mockStats: RepositoryStats[] = [
  {
    repository_id: 1,
    name: 'test-repo',
    total_files: 42,
    total_symbols: 150,
    total_references: 300,
    languages: { Python: 30, TypeScript: 12 },
    total_lines: 5000,
    total_references_resolved: 250,
    total_references_unresolved: 50,
    commit_date_earliest: '2024-01-01T00:00:00',
    commit_date_latest: '2024-06-15T00:00:00',
  },
  {
    repository_id: 2,
    name: 'another-repo',
    total_files: 10,
    total_symbols: 25,
    total_references: 40,
    languages: { JavaScript: 10 },
    total_lines: 1200,
    total_references_resolved: 40,
    total_references_unresolved: 0,
    commit_date_earliest: '2024-03-01T00:00:00',
    commit_date_latest: '2024-03-01T00:00:00',
  },
]

const renderWithRouter = (ui: React.ReactElement) => {
  return render(
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      {ui}
    </BrowserRouter>
  )
}

describe('Home', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockResolvedValue(mockRepositories)
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue(mockStats)
  })

  it('should render the home page with title', async () => {
    renderWithRouter(<Home />)

    // Wait for async data loading to complete to avoid act() warnings
    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

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

  it('should display stats on repository cards', async () => {
    renderWithRouter(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    // Check stats chips appear
    const statsContainers = screen.getAllByTestId('repo-stats')
    expect(statsContainers).toHaveLength(2)

    // Check specific stats values for test-repo
    expect(screen.getByText('5.0K lines')).toBeInTheDocument()
    expect(screen.getByText('42 files')).toBeInTheDocument()
    expect(screen.getByText('150 symbols')).toBeInTheDocument()
    // 250/300 = 83%
    expect(screen.getByText('83% resolved')).toBeInTheDocument()
    // Top languages shown
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('TypeScript')).toBeInTheDocument()
  })

  it('should display commit date range when available', async () => {
    renderWithRouter(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    // Check for date range text (format depends on locale, just check "Commits:" prefix exists)
    const commitTexts = screen.getAllByText(/^Commits:/)
    expect(commitTexts.length).toBeGreaterThanOrEqual(1)
  })

  it('should render cards gracefully when stats fetch fails', async () => {
    const api = await import('@/lib/api')
    vi.mocked(api.getAllRepositoryStats).mockRejectedValue(new Error('Stats failed'))

    renderWithRouter(<Home />)

    // Cards should still render without stats
    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
      expect(screen.getByText('another-repo')).toBeInTheDocument()
    })

    // Stats should not appear
    expect(screen.queryAllByTestId('repo-stats')).toHaveLength(0)
  })
})
