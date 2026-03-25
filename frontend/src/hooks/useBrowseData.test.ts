import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, type RenderHookResult } from '@testing-library/react'
import { useBrowseData } from './useBrowseData'
import type { UseBrowseDataParams, UseBrowseDataResult } from './useBrowseData'
import type { BrowseUrlState } from './useBrowseTypes'
import * as api from '@/lib/api'
import { ApiError } from '@/lib/api'

/**
 * Render useBrowseData wrapped in act() so all async mount effects settle
 * without "not wrapped in act" warnings.
 */
async function renderBrowseDataHook(
  initialProps: UseBrowseDataParams
): Promise<RenderHookResult<UseBrowseDataResult, UseBrowseDataParams>> {
  let result: RenderHookResult<UseBrowseDataResult, UseBrowseDataParams>
  await act(async () => {
    result = renderHook((props: UseBrowseDataParams) => useBrowseData(props), { initialProps })
    await new Promise((resolve) => setTimeout(resolve, 50))
  })
  return result!
}

// Mock the API module
vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof api>()
  return {
    ...actual,
    getRepositories: vi.fn(),
    getRepositoryByName: vi.fn(),
    getRepositoryTreeByName: vi.fn(),
    getCommits: vi.fn(),
    getFileContentByPathAtCommit: vi.fn(),
    getFileSymbolsByPath: vi.fn(),
    getFileReferencesByPath: vi.fn(),
    getFileRawContent: vi.fn(),
    getFileHistory: vi.fn(),
    resolveFilePath: vi.fn(),
  }
})

// Mock fileUtils
vi.mock('@/lib/fileUtils', () => ({
  isImageFile: vi.fn(() => false),
}))

const mockGetRepositories = vi.mocked(api.getRepositories)
const mockGetRepositoryByName = vi.mocked(api.getRepositoryByName)
const mockGetRepositoryTreeByName = vi.mocked(api.getRepositoryTreeByName)
const mockGetCommits = vi.mocked(api.getCommits)
const mockGetFileHistory = vi.mocked(api.getFileHistory)
const mockGetFileContentByPathAtCommit = vi.mocked(api.getFileContentByPathAtCommit)
const mockGetFileSymbolsByPath = vi.mocked(api.getFileSymbolsByPath)
const mockGetFileReferencesByPath = vi.mocked(api.getFileReferencesByPath)
const mockResolveFilePath = vi.mocked(api.resolveFilePath)

function makeUrlState(overrides: Partial<BrowseUrlState> = {}): BrowseUrlState {
  return {
    repoName: 'test-repo',
    filePath: 'src/main.py',
    directoryPath: null,
    highlightLine: undefined,
    selectedCommit: null,
    diffCommit: null,
    diffMode: false,
    selectedBranch: null,
    diffBranch: null,
    searchQuery: '',
    drawerOpen: true,
    refsPanelOpen: false,
    treePanel: 'left',
    refPanel: 'left',
    activePanel: 'left',
    changedOnly: false,
    viewMode: null,
    ...overrides,
  }
}

function makeParams(urlState: BrowseUrlState): UseBrowseDataParams {
  return {
    urlState,
    diffFileVersions: [],
    navigate: vi.fn(),
    searchParams: new URLSearchParams(),
  }
}

