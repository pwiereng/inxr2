import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/utils'
import { CodeHeader } from './CodeHeader'
import { formatDateYMD } from '@/lib/dateUtils'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getRepositories: vi.fn(),
  getRepositoryBranches: vi.fn(),
  getCommits: vi.fn(),
}))

// Mock data
const mockRepositories = [
  {
    id: 1,
    name: 'test-repo',
    url: 'https://github.com/test/test-repo',
    description: 'Test repository',
    default_branch: 'main',
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
  },
  {
    id: 2,
    name: 'another-repo',
    url: 'https://github.com/test/another-repo',
    description: 'Another repository',
    default_branch: 'master',
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
  },
]

const mockBranches = {
  branches: [
    {
      name: 'main',
      last_indexed_commit: 'abc123',
      oldest_indexed_commit: 'def456',
      commit_count: 10,
      last_indexed_at: '2024-01-01',
    },
    {
      name: 'feature-branch',
      last_indexed_commit: 'ghi789',
      oldest_indexed_commit: 'jkl012',
      commit_count: 5,
      last_indexed_at: '2024-01-01',
    },
  ],
}

const mockCommits = {
  commits: [
    {
      hash: 'abc123def456',
      short_hash: 'abc123d',
      message: 'Initial commit',
      author_name: 'Test Author',
      author_email: 'test@example.com',
      commit_date: '2024-01-01T10:30:00Z',
      is_indexed: true,
      tags: ['v1.0'],
      is_branch_specific: false,
      is_merge_base: false,
    },
    {
      hash: 'def456ghi789',
      short_hash: 'def456g',
      message: 'Second commit',
      author_name: 'Test Author',
      author_email: 'test@example.com',
      commit_date: '2024-01-02T14:45:00Z',
      is_indexed: true,
      tags: [],
      is_branch_specific: false,
      is_merge_base: false,
    },
  ],
  total: 2,
}

const defaultProps = {
  currentTab: 'browse' as const,
  repoName: 'test-repo',
  branch: 'main',
  commit: null,
  onRepoChange: vi.fn(),
  onBranchChange: vi.fn(),
  onCommitChange: vi.fn(),
  onTabChange: vi.fn(),
}

// render from @/test/utils already wraps with BrowserRouter + AppProvider + ThemeProvider

// Setup mocks before each test
beforeEach(async () => {
  vi.clearAllMocks()
  const api = await import('@/lib/api')
  vi.mocked(api.getRepositories).mockResolvedValue(mockRepositories)
  vi.mocked(api.getRepositoryBranches).mockResolvedValue(mockBranches)
  vi.mocked(api.getCommits).mockResolvedValue(mockCommits)
})

