import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useRepositorySelector } from './useRepositorySelector'
import * as api from '@/lib/api'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getRepositories: vi.fn(),
  getRepositoryBranches: vi.fn(),
  getCommits: vi.fn(),
}))

const mockGetRepositories = vi.mocked(api.getRepositories)
const mockGetRepositoryBranches = vi.mocked(api.getRepositoryBranches)
const mockGetCommits = vi.mocked(api.getCommits)

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
    {
      name: 'unindexed-branch',
      last_indexed_commit: null,
      oldest_indexed_commit: null,
      commit_count: 0,
      last_indexed_at: null,
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
    {
      hash: 'notindexed123',
      short_hash: 'notinde',
      message: 'Not indexed commit',
      author_name: 'Test Author',
      author_email: 'test@example.com',
      commit_date: '2024-01-03T08:00:00Z',
      is_indexed: false,
      tags: [],
      is_branch_specific: false,
      is_merge_base: false,
    },
  ],
  total: 3,
}

/**
 * Helper to render the hook and wait for all async effects to settle.
 */
async function renderRepositorySelectorHook(
  params: { repoName: string | null; branch: string | null; commit: string | null } = {
    repoName: 'test-repo',
    branch: 'main',
    commit: null,
  }
) {
  let result: ReturnType<typeof renderHook<ReturnType<typeof useRepositorySelector>, unknown>>
  await act(async () => {
    result = renderHook(() => useRepositorySelector(params))
    await new Promise((resolve) => setTimeout(resolve, 50))
  })
  return result!
}