describe('useBrowseData', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockGetRepositories.mockResolvedValue([])
    mockGetRepositoryByName.mockResolvedValue({
      id: 1,
      name: 'test-repo',
      url: '/path/to/repo',
      description: null,
      default_branch: 'main',
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
    })
    mockGetRepositoryTreeByName.mockResolvedValue({
      root: [],
      repository_id: 1,
      repository_name: 'test-repo',
      total_files: 0,
      total_directories: 0,
    })
    mockGetCommits.mockResolvedValue({ commits: [], total: 0 })
    mockGetFileHistory.mockResolvedValue({
      versions: [],
      path: '',
      repository_name: '',
      total: 0,
    })
    mockGetFileSymbolsByPath.mockResolvedValue({
      symbols: [],
      file_id: 1,
      file_path: 'src/main.py',
      total: 0,
    })
    mockGetFileReferencesByPath.mockResolvedValue({
      references: [],
      file_id: 1,
      file_path: 'src/main.py',
      total: 0,
    })
    mockResolveFilePath.mockResolvedValue({
      found: false,
      resolved_path: null,
      renamed_from: null,
      renamed_to: null,
      rename_commit_hash: null,
    })
  })

  describe('double-load prevention (#267)', () => {
    it('should skip re-fetch when selectedCommit changes from null to a hash (commit-sync)', async () => {
      // Scenario: Navigate from Search → Browse with ?line=X (no commit param).
      // File loads once (selectedCommit=null, API uses branch HEAD).
      // Then commit-sync writes HEAD hash to URL → selectedCommit changes →
      // file content effect should detect this is a null→hash transition and
      // skip the re-fetch entirely (no setFileLoading, no API calls).
      const fileContentObj = {
        id: 42,
        path: 'src/main.py',
        content: 'print("hello")',
        language: 'python',
        line_count: 1,
        size_bytes: 15,
      }

      mockGetFileContentByPathAtCommit.mockResolvedValue(fileContentObj)

      // Initial render: no commit param (selectedCommit=null)
      const initialUrlState = makeUrlState({ selectedCommit: null })
      const { result, rerender } = await renderBrowseDataHook(makeParams(initialUrlState))

      expect(result.current.fileContent).not.toBeNull()
      expect(mockGetFileContentByPathAtCommit).toHaveBeenCalledTimes(1)

      // Simulate commit-sync: selectedCommit changes from null to HEAD hash
      const headHash = 'abc123abc123abc123abc123abc123abc123abc1'
      const updatedUrlState = makeUrlState({ selectedCommit: headHash })

      await act(async () => {
        rerender(makeParams(updatedUrlState))
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      // Key assertion: file content API should NOT have been called again
      expect(mockGetFileContentByPathAtCommit).toHaveBeenCalledTimes(1)
      // Content should still be present (not cleared)
      expect(result.current.fileContent).toBe(fileContentObj)
    })

    it('should re-fetch when selectedCommit changes to a genuinely different commit', async () => {
      // When the user explicitly selects a different commit (not commit-sync),
      // the file content should be re-fetched.
      const firstContent = {
        id: 42,
        path: 'src/main.py',
        content: 'print("hello")',
        language: 'python',
        line_count: 1,
        size_bytes: 15,
      }
      const secondContent = {
        id: 99,
        path: 'src/main.py',
        content: 'print("world")',
        language: 'python',
        line_count: 1,
        size_bytes: 15,
      }

      mockGetFileContentByPathAtCommit
        .mockResolvedValueOnce(firstContent)
        .mockResolvedValueOnce(secondContent)

      // Start with an explicit commit
      const initialUrlState = makeUrlState({ selectedCommit: 'commit-aaa' })
      const { result, rerender } = await renderBrowseDataHook(makeParams(initialUrlState))

      expect(result.current.fileContent?.id).toBe(42)

      // Switch to a different commit (hash → different hash)
      const updatedUrlState = makeUrlState({ selectedCommit: 'commit-bbb' })

      await act(async () => {
        rerender(makeParams(updatedUrlState))
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      await vi.waitFor(() => {
        expect(result.current.fileContent?.id).toBe(99)
      })

      // Should have fetched twice — once for each commit
      expect(mockGetFileContentByPathAtCommit).toHaveBeenCalledTimes(2)
    })

    it('should re-fetch when file path changes even during commit-sync', async () => {
      // If both the file and commit change simultaneously, we must fetch
      const firstContent = {
        id: 42,
        path: 'src/main.py',
        content: 'print("hello")',
        language: 'python',
        line_count: 1,
        size_bytes: 15,
      }
      const secondContent = {
        id: 77,
        path: 'src/other.py',
        content: 'print("other")',
        language: 'python',
        line_count: 1,
        size_bytes: 15,
      }

      mockGetFileContentByPathAtCommit
        .mockResolvedValueOnce(firstContent)
        .mockResolvedValueOnce(secondContent)

      const initialUrlState = makeUrlState({ selectedCommit: null, filePath: 'src/main.py' })
      const { result, rerender } = await renderBrowseDataHook(makeParams(initialUrlState))

      expect(result.current.fileContent).not.toBeNull()

      // Navigate to different file AND commit syncs at same time
      const updatedUrlState = makeUrlState({
        selectedCommit: 'abc123',
        filePath: 'src/other.py',
      })

      await act(async () => {
        rerender(makeParams(updatedUrlState))
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      await vi.waitFor(() => {
        expect(result.current.fileContent?.id).toBe(77)
      })

      expect(mockGetFileContentByPathAtCommit).toHaveBeenCalledTimes(2)
    })

    it('should skip re-fetch even when commit-sync fires while initial load is in-flight', async () => {
      // Race condition: commit-sync resolves before the initial file fetch
      // completes.  The optimistic ref update should prevent a second request.
      const fileContentObj = {
        id: 42,
        path: 'src/main.py',
        content: 'print("hello")',
        language: 'python',
        line_count: 1,
        size_bytes: 15,
      }

      // Make file content resolve slowly (after commit-sync would fire)
      let resolveContent!: (value: typeof fileContentObj) => void
      mockGetFileContentByPathAtCommit.mockReturnValue(
        new Promise((resolve) => {
          resolveContent = resolve
        })
      )

      // Initial render: selectedCommit=null (implicit HEAD)
      const initialUrlState = makeUrlState({ selectedCommit: null })
      let hookResult: Awaited<ReturnType<typeof renderBrowseDataHook>>

      // Render without waiting for content to settle
      await act(async () => {
        hookResult = await renderBrowseDataHook(makeParams(initialUrlState))
      })

      // Content still loading — commit-sync fires while in-flight
      const headHash = 'abc123abc123abc123abc123abc123abc123abc1'
      const updatedUrlState = makeUrlState({ selectedCommit: headHash })

      await act(async () => {
        hookResult!.rerender(makeParams(updatedUrlState))
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      // Now let the original fetch complete
      await act(async () => {
        resolveContent(fileContentObj)
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      // Key assertion: only ONE fetch should have been made (the initial one)
      expect(mockGetFileContentByPathAtCommit).toHaveBeenCalledTimes(1)
      expect(hookResult!.result.current.fileContent).toBe(fileContentObj)
    })
  })

  describe('double tree-load prevention (#391)', () => {
    it('should load tree only once when latestBranchCommit resolves after initial load', async () => {
      // Scenario: Navigate to a repo with ?branch=main (no commit param).
      // Tree loads once (treeCommit=undefined, API uses branch only).
      // Then getCommits resolves to HEAD hash → latestBranchCommit changes →
      // treeCommit changes from undefined → "abc123" → effect re-fires.
      // Skip guard should detect this null→hash transition and suppress the
      // second fetch (both calls return identical results).

      // Make getCommits deferred so we can control when latestBranchCommit resolves
      let resolveCommits!: (value: api.CommitListResponse) => void
      mockGetCommits.mockReturnValue(
        new Promise<api.CommitListResponse>((resolve) => {
          resolveCommits = resolve
        })
      )

      const urlState = makeUrlState({
        repoName: 'test-repo',
        filePath: null,
        selectedBranch: 'main',
        selectedCommit: null,
      })

      await act(async () => {
        await renderBrowseDataHook(makeParams(urlState))
      })

      // Tree should have been called once (with branch only, no commit)
      expect(mockGetRepositoryTreeByName).toHaveBeenCalledTimes(1)
      expect(mockGetRepositoryTreeByName).toHaveBeenCalledWith(
        'test-repo',
        undefined,
        'main',
        false
      )

      // Now simulate latestBranchCommit resolving to HEAD hash
      const headHash = 'abc123abc123abc123abc123abc123abc123abc1'
      await act(async () => {
        resolveCommits({
          commits: [
            {
              hash: headHash,
              short_hash: 'abc123a',
              message: 'fix',
              author_name: 'A',
              author_email: 'a@b.com',
              commit_date: '2024-01-01',
              is_indexed: true,
              tags: [],
              is_branch_specific: false,
              is_merge_base: false,
            },
          ],
          total: 1,
        })
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      // Key assertion: tree should NOT have been re-fetched (skip guard)
      expect(mockGetRepositoryTreeByName).toHaveBeenCalledTimes(1)
    })

    it('should re-fetch tree when switching to a different branch', async () => {
      // After the skip guard fires, a genuine branch change must still fetch
      const urlState = makeUrlState({
        filePath: null,
        selectedBranch: 'main',
        selectedCommit: null,
      })
      const { rerender } = await renderBrowseDataHook(makeParams(urlState))

      const updatedUrlState = makeUrlState({
        filePath: null,
        selectedBranch: 'feature',
        selectedCommit: null,
      })
      await act(async () => {
        rerender(makeParams(updatedUrlState))
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      // Verify the skip guard didn't block the branch-switch fetch
      expect(mockGetRepositoryTreeByName).toHaveBeenCalledWith(
        'test-repo',
        undefined,
        'feature',
        false
      )
    })

    it('should re-fetch tree when changedOnly is true even if commit just resolved', async () => {
      // changedOnly=true: tree at HEAD via branch ≠ tree filtered to commit's diff
      // The skip guard must NOT fire in this case.
      let resolveCommits!: (value: api.CommitListResponse) => void
      mockGetCommits.mockReturnValue(
        new Promise<api.CommitListResponse>((resolve) => {
          resolveCommits = resolve
        })
      )

      const urlState = makeUrlState({
        filePath: null,
        selectedBranch: 'main',
        selectedCommit: null,
        changedOnly: true,
      })

      await act(async () => {
        await renderBrowseDataHook(makeParams(urlState))
      })

      // Guard 1 fires (changedOnly + no commit yet), so tree may not have been called
      const callsBeforeResolve = mockGetRepositoryTreeByName.mock.calls.length

      const headHash = 'abc123abc123abc123abc123abc123abc123abc1'
      await act(async () => {
        resolveCommits({
          commits: [
            {
              hash: headHash,
              short_hash: 'abc123a',
              message: 'fix',
              author_name: 'A',
              author_email: 'a@b.com',
              commit_date: '2024-01-01',
              is_indexed: true,
              tags: [],
              is_branch_specific: false,
              is_merge_base: false,
            },
          ],
          total: 1,
        })
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      // After commit resolves, tree SHOULD load exactly once (skip guard must not block this)
      expect(mockGetRepositoryTreeByName).toHaveBeenCalledTimes(callsBeforeResolve + 1)
    })
  })

  describe('rename banner (#240)', () => {
    it('sets fileRenameInfo and clears stale content when file returns 404 and rename is found', async () => {
      // Browsing a renamed file at an old commit: getFileContentByPathAtCommit
      // returns 404, resolveFilePath finds the old path.
      const renameInfo = {
        found: false,
        resolved_path: 'src/old.py',
        renamed_from: 'src/old.py',
        renamed_to: null,
        rename_commit_hash: 'abc123',
      }
      mockGetFileContentByPathAtCommit.mockRejectedValue(new ApiError('Not Found', 404))
      mockResolveFilePath.mockResolvedValue(renameInfo)

      const urlState = makeUrlState({
        filePath: 'src/new.py',
        selectedCommit: 'commit-before-rename',
        selectedBranch: 'main',
      })
      const { result } = await renderBrowseDataHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.fileRenameInfo).toEqual(renameInfo)
      })
      // Stale content must be cleared
      expect(result.current.fileContent).toBeNull()
      expect(result.current.fileSymbols).toEqual([])
      expect(result.current.fileReferences).toEqual([])
      // No error shown — banner replaces it
      expect(result.current.error).toBeNull()
      // resolveFilePath called with branch
      expect(mockResolveFilePath).toHaveBeenCalledWith(
        'test-repo',
        'src/new.py',
        'commit-before-rename',
        'main'
      )
    })

    it('does not call resolveFilePath for non-404 errors', async () => {
      mockGetFileContentByPathAtCommit.mockRejectedValue(new ApiError('Internal Server Error', 500))

      const urlState = makeUrlState({ selectedCommit: 'some-commit' })
      const { result } = await renderBrowseDataHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.error).not.toBeNull()
      })
      expect(mockResolveFilePath).not.toHaveBeenCalled()
      expect(result.current.fileRenameInfo).toBeNull()
    })
  })
})
