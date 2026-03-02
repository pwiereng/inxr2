import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { render } from '@/test/utils'
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
  {
    id: 3,
    name: 'demo-project',
    url: 'https://github.com/test/demo-project',
    description: 'A demo project',
    default_branch: 'main',
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
    last_indexed_at: '2024-06-15T00:00:00',
    last_indexed_commit: 'abc123',
    last_indexing_duration_seconds: 45.3,
    last_resolving_duration_seconds: 12.7,
    git_head_commit: 'abc123',
    is_stale: false,
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
    last_indexed_at: '2024-03-01T00:00:00',
    last_indexed_commit: 'def456',
    last_indexing_duration_seconds: 10.0,
    last_resolving_duration_seconds: 3.5,
    git_head_commit: 'def456',
    is_stale: false,
  },
  {
    repository_id: 3,
    name: 'demo-project',
    total_files: 5,
    total_symbols: 10,
    total_references: 0,
    languages: { Rust: 5 },
    total_lines: 200,
    total_references_resolved: 0,
    total_references_unresolved: 0,
    commit_date_earliest: '2024-02-01T00:00:00',
    commit_date_latest: '2024-02-01T00:00:00',
    last_indexed_at: '2024-02-01T00:00:00',
    last_indexed_commit: 'ghi789',
    last_indexing_duration_seconds: null,
    last_resolving_duration_seconds: null,
    git_head_commit: 'ghi789',
    is_stale: false,
  },
]

