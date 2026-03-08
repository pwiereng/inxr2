import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useBrowseData } from './useBrowseData'
import type { UseBrowseDataParams } from './useBrowseData'
import type { BrowseUrlState } from './useBrowseTypes'
import * as api from '@/lib/api'

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
      const { result, rerender } = renderHook(
        (props: UseBrowseDataParams) => useBrowseData(props),
        { initialProps: makeParams(initialUrlState) }
      )

      // Wait for initial file load
      await vi.waitFor(() => {
        expect(result.current.fileContent).not.toBeNull()
      })

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
      const { result, rerender } = renderHook(
        (props: UseBrowseDataParams) => useBrowseData(props),
        { initialProps: makeParams(initialUrlState) }
      )

      await vi.waitFor(() => {
        expect(result.current.fileContent).not.toBeNull()
      })

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
      const { result, rerender } = renderHook(
        (props: UseBrowseDataParams) => useBrowseData(props),
        { initialProps: makeParams(initialUrlState) }
      )

      await vi.waitFor(() => {
        expect(result.current.fileContent).not.toBeNull()
      })

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
  })
})