describe('useRepositorySelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetRepositories.mockResolvedValue(mockRepositories)
    mockGetRepositoryBranches.mockResolvedValue(mockBranches)
    mockGetCommits.mockResolvedValue(mockCommits)
  })

  describe('initial state', () => {
    it('should start with loading repos', () => {
      // Use a never-resolving promise so loading stays true
      mockGetRepositories.mockReturnValue(new Promise(() => {}))
      mockGetCommits.mockReturnValue(new Promise(() => {}))

      const { result } = renderHook(() =>
        useRepositorySelector({ repoName: null, branch: null, commit: null })
      )

      expect(result.current.loadingRepos).toBe(true)
      expect(result.current.repositories).toEqual([])
      expect(result.current.branches).toEqual([])
      expect(result.current.commits).toEqual([])
    })
  })

  describe('repository loading', () => {
    it('should load repositories on mount', async () => {
      const { result } = await renderRepositorySelectorHook({
        repoName: null,
        branch: null,
        commit: null,
      })

      expect(mockGetRepositories).toHaveBeenCalledTimes(1)
      expect(result.current.repositories).toEqual(mockRepositories)
      expect(result.current.loadingRepos).toBe(false)
    })

    it('should handle repository loading error', async () => {
      mockGetRepositories.mockRejectedValue(new Error('Network error'))
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const { result } = await renderRepositorySelectorHook({
        repoName: null,
        branch: null,
        commit: null,
      })

      expect(result.current.repositories).toEqual([])
      expect(result.current.loadingRepos).toBe(false)
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Failed to load repositories:',
        expect.any(Error)
      )

      consoleErrorSpy.mockRestore()
    })
  })

  describe('branch loading', () => {
    it('should load branches when repoName is provided', async () => {
      const { result } = await renderRepositorySelectorHook()

      expect(mockGetRepositoryBranches).toHaveBeenCalledWith(1)
      // Should filter out unindexed branches
      expect(result.current.branches).toHaveLength(2)
      expect(result.current.branches.map((b) => b.name)).toEqual(['main', 'feature-branch'])
    })

    it('should not load branches when repoName is null', async () => {
      const { result } = await renderRepositorySelectorHook({
        repoName: null,
        branch: null,
        commit: null,
      })

      expect(result.current.branches).toEqual([])
      // getRepositoryBranches should not have been called
      expect(mockGetRepositoryBranches).not.toHaveBeenCalled()
    })

    it('should clear branches on error', async () => {
      mockGetRepositoryBranches.mockRejectedValue(new Error('Branch error'))
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const { result } = await renderRepositorySelectorHook()

      expect(result.current.branches).toEqual([])
      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to load branches:', expect.any(Error))

      consoleErrorSpy.mockRestore()
    })
  })

  describe('commit loading', () => {
    it('should load commits when repoName and branch are provided', async () => {
      const { result } = await renderRepositorySelectorHook()

      expect(mockGetCommits).toHaveBeenCalledWith('test-repo', 'main', 500)
      // Should filter out non-indexed commits
      expect(result.current.commits).toHaveLength(2)
      expect(result.current.commits.map((c) => c.hash)).toEqual(['abc123def456', 'def456ghi789'])
    })

    it('should pass undefined branch when branch is null', async () => {
      const { result } = await renderRepositorySelectorHook({
        repoName: 'test-repo',
        branch: null,
        commit: null,
      })

      expect(mockGetCommits).toHaveBeenCalledWith('test-repo', undefined, 500)
      expect(result.current.commits).toHaveLength(2)
    })

    it('should not load commits when repoName is null', async () => {
      const { result } = await renderRepositorySelectorHook({
        repoName: null,
        branch: null,
        commit: null,
      })

      expect(result.current.commits).toEqual([])
    })

    it('should clear commits on error', async () => {
      mockGetCommits.mockRejectedValue(new Error('Commit error'))
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const { result } = await renderRepositorySelectorHook()

      expect(result.current.commits).toEqual([])
      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to load commits:', expect.any(Error))

      consoleErrorSpy.mockRestore()
    })
  })

  describe('computed values', () => {
    it('should compute currentRepo from repositories and repoName', async () => {
      const { result } = await renderRepositorySelectorHook()

      expect(result.current.currentRepo).toEqual(mockRepositories[0])
    })

    it('should return undefined currentRepo when repoName does not match', async () => {
      const { result } = await renderRepositorySelectorHook({
        repoName: 'nonexistent',
        branch: null,
        commit: null,
      })

      expect(result.current.currentRepo).toBeUndefined()
    })

    it('should compute defaultBranch from currentRepo', async () => {
      const { result } = await renderRepositorySelectorHook()

      expect(result.current.defaultBranch).toBe('main')
    })

    it('should fall back to "main" when no currentRepo', async () => {
      const { result } = await renderRepositorySelectorHook({
        repoName: null,
        branch: null,
        commit: null,
      })

      expect(result.current.defaultBranch).toBe('main')
    })

    it('should use commit prop as commitDisplayValue when provided', async () => {
      const { result } = await renderRepositorySelectorHook({
        repoName: 'test-repo',
        branch: 'main',
        commit: 'def456ghi789',
      })

      expect(result.current.commitDisplayValue).toBe('def456ghi789')
    })

    it('should fall back to first commit hash when no commit prop', async () => {
      const { result } = await renderRepositorySelectorHook()

      expect(result.current.commitDisplayValue).toBe('abc123def456')
    })

    it('should return empty string commitDisplayValue when no commits', async () => {
      mockGetCommits.mockResolvedValue({ commits: [], total: 0 })

      const { result } = await renderRepositorySelectorHook()

      expect(result.current.commitDisplayValue).toBe('')
    })

    it('should compute currentCommitDate for selected commit', async () => {
      const { result } = await renderRepositorySelectorHook({
        repoName: 'test-repo',
        branch: 'main',
        commit: 'def456ghi789',
      })

      expect(result.current.currentCommitDate).toBe('2024-01-02 14:45 UTC')
    })

    it('should compute currentCommitDate for latest commit when no commit selected', async () => {
      const { result } = await renderRepositorySelectorHook()

      expect(result.current.currentCommitDate).toBe('2024-01-01 10:30 UTC')
    })

    it('should return empty string for currentCommitDate when no commits', async () => {
      mockGetCommits.mockResolvedValue({ commits: [], total: 0 })

      const { result } = await renderRepositorySelectorHook()

      expect(result.current.currentCommitDate).toBe('')
    })
  })
})
