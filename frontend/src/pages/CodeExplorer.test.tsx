import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CodeExplorer from './CodeExplorer'
import * as api from '@/lib/api'

vi.mock('@/lib/api')

// Mock Browse and Search components to avoid complex setup
vi.mock('./Browse', () => ({
  default: ({ noAppBar, repoName }: { noAppBar?: boolean; repoName?: string }) => (
    <div data-testid="browse-component" data-no-app-bar={noAppBar} data-repo-name={repoName}>
      Browse Component
    </div>
  ),
}))

vi.mock('./Search', () => ({
  default: ({ noAppBar, repoName }: { noAppBar?: boolean; repoName?: string }) => (
    <div data-testid="search-component" data-no-app-bar={noAppBar} data-repo-name={repoName}>
      Search Component
    </div>
  ),
}))

describe('CodeExplorer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render tabs for Browse, Search, and History', async () => {
    vi.mocked(api.getRepositories).mockResolvedValue([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: null,
        default_branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
      },
    ])

    render(
      <MemoryRouter initialEntries={['/code']}>
        <CodeExplorer />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Browse/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /Search/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /History/i })).toBeInTheDocument()
    })
  })

  it('should switch tabs when clicked', async () => {
    const user = userEvent.setup()

    vi.mocked(api.getRepositories).mockResolvedValue([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: null,
        default_branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
      },
    ])

    render(
      <MemoryRouter initialEntries={['/code?tab=browse']}>
        <CodeExplorer />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Browse/i })).toHaveAttribute('aria-selected', 'true')
    })

    // Click Search tab
    const searchTab = screen.getByRole('tab', { name: /Search/i })
    await user.click(searchTab)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Search/i })).toHaveAttribute('aria-selected', 'true')
    })
  })

  it('should show repository selector when multiple repositories exist', async () => {
    vi.mocked(api.getRepositories).mockResolvedValue([
      {
        id: 1,
        name: 'repo-1',
        url: 'https://github.com/test/repo1',
        description: null,
        default_branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
      },
      {
        id: 2,
        name: 'repo-2',
        url: 'https://github.com/test/repo2',
        description: null,
        default_branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
      },
    ])

    render(
      <MemoryRouter initialEntries={['/code']}>
        <CodeExplorer />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })
  })

  it('should respect tab parameter from URL', async () => {
    vi.mocked(api.getRepositories).mockResolvedValue([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: null,
        default_branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
      },
    ])

    render(
      <MemoryRouter initialEntries={['/code?tab=search']}>
        <CodeExplorer />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Search/i })).toHaveAttribute('aria-selected', 'true')
    })
  })

  it('should pass repoName to Search component', async () => {
    vi.mocked(api.getRepositories).mockResolvedValue([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: null,
        default_branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
      },
    ])

    render(
      <MemoryRouter initialEntries={['/code?tab=search&repo=test-repo']}>
        <CodeExplorer />
      </MemoryRouter>
    )

    await waitFor(() => {
      const searchComponent = screen.getByTestId('search-component')
      expect(searchComponent).toHaveAttribute('data-repo-name', 'test-repo')
    })
  })

  it('should pass repoName to Browse component', async () => {
    vi.mocked(api.getRepositories).mockResolvedValue([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: null,
        default_branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
      },
    ])

    render(
      <MemoryRouter initialEntries={['/code?tab=browse&repo=test-repo']}>
        <CodeExplorer />
      </MemoryRouter>
    )

    await waitFor(() => {
      const browseComponent = screen.getByTestId('browse-component')
      expect(browseComponent).toHaveAttribute('data-repo-name', 'test-repo')
    })
  })
})