describe('Home', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    localStorage.clear()
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockResolvedValue(mockRepositories)
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue(mockStats)
  })

  it('should render the home page with title', async () => {
    render(<Home />)

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

    render(<Home />)

    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('should display repositories when loaded', async () => {
    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
      expect(screen.getByText('another-repo')).toBeInTheDocument()
      expect(screen.getByText('demo-project')).toBeInTheDocument()
    })
  })

  it('should display repository description when available', async () => {
    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('A test repository')).toBeInTheDocument()
    })
  })

  it('should navigate to browse when clicking a repository in grid view', async () => {
    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    const repoCard = screen.getByText('test-repo').closest('button')
    if (repoCard) {
      fireEvent.click(repoCard)
    }

    expect(mockNavigate).toHaveBeenCalledWith('/browse/test-repo?branch=main')
  })

  it('should navigate to browse when clicking a repository in list view', async () => {
    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    // Switch to list view
    fireEvent.click(screen.getByLabelText('Switch to list view'))

    const repoRow = screen.getByText('test-repo').closest('[role="button"]')
    expect(repoRow).not.toBeNull()
    fireEvent.click(repoRow!)

    expect(mockNavigate).toHaveBeenCalledWith('/browse/test-repo?branch=main')
  })

  it('should show message when no repositories are indexed', async () => {
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockResolvedValue([])

    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText(/No repositories indexed yet/i)).toBeInTheDocument()
    })
  })

  it('should show error message when API fails', async () => {
    const api = await import('@/lib/api')
    vi.mocked(api.getRepositories).mockRejectedValue(new Error('API Error'))

    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeInTheDocument()
    })
  })

  it('should display stats in grid view', async () => {
    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    const statsContainers = screen.getAllByTestId('repo-stats')
    expect(statsContainers).toHaveLength(3)

    expect(screen.getByText('5.0K lines')).toBeInTheDocument()
    expect(screen.getByText('42 files')).toBeInTheDocument()
    expect(screen.getByText('150 symbols')).toBeInTheDocument()
    expect(screen.getByText('83% resolved')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('TypeScript')).toBeInTheDocument()
  })

  it('should display stats in list view', async () => {
    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByLabelText('Switch to list view'))

    const statsContainers = screen.getAllByTestId('repo-stats')
    expect(statsContainers).toHaveLength(3)

    expect(screen.getByText('42 files')).toBeInTheDocument()
    expect(screen.getByText('150 symbols')).toBeInTheDocument()
    expect(screen.getByText('83% resolved')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
  })

  it('should display commit date range in grid view', async () => {
    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    const commitTexts = screen.getAllByText(/^Commits:/)
    expect(commitTexts.length).toBeGreaterThanOrEqual(1)
  })

  it('should render gracefully when stats fetch fails', async () => {
    const api = await import('@/lib/api')
    vi.mocked(api.getAllRepositoryStats).mockRejectedValue(new Error('Stats failed'))

    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
      expect(screen.getByText('another-repo')).toBeInTheDocument()
    })

    expect(screen.queryAllByTestId('repo-stats')).toHaveLength(0)
  })

  it('should show stale indicator when is_stale is true', async () => {
    const api = await import('@/lib/api')
    const staleStats: RepositoryStats[] = mockStats.map((s) =>
      s.repository_id === 1
        ? {
            ...s,
            is_stale: true,
            git_head_commit: 'new999',
            last_indexed_at: '2024-06-15T00:00:00',
          }
        : s
    )
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue(staleStats)

    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('Index outdated')).toBeInTheDocument()
    })
  })

  it('should not show stale indicator when is_stale is false', async () => {
    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    expect(screen.queryByText('Index outdated')).not.toBeInTheDocument()
  })

  describe('view mode toggle', () => {
    it('should default to grid view', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      // Grid view shows the list view toggle icon
      expect(screen.getByLabelText('Switch to list view')).toBeInTheDocument()
    })

    it('should toggle between grid and list views', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      // Initially grid — toggle button says "Switch to list view"
      const toggleBtn = screen.getByLabelText('Switch to list view')
      fireEvent.click(toggleBtn)

      // Now in list view — toggle button says "Switch to grid view"
      expect(screen.getByLabelText('Switch to grid view')).toBeInTheDocument()

      // Toggle back
      fireEvent.click(screen.getByLabelText('Switch to grid view'))
      expect(screen.getByLabelText('Switch to list view')).toBeInTheDocument()
    })

    it('should persist view mode in localStorage', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByLabelText('Switch to list view'))
      expect(localStorage.getItem('inxr2-home-view-mode')).toBe('list')

      fireEvent.click(screen.getByLabelText('Switch to grid view'))
      expect(localStorage.getItem('inxr2-home-view-mode')).toBe('grid')
    })

    it('should restore view mode from localStorage', async () => {
      localStorage.setItem('inxr2-home-view-mode', 'list')

      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      // Should start in list view
      expect(screen.getByLabelText('Switch to grid view')).toBeInTheDocument()
    })

    it('should not show toggle when no repos exist', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getRepositories).mockResolvedValue([])

      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText(/No repositories indexed yet/i)).toBeInTheDocument()
      })

      expect(screen.queryByLabelText('Switch to list view')).not.toBeInTheDocument()
      expect(screen.queryByLabelText('Switch to grid view')).not.toBeInTheDocument()
    })
  })

  describe('filter', () => {
    it('should render filter input', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      expect(screen.getByPlaceholderText('Filter repositories...')).toBeInTheDocument()
    })

    it('should filter repositories by name as user types', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Filter repositories...')
      fireEvent.change(input, { target: { value: 'test' } })

      expect(screen.getByText('test-repo')).toBeInTheDocument()
      expect(screen.queryByText('another-repo')).not.toBeInTheDocument()
      expect(screen.queryByText('demo-project')).not.toBeInTheDocument()
    })

    it('should filter case-insensitively', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Filter repositories...')
      fireEvent.change(input, { target: { value: 'TEST' } })

      expect(screen.getByText('test-repo')).toBeInTheDocument()
    })

    it('should show all repos when filter is cleared', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Filter repositories...')
      fireEvent.change(input, { target: { value: 'test' } })
      expect(screen.queryByText('another-repo')).not.toBeInTheDocument()

      fireEvent.change(input, { target: { value: '' } })
      expect(screen.getByText('test-repo')).toBeInTheDocument()
      expect(screen.getByText('another-repo')).toBeInTheDocument()
      expect(screen.getByText('demo-project')).toBeInTheDocument()
    })

    it('should show "no match" message when filter matches nothing', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Filter repositories...')
      fireEvent.change(input, { target: { value: 'zzz-no-match' } })

      expect(screen.getByText(/No repositories match/)).toBeInTheDocument()
    })

    it('should show filtered count', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      expect(screen.getByText('3 repositories')).toBeInTheDocument()

      const input = screen.getByPlaceholderText('Filter repositories...')
      fireEvent.change(input, { target: { value: 'repo' } })

      expect(screen.getByText('Showing 2 of 3 repositories')).toBeInTheDocument()
    })

    it('should not show filter when no repos exist', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getRepositories).mockResolvedValue([])

      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText(/No repositories indexed yet/i)).toBeInTheDocument()
      })

      expect(screen.queryByPlaceholderText('Filter repositories...')).not.toBeInTheDocument()
    })

    it('should filter in list view too', async () => {
      render(<Home />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByLabelText('Switch to list view'))

      const input = screen.getByPlaceholderText('Filter repositories...')
      fireEvent.change(input, { target: { value: 'demo' } })

      expect(screen.getByText('demo-project')).toBeInTheDocument()
      expect(screen.queryByText('test-repo')).not.toBeInTheDocument()
      expect(screen.queryByText('another-repo')).not.toBeInTheDocument()
    })
  })
})
