import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { VersionSelector } from './VersionSelector'
import * as api from '@/lib/api'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getFileHistory: vi.fn(),
}))

const mockGetFileHistory = vi.mocked(api.getFileHistory)

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
    it('should show loading indicator while fetching versions', async () => {
      // Never resolve the promise to keep loading state
      mockGetFileHistory.mockReturnValue(new Promise(() => {}))

      render(<VersionSelector {...defaultProps} />)

      // Should show loading indicator (CircularProgress)
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('should render nothing when no repoName provided', async () => {
      const { container } = render(
        <VersionSelector {...defaultProps} repoName="" />
      )

      // Should not call API and render nothing
      expect(mockGetFileHistory).not.toHaveBeenCalled()
      expect(container.firstChild).toBeNull()
    })

    it('should render nothing when no filePath provided', async () => {
      const { container } = render(
        <VersionSelector {...defaultProps} filePath="" />
      )

      expect(mockGetFileHistory).not.toHaveBeenCalled()
      expect(container.firstChild).toBeNull()
    })

    it('should render nothing when API returns empty versions', async () => {
      mockGetFileHistory.mockResolvedValue({
        path: 'src/main.py',
        repository_name: 'test-repo',
        versions: [],
        total: 0,
      })

      const { container } = render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(container.querySelector('[role="progressbar"]')).not.toBeInTheDocument()
      })

      // Should render nothing for empty versions
      expect(container.firstChild).toBeNull()
    })
  })

  describe('single version', () => {
    it('should show static display for single version', async () => {
      mockGetFileHistory.mockResolvedValue({
        path: 'src/main.py',
        repository_name: 'test-repo',
        versions: [
          {
            commit_id: 1,
            commit_hash: 'abc1234567890abcdef1234567890abcdef123456',
            short_hash: 'abc1234',
            commit_date: '2025-01-15T10:30:00Z',
            message: 'Initial commit',
            content_hash: 'hash1',
          },
        ],
        total: 1,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('abc1234')).toBeInTheDocument()
      })

      // Should not have a select/dropdown for single version
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    })
  })

  describe('multiple versions', () => {
    const multipleVersions = {
      path: 'src/main.py',
      repository_name: 'test-repo',
      versions: [
        {
          commit_id: 3,
          commit_hash: 'ccc1234567890abcdef1234567890abcdef123456',
          short_hash: 'ccc1234',
          commit_date: '2025-01-17T10:30:00Z',
          message: 'Third commit',
          content_hash: 'hash3',
        },
        {
          commit_id: 2,
          commit_hash: 'bbb1234567890abcdef1234567890abcdef123456',
          short_hash: 'bbb1234',
          commit_date: '2025-01-16T10:30:00Z',
          message: 'Second commit (file unchanged)',
          content_hash: 'hash2', // Same as first = no change
        },
        {
          commit_id: 1,
          commit_hash: 'aaa1234567890abcdef1234567890abcdef123456',
          short_hash: 'aaa1234',
          commit_date: '2025-01-15T10:30:00Z',
          message: 'First commit',
          content_hash: 'hash2',
        },
      ],
      total: 3,
    }

    it('should show dropdown for multiple versions', async () => {
      mockGetFileHistory.mockResolvedValue(multipleVersions)

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })
    })

    it('should call onVersionChange with null when selecting latest', async () => {
      mockGetFileHistory.mockResolvedValue(multipleVersions)
      const onVersionChange = vi.fn()

      // Start with an older version selected
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

      // Open dropdown and select the first (latest) option
      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      // Click on the latest version
      const options = screen.getAllByRole('option')
      fireEvent.click(options[0]!)

      // Should call with null for latest version
      expect(onVersionChange).toHaveBeenCalledWith(null)
    })

    it('should call onVersionChange with commit hash when selecting older version', async () => {
      mockGetFileHistory.mockResolvedValue(multipleVersions)
      const onVersionChange = vi.fn()

      render(<VersionSelector {...defaultProps} onVersionChange={onVersionChange} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      // Open dropdown
      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      // Click on an older version (not the first one)
      const options = screen.getAllByRole('option')
      fireEvent.click(options[2]!) // Third option (oldest)

      // Should call with the commit hash
      expect(onVersionChange).toHaveBeenCalledWith(
        'aaa1234567890abcdef1234567890abcdef123456'
      )
    })
  })

  describe('date formatting', () => {
    it('should format dates as yyyymmdd', async () => {
      mockGetFileHistory.mockResolvedValue({
        path: 'src/main.py',
        repository_name: 'test-repo',
        versions: [
          {
            commit_id: 2,
            commit_hash: 'bbb1234567890abcdef1234567890abcdef123456',
            short_hash: 'bbb1234',
            commit_date: '2025-03-15T10:30:00Z',
            message: 'Second commit',
            content_hash: 'hash2',
          },
          {
            commit_id: 1,
            commit_hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-05T10:30:00Z',
            message: 'First commit',
            content_hash: 'hash1',
          },
        ],
        total: 2,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      // Open dropdown to see date formatting
      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      // Dates should be in yyyymmdd format (local timezone varies, so check pattern)
      // The exact date depends on timezone, but format should be 8 digits
      const listbox = screen.getByRole('listbox')
      const datePattern = /\d{8}/
      expect(listbox.textContent).toMatch(datePattern)
    })

    it('should add time for same-day commits', async () => {
      mockGetFileHistory.mockResolvedValue({
        path: 'src/main.py',
        repository_name: 'test-repo',
        versions: [
          {
            commit_id: 2,
            commit_hash: 'bbb1234567890abcdef1234567890abcdef123456',
            short_hash: 'bbb1234',
            commit_date: '2025-01-15T14:30:00Z',
            message: 'Afternoon commit',
            content_hash: 'hash2',
          },
          {
            commit_id: 1,
            commit_hash: 'aaa1234567890abcdef1234567890abcdef123456',
            short_hash: 'aaa1234',
            commit_date: '2025-01-15T10:30:00Z',
            message: 'Morning commit',
            content_hash: 'hash1',
          },
        ],
        total: 2,
      })

      render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      // Open dropdown
      fireEvent.mouseDown(screen.getByRole('combobox'))

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })

      // Same-day commits should include time (hh:mm format)
      const listbox = screen.getByRole('listbox')
      const timePattern = /\d{2}:\d{2}/
      expect(listbox.textContent).toMatch(timePattern)
    })
  })

  describe('error handling', () => {
    it('should render nothing when API throws error', async () => {
      mockGetFileHistory.mockRejectedValue(new Error('API error'))

      const { container } = render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(container.querySelector('[role="progressbar"]')).not.toBeInTheDocument()
      })

      // Should render nothing on error
      expect(container.firstChild).toBeNull()
    })
  })

  describe('props changes', () => {
    it('should refetch when filePath changes', async () => {
      mockGetFileHistory.mockResolvedValue({
        path: 'src/main.py',
        repository_name: 'test-repo',
        versions: [
          {
            commit_id: 1,
            commit_hash: 'abc1234567890abcdef1234567890abcdef123456',
            short_hash: 'abc1234',
            commit_date: '2025-01-15T10:30:00Z',
            message: 'Commit',
            content_hash: 'hash1',
          },
        ],
        total: 1,
      })

      const { rerender } = render(<VersionSelector {...defaultProps} />)

      await waitFor(() => {
        expect(mockGetFileHistory).toHaveBeenCalledWith('test-repo', 'src/main.py')
      })

      // Change filePath
      rerender(<VersionSelector {...defaultProps} filePath="src/other.py" />)

      await waitFor(() => {
        expect(mockGetFileHistory).toHaveBeenCalledWith('test-repo', 'src/other.py')
      })

      expect(mockGetFileHistory).toHaveBeenCalledTimes(2)
    })
  })
})