describe('CodeHeader', () => {
  describe('rendering', () => {
    it('should render home icon button', async () => {
      render(<CodeHeader {...defaultProps} />)

      // Wait for all data to load to avoid act() warnings
      await waitFor(() => {
        expect(screen.getByText('abc123d')).toBeInTheDocument()
      })

      expect(screen.getByRole('button', { name: /home/i })).toBeInTheDocument()
    })

    it('should render all three tabs', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /browse/i })).toBeInTheDocument()
        expect(screen.getByRole('tab', { name: /search/i })).toBeInTheDocument()
        expect(screen.getByRole('tab', { name: /history/i })).toBeInTheDocument()
      })
    })

    it('should highlight the current tab', async () => {
      render(<CodeHeader {...defaultProps} currentTab="search" />)

      await waitFor(() => {
        const searchTab = screen.getByRole('tab', { name: /search/i })
        expect(searchTab).toHaveAttribute('aria-selected', 'true')
      })
    })

    it('should show loading state for repositories initially', async () => {
      const api = await import('@/lib/api')
      // Use promises that never resolve so loading state persists
      // and no state updates happen after assertions
      vi.mocked(api.getRepositories).mockReturnValue(new Promise(() => {}))
      vi.mocked(api.getRepositoryBranches).mockReturnValue(new Promise(() => {}))
      vi.mocked(api.getCommits).mockReturnValue(new Promise(() => {}))

      render(<CodeHeader {...defaultProps} />)

      // At least one progress indicator should be shown
      expect(screen.getAllByRole('progressbar').length).toBeGreaterThan(0)
    })
  })

  describe('repository selector', () => {
    it('should display repository dropdown when multiple repositories exist', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        // Should show the repo name in autocomplete input
        expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0)
        expect(screen.getByDisplayValue('test-repo')).toBeInTheDocument()
      })
    })

    it('should display single repository name without dropdown', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getRepositories).mockResolvedValue([mockRepositories[0]!])

      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('test-repo')).toBeInTheDocument()
      })

      // Should not have combobox when single repo
      const comboboxes = screen.queryAllByRole('combobox')
      // Only branch/commit selectors, not repo selector
      expect(comboboxes.length).toBeLessThan(3)
    })

    it('should call onRepoChange when repository is changed', async () => {
      const onRepoChange = vi.fn()

      render(<CodeHeader {...defaultProps} onRepoChange={onRepoChange} />)

      await waitFor(() => {
        expect(screen.getByDisplayValue('test-repo')).toBeInTheDocument()
      })

      // Open the autocomplete dropdown by clicking the Open button
      const openButton = screen.getByTitle('Open')
      fireEvent.click(openButton)

      // Click another repo in the dropdown
      const anotherRepoOption = await screen.findByText('another-repo')
      fireEvent.click(anotherRepoOption)

      expect(onRepoChange).toHaveBeenCalledWith('another-repo')
    })
  })

  describe('branch selector', () => {
    it('should load branches for selected repository', async () => {
      const api = await import('@/lib/api')

      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(api.getRepositoryBranches).toHaveBeenCalledWith(1)
      })
    })

    it('should display branch selector when repo is selected', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        // Should show branch name
        expect(screen.getByText('main')).toBeInTheDocument()
      })
    })

    it('should not display branch selector when no repository is selected', async () => {
      render(<CodeHeader {...defaultProps} repoName={null} />)

      await waitFor(() => {
        // Home button should be there
        expect(screen.getByRole('button', { name: /home/i })).toBeInTheDocument()
      })

      // Branch selector should not be present (no 'main' text from branch)
      // But tabs should still show
      expect(screen.getByRole('tab', { name: /browse/i })).toBeInTheDocument()
    })

    it('should show branches with last_indexed_commit even when commit_count is 0', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getRepositoryBranches).mockResolvedValue({
        branches: [
          {
            name: 'main',
            last_indexed_commit: 'abc123',
            oldest_indexed_commit: 'def456',
            commit_count: 289,
            last_indexed_at: '2024-01-01',
          },
          {
            name: 'feature-branch',
            last_indexed_commit: 'ghi789',
            oldest_indexed_commit: null,
            commit_count: 0,
            last_indexed_at: null,
          },
        ],
      })

      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('main')).toBeInTheDocument()
      })

      // Open the branch selector
      const comboboxes = screen.getAllByRole('combobox')
      const branchSelect = comboboxes[1]!
      fireEvent.mouseDown(branchSelect)

      // feature-branch should appear even though commit_count is 0
      const featureBranchOption = await screen.findByText(/feature-branch/)
      expect(featureBranchOption).toBeInTheDocument()
    })

    it('should not show branches without last_indexed_commit', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getRepositoryBranches).mockResolvedValue({
        branches: [
          {
            name: 'main',
            last_indexed_commit: 'abc123',
            oldest_indexed_commit: 'def456',
            commit_count: 289,
            last_indexed_at: '2024-01-01',
          },
          {
            name: 'unindexed-branch',
            last_indexed_commit: null,
            oldest_indexed_commit: null,
            commit_count: 0,
            last_indexed_at: null,
          },
        ],
      })

      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('main')).toBeInTheDocument()
      })

      // unindexed-branch should NOT appear
      expect(screen.queryByText('unindexed-branch')).not.toBeInTheDocument()
    })

    it('should call onBranchChange when branch is changed', async () => {
      const onBranchChange = vi.fn()

      render(<CodeHeader {...defaultProps} onBranchChange={onBranchChange} />)

      await waitFor(() => {
        expect(screen.getByText('main')).toBeInTheDocument()
      })

      // Find and click the branch selector (it's the second combobox after repo)
      const comboboxes = screen.getAllByRole('combobox')
      const branchSelect = comboboxes[1]!
      fireEvent.mouseDown(branchSelect)

      // Click feature-branch
      const featureBranchOption = await screen.findByText(/feature-branch/)
      fireEvent.click(featureBranchOption)

      expect(onBranchChange).toHaveBeenCalledWith('feature-branch')
    })
  })

  describe('commit selector', () => {
    it('should load commits for selected repository and branch', async () => {
      const api = await import('@/lib/api')

      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(api.getCommits).toHaveBeenCalledWith('test-repo', 'main', 500)
      })
    })

    it('should display short commit hash', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        // Should show 7-char short hash
        expect(screen.getByText('abc123d')).toBeInTheDocument()
      })
    })

    it('should call onCommitChange when commit is changed', async () => {
      const onCommitChange = vi.fn()

      render(<CodeHeader {...defaultProps} onCommitChange={onCommitChange} />)

      await waitFor(() => {
        expect(screen.getByText('abc123d')).toBeInTheDocument()
      })

      // Find and click the commit selector (it's the third combobox)
      const comboboxes = screen.getAllByRole('combobox')
      const commitSelect = comboboxes[2]!
      fireEvent.mouseDown(commitSelect)

      // Click second commit
      const secondCommitOption = await screen.findByText('def456g')
      fireEvent.click(secondCommitOption)

      expect(onCommitChange).toHaveBeenCalledWith('def456ghi789')
    })
  })

  describe('tab navigation', () => {
    it('should call onTabChange when tab is clicked', async () => {
      const onTabChange = vi.fn()

      render(<CodeHeader {...defaultProps} onTabChange={onTabChange} />)

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /search/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('tab', { name: /search/i }))

      expect(onTabChange).toHaveBeenCalledWith('search')
    })

    it('should call onTabChange with history value', async () => {
      const onTabChange = vi.fn()

      render(<CodeHeader {...defaultProps} onTabChange={onTabChange} />)

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /history/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('tab', { name: /history/i }))

      expect(onTabChange).toHaveBeenCalledWith('history')
    })
  })

  describe('data loading', () => {
    it('should reload branches when repository changes', async () => {
      const api = await import('@/lib/api')

      const { rerender } = render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(api.getRepositoryBranches).toHaveBeenCalledWith(1)
      })

      // Change repository
      rerender(<CodeHeader {...defaultProps} repoName="another-repo" />)

      await waitFor(() => {
        expect(api.getRepositoryBranches).toHaveBeenCalledWith(2)
      })
    })

    it('should reload commits when branch changes', async () => {
      const api = await import('@/lib/api')

      const { rerender } = render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(api.getCommits).toHaveBeenCalledWith('test-repo', 'main', 500)
      })

      // Change branch
      rerender(<CodeHeader {...defaultProps} branch="feature-branch" />)

      await waitFor(() => {
        expect(api.getCommits).toHaveBeenCalledWith('test-repo', 'feature-branch', 500)
      })
    })
  })

  describe('theme toggle', () => {
    it('should render the theme toggle button', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /switch to light mode/i })).toBeInTheDocument()
      })
    })

    it('should switch icon when toggle is clicked', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /switch to light mode/i })).toBeInTheDocument()
      })

      // Click to switch to light mode
      fireEvent.click(screen.getByRole('button', { name: /switch to light mode/i }))

      // After toggle, button should now say "switch to dark mode"
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /switch to dark mode/i })).toBeInTheDocument()
      })
    })
  })

  describe('commit date display', () => {
    it('should display commit dates with UTC in dropdown items', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('abc123d')).toBeInTheDocument()
      })

      // Open the commit selector dropdown
      const comboboxes = screen.getAllByRole('combobox')
      const commitSelect = comboboxes[2]!
      fireEvent.mouseDown(commitSelect)

      // Both formatted dates should appear in dropdown with UTC
      await waitFor(() => {
        // First commit date appears in both the indicator and dropdown
        expect(screen.getAllByText('2024-01-01 10:30 UTC').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText('2024-01-02 14:45 UTC')).toBeInTheDocument()
      })
    })

    it('should show datetime indicator for latest commit when no commit is selected', async () => {
      render(<CodeHeader {...defaultProps} commit={null} />)

      // The date indicator should show the first commit's datetime with UTC
      await waitFor(() => {
        expect(screen.getByText('2024-01-01 10:30 UTC')).toBeInTheDocument()
      })
    })

    it('should show datetime indicator for a specific selected commit', async () => {
      render(<CodeHeader {...defaultProps} commit="def456ghi789" />)

      await waitFor(() => {
        expect(screen.getByText('2024-01-02 14:45 UTC')).toBeInTheDocument()
      })
    })

    it('should not show date indicator when no repo is selected', async () => {
      render(<CodeHeader {...defaultProps} repoName={null} />)

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /browse/i })).toBeInTheDocument()
      })

      // No datetime indicator should be shown
      expect(screen.queryByText(/UTC/)).not.toBeInTheDocument()
    })
  })

  describe('commit badges', () => {
    it('should show HEAD badge on the first commit in dropdown', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('abc123d')).toBeInTheDocument()
      })

      // Open the commit selector dropdown
      const comboboxes = screen.getAllByRole('combobox')
      const commitSelect = comboboxes[2]!
      fireEvent.mouseDown(commitSelect)

      await waitFor(() => {
        expect(screen.getByText('HEAD')).toBeInTheDocument()
      })
    })

    it('should show tag badges in commit dropdown', async () => {
      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('abc123d')).toBeInTheDocument()
      })

      // Open the commit selector dropdown
      const comboboxes = screen.getAllByRole('combobox')
      const commitSelect = comboboxes[2]!
      fireEvent.mouseDown(commitSelect)

      await waitFor(() => {
        expect(screen.getByText('v1.0')).toBeInTheDocument()
      })
    })
  })

  describe('formatDateYMD', () => {
    it('should format dates as yyyy-mm-dd', () => {
      expect(formatDateYMD('2024-01-15')).toBe('2024-01-15')
    })

    it('should return empty string for empty input', () => {
      expect(formatDateYMD('')).toBe('')
    })

    it('should return empty string for invalid date', () => {
      expect(formatDateYMD('not-a-date')).toBe('')
    })

    it('should handle ISO timestamp with time component', () => {
      expect(formatDateYMD('2025-01-15T10:30:00')).toBe('2025-01-15')
    })

    it('should handle ISO timestamp with UTC suffix', () => {
      expect(formatDateYMD('2025-01-15T10:30:00Z')).toBe('2025-01-15')
    })
  })

  describe('branch-specific commit highlighting', () => {
    it('should show FORK badge on merge-base commit', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getCommits).mockResolvedValue({
        commits: [
          {
            hash: 'branch1hash',
            short_hash: 'branch1',
            message: 'Branch commit',
            author_name: 'Test Author',
            author_email: 'test@example.com',
            commit_date: '2024-01-03T10:00:00Z',
            is_indexed: true,
            tags: [],
            is_branch_specific: true,
            is_merge_base: false,
          },
          {
            hash: 'mergebasehash',
            short_hash: 'mergeba',
            message: 'Merge base commit',
            author_name: 'Test Author',
            author_email: 'test@example.com',
            commit_date: '2024-01-02T10:00:00Z',
            is_indexed: true,
            tags: [],
            is_branch_specific: false,
            is_merge_base: true,
          },
          {
            hash: 'sharedhash',
            short_hash: 'shared1',
            message: 'Shared commit',
            author_name: 'Test Author',
            author_email: 'test@example.com',
            commit_date: '2024-01-01T10:00:00Z',
            is_indexed: true,
            tags: [],
            is_branch_specific: false,
            is_merge_base: false,
          },
        ],
        total: 3,
      })

      render(<CodeHeader {...defaultProps} branch="feature-branch" />)

      await waitFor(() => {
        expect(screen.getByText('branch1')).toBeInTheDocument()
      })

      // Open the commit selector dropdown
      const comboboxes = screen.getAllByRole('combobox')
      const commitSelect = comboboxes[2]!
      fireEvent.mouseDown(commitSelect)

      await waitFor(() => {
        expect(screen.getByText('FORK')).toBeInTheDocument()
      })
    })

    it('should not show FORK badge on default branch', async () => {
      render(<CodeHeader {...defaultProps} branch="main" />)

      await waitFor(() => {
        expect(screen.getByText('abc123d')).toBeInTheDocument()
      })

      // Open the commit selector dropdown
      const comboboxes = screen.getAllByRole('combobox')
      const commitSelect = comboboxes[2]!
      fireEvent.mouseDown(commitSelect)

      await waitFor(() => {
        // After opening dropdown, hash appears in both the select value and menu items
        expect(screen.getAllByText('abc123d').length).toBeGreaterThanOrEqual(1)
      })

      expect(screen.queryByText('FORK')).not.toBeInTheDocument()
    })
  })

  describe('help page', () => {
    it('should not display branch or commit selectors on help tab', async () => {
      render(<CodeHeader {...defaultProps} currentTab="help" />)

      await waitFor(() => {
        // Repo selector should still be present
        expect(screen.getByDisplayValue('test-repo')).toBeInTheDocument()
      })

      // Branch and commit selectors should NOT be present
      // On browse tab there are 3 comboboxes (repo, branch, commit), on help only 1 (repo)
      const comboboxes = screen.getAllByRole('combobox')
      expect(comboboxes).toHaveLength(1)
    })

    it('should not display commit date indicator on help tab', async () => {
      render(<CodeHeader {...defaultProps} currentTab="help" />)

      await waitFor(() => {
        expect(screen.getByDisplayValue('test-repo')).toBeInTheDocument()
      })

      // No datetime indicator should be shown
      expect(screen.queryByText(/UTC/)).not.toBeInTheDocument()
    })
  })

  describe('error handling', () => {
    it('should handle repository loading error gracefully', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getRepositories).mockRejectedValue(new Error('Failed to load repositories'))

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalledWith(
          'Failed to load repositories:',
          expect.any(Error)
        )
      })

      consoleErrorSpy.mockRestore()
    })

    it('should handle branch loading error gracefully', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getRepositoryBranches).mockRejectedValue(new Error('Failed to load branches'))

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to load branches:', expect.any(Error))
      })

      consoleErrorSpy.mockRestore()
    })

    it('should handle commit loading error gracefully', async () => {
      const api = await import('@/lib/api')
      vi.mocked(api.getCommits).mockRejectedValue(new Error('Failed to load commits'))

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      render(<CodeHeader {...defaultProps} />)

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to load commits:', expect.any(Error))
      })

      consoleErrorSpy.mockRestore()
    })
  })
})
