import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, type RenderHookResult } from '@testing-library/react'
import { useBrowseData } from './useBrowseData'
import type { UseBrowseDataParams, UseBrowseDataResult } from './useBrowseData'
import type { BrowseUrlState } from './useBrowseTypes'
import * as api from '@/lib/api'

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
vi.mock('@/lib/api', () => ({
  getRepositories: vi.fn(),
  getRepositoryByName: vi.fn(),
  getRepositoryTreeByName: vi.fn(),
  getCommits: vi.fn(),
  getFileContentByPathAtCommit: vi.fn(),
  getFileSymbolsByPath: vi.fn(),
  getFileReferencesByPath: vi.fn(),
  getFileRawContent: vi.fn(),
  getFileHistory: vi.fn(),
}))

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

function makeUrlState(overrides: Partial<BrowseUrlState> = {}): BrowseUrlState {
  return {
    repoName: 'test-repo',
    filePath: 'src/main.py',
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
})
