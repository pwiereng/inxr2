import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { VersionSelector } from './VersionSelector'
import * as api from '@/lib/api'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getCommits: vi.fn(),
  getFileHistory: vi.fn(),
}))

const mockGetCommits = vi.mocked(api.getCommits)
const mockGetFileHistory = vi.mocked(api.getFileHistory)

function makeCommit(overrides: Partial<api.CommitInfo> = {}): api.CommitInfo {
  return {
    hash: 'abc1234567890abcdef1234567890abcdef123456',
    short_hash: 'abc1234',
    message: 'Test commit',
    author_name: 'Test',
    author_email: 'test@test.com',
    commit_date: '2025-01-15T10:30:00Z',
    is_indexed: true,
    tags: [],
    is_branch_specific: false,
    is_merge_base: false,
    ...overrides,
  }
}

describe('VersionSelector', () => {
  const defaultProps = {
    repoName: 'test-repo',
    filePath: 'src/main.py',
    selectedCommit: null,
    onVersionChange: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('loading state', () => {
    it('should show loading indicator while fetching', async () => {
      // Never resolve to keep loading
      mockGetCommits.mockReturnValue(new Promise(() => {}))

      render(<VersionSelector {...defaultProps} />)

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('should render nothing when no repoName provided', async () => {
      const { container } = render(<VersionSelector {...defaultProps} repoName="" />)

      expect(mockGetCommits).not.toHaveBeenCalled()
      expect(container.firstChild).toBeNull()
    })

    it('should render nothing when no filePath provided', async () => {
      const { container } = render(<VersionSelector {...defaultProps} filePath="" />)

      expect(mockGetCommits).not.toHaveBeenCalled()
      expect(container.firstChild).toBeNull()
    })

    it('should render nothing when API returns empty commits', async () => {
      mockGetCommits.mockResolvedValue({ commits: [], total: 0 })

      const { container } = render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(container.querySelector('[role="progressbar"]')).not.toBeInTheDocument()
      })

      expect(container.firstChild).toBeNull()
    })
  })

  describe('single commit', () => {
    it('should show static display for single commit (no dropdown)', async () => {
      mockGetCommits.mockResolvedValue({
        commits: [makeCommit({ short_hash: 'abc1234' })],
        total: 1,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('abc1234')).toBeInTheDocument()
      })

      expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    })
  })

  describe('multiple commits', () => {
    const threeCommits = {
      commits: [
        makeCommit({
          hash: 'ccc1234567890abcdef1234567890abcdef123456',
          short_hash: 'ccc1234',
          commit_date: '2025-01-17T10:30:00Z',
          message: 'Third commit',
          is_indexed: true,
        }),
        makeCommit({
          hash: 'bbb1234567890abcdef1234567890abcdef123456',
          short_hash: 'bbb1234',
          commit_date: '2025-01-16T10:30:00Z',
          message: 'Second commit',
          is_indexed: true,
        }),
        makeCommit({
          hash: 'aaa1234567890abcdef1234567890abcdef123456',
          short_hash: 'aaa1234',
          commit_date: '2025-01-15T10:30:00Z',
          message: 'First commit',
          is_indexed: true,
        }),
      ],
      total: 3,
    }

    it('should show dropdown for multiple commits', async () => {
      mockGetCommits.mockResolvedValue(threeCommits)

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })
    })

    it('should display all commits (not just file-modifying ones)', async () => {
      mockGetCommits.mockResolvedValue(threeCommits)

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      const options = screen.getAllByRole('option')
      expect(options).toHaveLength(3)
    })

    it('should call onVersionChange with commit hash when selecting', async () => {
      mockGetCommits.mockResolvedValue(threeCommits)
      const onVersionChange = vi.fn()

      render(<VersionSelector {...defaultProps} onVersionChange={onVersionChange} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      const options = screen.getAllByRole('option')
      fireEvent.click(options[2]!)

      expect(onVersionChange).toHaveBeenCalledWith('aaa1234567890abcdef1234567890abcdef123456')
    })

    it('should call onVersionChange with latest hash when selecting first option', async () => {
      mockGetCommits.mockResolvedValue(threeCommits)
      const onVersionChange = vi.fn()

      render(
        <VersionSelector
          {...defaultProps}
          selectedCommit="aaa1234567890abcdef1234567890abcdef123456"
          onVersionChange={onVersionChange}
        />
      )

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      const options = screen.getAllByRole('option')
      fireEvent.click(options[0]!)

      expect(onVersionChange).toHaveBeenCalledWith('ccc1234567890abcdef1234567890abcdef123456')
    })
  })

  describe('showFileChanges prop', () => {
    const twoCommits = {
      commits: [
        makeCommit({
          hash: 'bbb1234567890abcdef1234567890abcdef123456',
          short_hash: 'bbb1234',
          commit_date: '2025-01-16T10:30:00Z',
          message: 'Second commit',
        }),
        makeCommit({
          hash: 'aaa1234567890abcdef1234567890abcdef123456',
          short_hash: 'aaa1234',
          commit_date: '2025-01-15T10:30:00Z',
          message: 'First commit',
        }),
      ],
      total: 2,
    }

    it('should not fetch file history when showFileChanges is false', async () => {
      mockGetCommits.mockResolvedValue(twoCommits)

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      expect(mockGetFileHistory).not.toHaveBeenCalled()
    })

    it('should fetch file history when showFileChanges is true', async () => {
      mockGetCommits.mockResolvedValue(twoCommits)
      mockGetFileHistory.mockResolvedValue({
        path: 'src/main.py',
        repository_name: 'test-repo',
        versions: [
          {
            commit_id: 1,
            commit_hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-15T10:30:00Z',
            message: 'First commit',
            content_hash: 'hash1',
          },
        ],
        total: 1,
      })

      render(<VersionSelector {...defaultProps} showFileChanges />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      expect(mockGetFileHistory).toHaveBeenCalledWith('test-repo', 'src/main.py', undefined)
    })

    it('should show EditIcon only on commits that modified the file', async () => {
      mockGetCommits.mockResolvedValue(twoCommits)
      mockGetFileHistory.mockResolvedValue({
        path: 'src/main.py',
        repository_name: 'test-repo',
        versions: [
          {
            commit_id: 1,
            commit_hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-15T10:30:00Z',
            message: 'First commit',
            content_hash: 'hash1',
          },
        ],
        total: 1,
      })

      render(<VersionSelector {...defaultProps} showFileChanges />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      // EditIcon is an SVG with data-testid="EditIcon"
      const editIcons = screen.getAllByTestId('EditIcon')
      // Only the file-changing commit (aaa) should have EditIcon
      expect(editIcons).toHaveLength(1)
    })
  })

  describe('HEAD badge', () => {
    it('should show HEAD badge for the first indexed commit', async () => {
      mockGetCommits.mockResolvedValue({
        commits: [
          makeCommit({
            hash: 'bbb1234567890abcdef1234567890abcdef123456',
            short_hash: 'bbb1234',
            commit_date: '2025-01-16T10:30:00Z',
            is_indexed: true,
          }),
          makeCommit({
            hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-15T10:30:00Z',
            is_indexed: true,
          }),
        ],
        total: 2,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      // HEAD appears in both the combobox display and the dropdown item
      expect(screen.getAllByText('HEAD').length).toBeGreaterThanOrEqual(1)
    })

    it('should not show HEAD badge on non-first indexed commit', async () => {
      mockGetCommits.mockResolvedValue({
        commits: [
          makeCommit({
            hash: 'ccc1234567890abcdef1234567890abcdef123456',
            short_hash: 'ccc1234',
            commit_date: '2025-01-17T10:30:00Z',
            is_indexed: false, // not indexed
          }),
          makeCommit({
            hash: 'bbb1234567890abcdef1234567890abcdef123456',
            short_hash: 'bbb1234',
            commit_date: '2025-01-16T10:30:00Z',
            is_indexed: true, // first indexed
          }),
          makeCommit({
            hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-15T10:30:00Z',
            is_indexed: true,
          }),
        ],
        total: 3,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      // HEAD should appear once — on bbb (first indexed)
      const headBadges = screen.getAllByText('HEAD')
      expect(headBadges).toHaveLength(1)
    })
  })

  describe('FORK badge', () => {
    it('should show FORK badge on merge-base commits', async () => {
      mockGetCommits.mockResolvedValue({
        commits: [
          makeCommit({
            hash: 'bbb1234567890abcdef1234567890abcdef123456',
            short_hash: 'bbb1234',
            commit_date: '2025-01-16T10:30:00Z',
            is_merge_base: false,
          }),
          makeCommit({
            hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-15T10:30:00Z',
            is_merge_base: true,
          }),
        ],
        total: 2,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      expect(screen.getByText('FORK')).toBeInTheDocument()
    })
  })

  describe('branch-specific styling', () => {
    it('should apply left border styling for branch-specific commits', async () => {
      mockGetCommits.mockResolvedValue({
        commits: [
          makeCommit({
            hash: 'bbb1234567890abcdef1234567890abcdef123456',
            short_hash: 'bbb1234',
            commit_date: '2025-01-16T10:30:00Z',
            is_branch_specific: true,
          }),
          makeCommit({
            hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-15T10:30:00Z',
            is_branch_specific: false,
          }),
        ],
        total: 2,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      // Both commits are in the dropdown
      const options = screen.getAllByRole('option')
      expect(options).toHaveLength(2)
    })
  })

  describe('date formatting', () => {
    it('should format dates as YYYY-MM-DD HH:MM UTC', async () => {
      mockGetCommits.mockResolvedValue({
        commits: [
          makeCommit({
            hash: 'bbb1234567890abcdef1234567890abcdef123456',
            short_hash: 'bbb1234',
            commit_date: '2025-03-15T10:30:00Z',
          }),
          makeCommit({
            hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-05T14:45:00Z',
          }),
        ],
        total: 2,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      expect(screen.getAllByText('2025-03-15 10:30 UTC').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('2025-01-05 14:45 UTC')).toBeInTheDocument()
    })
  })

  describe('error handling', () => {
    it('should render nothing when API throws error', async () => {
      mockGetCommits.mockRejectedValue(new Error('API error'))

      const { container } = render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(container.querySelector('[role="progressbar"]')).not.toBeInTheDocument()
      })

      expect(container.firstChild).toBeNull()
    })
  })

  describe('props changes', () => {
    it('should refetch when filePath changes', async () => {
      mockGetCommits.mockResolvedValue({
        commits: [makeCommit()],
        total: 1,
      })

      const { rerender } = render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(mockGetCommits).toHaveBeenCalledWith('test-repo', undefined, 500)
      })

      rerender(<VersionSelector {...defaultProps} filePath="src/other.py" />)

      await waitFor(() => {
        expect(mockGetCommits).toHaveBeenCalledTimes(2)
      })
    })
  })
})
