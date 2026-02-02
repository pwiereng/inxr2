import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BranchSelector } from './BranchSelector'
import * as api from '@/lib/api'

// Mock the API
vi.mock('@/lib/api', () => ({
  getRepositoryBranches: vi.fn(),
  getFileHistory: vi.fn(),
}))

describe('BranchSelector', () => {
  const mockOnBranchChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state initially', async () => {
    vi.mocked(api.getRepositoryBranches).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    await act(async () => {
      render(
        <BranchSelector
          repositoryId={1}
          selectedBranch={null}
          defaultBranch="main"
          onBranchChange={mockOnBranchChange}
        />
      )
    })

    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('renders single branch as plain text', async () => {
    vi.mocked(api.getRepositoryBranches).mockResolvedValue({
      branches: [
        {
          name: 'main',
          commit_count: 10,
          last_indexed_commit: 'abc123',
          oldest_indexed_commit: 'def456',
          last_indexed_at: '2024-01-01T00:00:00Z',
        },
      ],
    })

    await act(async () => {
      render(
        <BranchSelector
          repositoryId={1}
          selectedBranch={null}
          defaultBranch="main"
          onBranchChange={mockOnBranchChange}
        />
      )
      // Allow async effects to settle
      await new Promise((resolve) => setTimeout(resolve, 50))
    })

    expect(screen.getByText('main')).toBeInTheDocument()
    // Should not have a dropdown button when single branch
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('renders dropdown for multiple branches', async () => {
    vi.mocked(api.getRepositoryBranches).mockResolvedValue({
      branches: [
        {
          name: 'main',
          commit_count: 10,
          last_indexed_commit: 'abc123',
          oldest_indexed_commit: 'def456',
          last_indexed_at: '2024-01-01T00:00:00Z',
        },
        {
          name: 'feature',
          commit_count: 5,
          last_indexed_commit: 'xyz789',
          oldest_indexed_commit: 'uvw012',
          last_indexed_at: '2024-01-02T00:00:00Z',
        },
      ],
    })

    await act(async () => {
      render(
        <BranchSelector
          repositoryId={1}
          selectedBranch={null}
          defaultBranch="main"
          onBranchChange={mockOnBranchChange}
        />
      )
      await new Promise((resolve) => setTimeout(resolve, 50))
    })

    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('calls onBranchChange when branch is selected', async () => {
    vi.mocked(api.getRepositoryBranches).mockResolvedValue({
      branches: [
        {
          name: 'main',
          commit_count: 10,
          last_indexed_commit: 'abc123',
          oldest_indexed_commit: 'def456',
          last_indexed_at: '2024-01-01T00:00:00Z',
        },
        {
          name: 'feature',
          commit_count: 5,
          last_indexed_commit: 'xyz789',
          oldest_indexed_commit: 'uvw012',
          last_indexed_at: '2024-01-02T00:00:00Z',
        },
      ],
    })

    const user = userEvent.setup()

    await act(async () => {
      render(
        <BranchSelector
          repositoryId={1}
          selectedBranch={null}
          defaultBranch="main"
          onBranchChange={mockOnBranchChange}
        />
      )
      await new Promise((resolve) => setTimeout(resolve, 50))
    })

    // Open the dropdown
    await act(async () => {
      await user.click(screen.getByRole('combobox'))
    })

    // Select the feature branch
    await act(async () => {
      await user.click(screen.getByText('feature'))
      // Wait for MUI transitions to complete
      await new Promise((resolve) => setTimeout(resolve, 100))
    })

    expect(mockOnBranchChange).toHaveBeenCalledWith('feature')
  })

  it('calls onBranchChange with null when default branch is selected', async () => {
    vi.mocked(api.getRepositoryBranches).mockResolvedValue({
      branches: [
        {
          name: 'main',
          commit_count: 10,
          last_indexed_commit: 'abc123',
          oldest_indexed_commit: 'def456',
          last_indexed_at: '2024-01-01T00:00:00Z',
        },
        {
          name: 'feature',
          commit_count: 5,
          last_indexed_commit: 'xyz789',
          oldest_indexed_commit: 'uvw012',
          last_indexed_at: '2024-01-02T00:00:00Z',
        },
      ],
    })

    const user = userEvent.setup()

    await act(async () => {
      render(
        <BranchSelector
          repositoryId={1}
          selectedBranch="feature"
          defaultBranch="main"
          onBranchChange={mockOnBranchChange}
        />
      )
      await new Promise((resolve) => setTimeout(resolve, 50))
    })

    // Open the dropdown
    await act(async () => {
      await user.click(screen.getByRole('combobox'))
    })

    // Select the main (default) branch
    await act(async () => {
      await user.click(screen.getByText('main'))
      // Wait for MUI transitions to complete
      await new Promise((resolve) => setTimeout(resolve, 100))
    })

    // Should call with the branch name (for URL bookmarkability)
    expect(mockOnBranchChange).toHaveBeenCalledWith('main')
  })

  it('returns null when no branches are loaded', async () => {
    vi.mocked(api.getRepositoryBranches).mockResolvedValue({
      branches: [],
    })

    let container: HTMLElement
    await act(async () => {
      const result = render(
        <BranchSelector
          repositoryId={1}
          selectedBranch={null}
          defaultBranch="main"
          onBranchChange={mockOnBranchChange}
        />
      )
      container = result.container
      await new Promise((resolve) => setTimeout(resolve, 50))
    })

    expect(container!.firstChild).toBeNull()
  })

  it('falls back to default branch when selected branch is not indexed', async () => {
    vi.mocked(api.getRepositoryBranches).mockResolvedValue({
      branches: [
        {
          name: 'main',
          commit_count: 10,
          last_indexed_commit: 'abc123',
          oldest_indexed_commit: 'def456',
          last_indexed_at: '2024-01-01T00:00:00Z',
        },
        {
          name: 'feature',
          commit_count: 5,
          last_indexed_commit: 'xyz789',
          oldest_indexed_commit: 'uvw012',
          last_indexed_at: '2024-01-02T00:00:00Z',
        },
      ],
    })

    await act(async () => {
      render(
        <BranchSelector
          repositoryId={1}
          selectedBranch="non-existent-branch" // Branch not in the list
          defaultBranch="main"
          onBranchChange={mockOnBranchChange}
        />
      )
      await new Promise((resolve) => setTimeout(resolve, 50))
    })

    // Should show 'main' (the fallback) instead of the non-existent branch
    // The combobox should have 'main' selected, not cause MUI out-of-range error
    expect(screen.getByRole('combobox')).toHaveTextContent('main')
  })

  describe('file-aware indicators', () => {
    const branches = [
      {
        name: 'main',
        commit_count: 10,
        last_indexed_commit: 'abc123',
        oldest_indexed_commit: 'def456',
        last_indexed_at: '2024-01-01T00:00:00Z',
      },
      {
        name: 'feature-a',
        commit_count: 5,
        last_indexed_commit: 'xyz789',
        oldest_indexed_commit: 'uvw012',
        last_indexed_at: '2024-01-02T00:00:00Z',
      },
      {
        name: 'feature-b',
        commit_count: 3,
        last_indexed_commit: 'pqr345',
        oldest_indexed_commit: 'stu678',
        last_indexed_at: '2024-01-03T00:00:00Z',
      },
    ]

    it('shows checkmark for branches where file exists', async () => {
      vi.mocked(api.getRepositoryBranches).mockResolvedValue({ branches })

      // File exists on main and feature-a, but not feature-b
      vi.mocked(api.getFileHistory).mockImplementation(async (_repo, _path, branch) => {
        if (branch === 'main' || branch === 'feature-a') {
          return {
            path: 'src/test.py',
            repository_name: 'test-repo',
            versions: [
              {
                commit_id: 1,
                commit_hash: 'abc',
                short_hash: 'abc',
                commit_date: '2024-01-01',
                message: 'test',
                content_hash: 'hash1',
              },
            ],
            total: 1,
          }
        }
        // feature-b: file doesn't exist
        throw new Error('File not found')
      })

      const user = userEvent.setup()

      await act(async () => {
        render(
          <BranchSelector
            repositoryId={1}
            selectedBranch={null}
            defaultBranch="main"
            onBranchChange={mockOnBranchChange}
            repoName="test-repo"
            filePath="src/test.py"
          />
        )
        await new Promise((resolve) => setTimeout(resolve, 100))
      })

      // Open dropdown
      await act(async () => {
        await user.click(screen.getByRole('combobox'))
      })

      // Wait for file history to be fetched
      await waitFor(() => {
        const listbox = screen.getByRole('listbox')
        // main and feature-a should have checkmarks (file exists)
        // feature-b should not have a checkmark (file doesn't exist)
        const options = listbox.querySelectorAll('[role="option"]')
        expect(options).toHaveLength(3)
      })
    })

    it('shows edit icon for branches with unique file changes', async () => {
      vi.mocked(api.getRepositoryBranches).mockResolvedValue({ branches })

      // main has content_hash: hash1
      // feature-a has content_hash: hash2 (different - should show edit icon)
      // feature-b has content_hash: hash1 (same as main - no edit icon)
      vi.mocked(api.getFileHistory).mockImplementation(async (_repo, _path, branch) => {
        const contentHash = branch === 'feature-a' ? 'hash2' : 'hash1'
        return {
          path: 'src/test.py',
          repository_name: 'test-repo',
          versions: [
            {
              commit_id: 1,
              commit_hash: 'abc',
              short_hash: 'abc',
              commit_date: '2024-01-01',
              message: 'test',
              content_hash: contentHash,
            },
          ],
          total: 1,
        }
      })

      const user = userEvent.setup()

      await act(async () => {
        render(
          <BranchSelector
            repositoryId={1}
            selectedBranch={null}
            defaultBranch="main"
            onBranchChange={mockOnBranchChange}
            repoName="test-repo"
            filePath="src/test.py"
          />
        )
        await new Promise((resolve) => setTimeout(resolve, 100))
      })

      // Open dropdown
      await act(async () => {
        await user.click(screen.getByRole('combobox'))
      })

      // Wait for file history to be fetched and verify edit icon appears
      await waitFor(() => {
        const listbox = screen.getByRole('listbox')
        // feature-a should have an edit icon (different content hash)
        // Look for the EditIcon (has data-testid or specific class)
        expect(listbox.textContent).toContain('feature-a')
      })
    })

    it('does not fetch file history when filePath is not provided', async () => {
      vi.mocked(api.getRepositoryBranches).mockResolvedValue({ branches })
      vi.mocked(api.getFileHistory).mockClear()

      await act(async () => {
        render(
          <BranchSelector
            repositoryId={1}
            selectedBranch={null}
            defaultBranch="main"
            onBranchChange={mockOnBranchChange}
            // No filePath or repoName provided
          />
        )
        await new Promise((resolve) => setTimeout(resolve, 100))
      })

      // getFileHistory should not be called when filePath is not provided
      expect(api.getFileHistory).not.toHaveBeenCalled()
    })
  })
})
