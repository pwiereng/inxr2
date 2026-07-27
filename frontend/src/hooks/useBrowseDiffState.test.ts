import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, type RenderHookResult } from '@testing-library/react'
import { useBrowseDiffState } from './useBrowseDiffState'
import type { UseBrowseDiffStateParams, UseBrowseDiffStateResult } from './useBrowseDiffState'
import type { BrowseUrlState } from './useBrowseTypes'
import * as api from '@/lib/api'
import { ApiError } from '@/lib/api'
import { consoleCallArgs, expectConsoleError } from '@/test/consoleGuard'

// The messages the hook logs before falling back to empty diff state.
const LOAD_FAILURE_LOG = 'Failed to load diff file:'
const RENAME_FAILURE_LOG = 'Failed to resolve rename or load content at resolved path:'

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof api>()
  return {
    ...actual,
    getFileContentByPathAtCommit: vi.fn(),
    getFileSymbolsByPath: vi.fn(),
    getFileReferencesByPath: vi.fn(),
    getFileHistory: vi.fn(),
    resolveFilePath: vi.fn(),
  }
})

const mockGetFileContentByPathAtCommit = vi.mocked(api.getFileContentByPathAtCommit)
const mockGetFileSymbolsByPath = vi.mocked(api.getFileSymbolsByPath)
const mockGetFileReferencesByPath = vi.mocked(api.getFileReferencesByPath)
const mockGetFileHistory = vi.mocked(api.getFileHistory)
const mockResolveFilePath = vi.mocked(api.resolveFilePath)

function makeUrlState(overrides: Partial<BrowseUrlState> = {}): BrowseUrlState {
  return {
    repoName: 'test-repo',
    filePath: 'src/new.py',
    directoryPath: null,
    highlightLine: undefined,
    selectedCommit: 'commit-b',
    diffCommit: 'commit-a',
    diffMode: true,
    selectedBranch: 'main',
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

function makeParams(urlState: BrowseUrlState): UseBrowseDiffStateParams {
  return {
    urlState,
    navigate: vi.fn(),
    refs: { fileVersionsRef: { current: [] } },
  }
}

async function renderDiffStateHook(
  initialProps: UseBrowseDiffStateParams
): Promise<RenderHookResult<UseBrowseDiffStateResult, UseBrowseDiffStateParams>> {
  let result: RenderHookResult<UseBrowseDiffStateResult, UseBrowseDiffStateParams>
  await act(async () => {
    result = renderHook((props: UseBrowseDiffStateParams) => useBrowseDiffState(props), {
      initialProps,
    })
    await new Promise((resolve) => setTimeout(resolve, 50))
  })
  return result!
}

const fileContentObj: api.FileContent = {
  id: 1,
  content: 'print("hello")',
  path: 'src/old.py',
  language: 'python',
  line_count: 1,
  size_bytes: 14,
}

const emptySymbols = { symbols: [], file_id: 1, file_path: 'src/old.py', total: 0 }
const emptyRefs = { references: [], file_id: 1, file_path: 'src/old.py', total: 0 }

describe('useBrowseDiffState', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockGetFileHistory.mockResolvedValue({
      versions: [],
      path: '',
      repository_name: '',
      total: 0,
    })
    mockGetFileSymbolsByPath.mockResolvedValue({ symbols: [], file_id: 1, file_path: '', total: 0 })
    mockGetFileReferencesByPath.mockResolvedValue({
      references: [],
      file_id: 1,
      file_path: '',
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

  describe('rename resolution on 404 (#240 Part 3)', () => {
    it('resolves rename and loads content at old path when diff commit returns 404', async () => {
      const renameInfo = {
        found: false,
        resolved_path: 'src/old.py',
        renamed_from: 'src/old.py',
        renamed_to: null,
        rename_commit_hash: 'commit-a',
      }
      mockGetFileContentByPathAtCommit
        // First call (new path at diff commit) → 404
        .mockRejectedValueOnce(new ApiError('Not Found', 404))
        // Second call (resolved old path at diff commit) → success
        .mockResolvedValueOnce(fileContentObj)
      mockGetFileSymbolsByPath.mockResolvedValue(emptySymbols)
      mockGetFileReferencesByPath.mockResolvedValue(emptyRefs)
      mockResolveFilePath.mockResolvedValue(renameInfo)

      const urlState = makeUrlState({
        filePath: 'src/new.py',
        diffCommit: 'commit-a',
        selectedBranch: 'main',
      })
      const { result } = await renderDiffStateHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.diffRenameInfo).toEqual(renameInfo)
      })
      expect(result.current.diffContent).toEqual(fileContentObj)
      expect(result.current.diffSymbols).toEqual([])
      expect(result.current.diffReferences).toEqual([])

      // resolveFilePath called with the new path and diff commit
      expect(mockResolveFilePath).toHaveBeenCalledWith(
        'test-repo',
        'src/new.py',
        'commit-a',
        'main'
      )
      // Content fetched at resolved (old) path
      expect(mockGetFileContentByPathAtCommit).toHaveBeenLastCalledWith(
        'test-repo',
        'src/old.py',
        'commit-a',
        undefined
      )
    })

    it('uses diffBranch for resolveFilePath when set', async () => {
      const renameInfo = {
        found: false,
        resolved_path: 'src/old.py',
        renamed_from: 'src/old.py',
        renamed_to: null,
        rename_commit_hash: 'commit-a',
      }
      mockGetFileContentByPathAtCommit
        .mockRejectedValueOnce(new ApiError('Not Found', 404))
        .mockResolvedValueOnce(fileContentObj)
      mockGetFileSymbolsByPath.mockResolvedValue(emptySymbols)
      mockGetFileReferencesByPath.mockResolvedValue(emptyRefs)
      mockResolveFilePath.mockResolvedValue(renameInfo)

      const urlState = makeUrlState({
        filePath: 'src/new.py',
        diffCommit: 'commit-a',
        diffBranch: 'feature',
        selectedBranch: 'main',
      })
      await renderDiffStateHook(makeParams(urlState))

      expect(mockResolveFilePath).toHaveBeenCalledWith(
        'test-repo',
        'src/new.py',
        'commit-a',
        'feature'
      )
    })

    it('does not attempt rename resolution when no diffCommit', async () => {
      mockGetFileContentByPathAtCommit.mockRejectedValue(new ApiError('Not Found', 404))

      const urlState = makeUrlState({
        diffCommit: null,
        diffBranch: 'feature',
      })
      const { result } = await renderDiffStateHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.diffLoading).toBe(false)
      })
      expect(mockResolveFilePath).not.toHaveBeenCalled()
      expect(result.current.diffRenameInfo).toBeNull()
      expect(result.current.diffContent).toBeNull()
    })

    it('does not attempt rename resolution for non-404 errors', async () => {
      // Declared for the suite-wide console guard; see consoleGuard.ts.
      expectConsoleError(LOAD_FAILURE_LOG, 'the hook logs the load error it recovers from')
      mockGetFileContentByPathAtCommit.mockRejectedValue(new ApiError('Internal Server Error', 500))

      const urlState = makeUrlState({ diffCommit: 'commit-a' })
      const { result } = await renderDiffStateHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.diffLoading).toBe(false)
      })
      expect(mockResolveFilePath).not.toHaveBeenCalled()
      expect(result.current.diffRenameInfo).toBeNull()
    })

    it('clears diffRenameInfo when rename resolution finds no resolved path', async () => {
      mockGetFileContentByPathAtCommit.mockRejectedValue(new ApiError('Not Found', 404))
      mockResolveFilePath.mockResolvedValue({
        found: false,
        resolved_path: null,
        renamed_from: null,
        renamed_to: null,
        rename_commit_hash: null,
      })

      const urlState = makeUrlState({ diffCommit: 'commit-a' })
      const { result } = await renderDiffStateHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.diffLoading).toBe(false)
      })
      expect(result.current.diffRenameInfo).toBeNull()
      expect(result.current.diffContent).toBeNull()
    })

    it('does not follow rename when resolveFilePath returns found: true', async () => {
      mockGetFileContentByPathAtCommit.mockRejectedValue(new ApiError('Not Found', 404))
      mockResolveFilePath.mockResolvedValue({
        found: true,
        resolved_path: 'src/old.py',
        renamed_from: null,
        renamed_to: null,
        rename_commit_hash: null,
      })

      const urlState = makeUrlState({ diffCommit: 'commit-a' })
      const { result } = await renderDiffStateHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.diffLoading).toBe(false)
      })
      // found: true means no rename needed — do not reload at resolved_path
      expect(mockGetFileContentByPathAtCommit).toHaveBeenCalledTimes(1)
      expect(result.current.diffRenameInfo).toBeNull()
      expect(result.current.diffContent).toBeNull()
    })

    it('logs unexpected errors from rename resolution attempt', async () => {
      expectConsoleError(
        RENAME_FAILURE_LOG,
        'the hook logs the rename-resolution error it swallows'
      )
      mockGetFileContentByPathAtCommit.mockRejectedValue(new ApiError('Not Found', 404))
      mockResolveFilePath.mockRejectedValue(new ApiError('Internal Server Error', 500))

      const urlState = makeUrlState({ diffCommit: 'commit-a' })
      const { result } = await renderDiffStateHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.diffLoading).toBe(false)
      })
      expect(consoleCallArgs('error')).toContainEqual([RENAME_FAILURE_LOG, expect.any(ApiError)])
      expect(result.current.diffRenameInfo).toBeNull()
    })

    it('clears diffRenameInfo on successful load (no rename)', async () => {
      const content: api.FileContent = {
        id: 2,
        content: 'x = 1',
        path: 'src/new.py',
        language: 'python',
        line_count: 1,
        size_bytes: 5,
      }
      mockGetFileContentByPathAtCommit.mockResolvedValue(content)
      mockGetFileSymbolsByPath.mockResolvedValue(emptySymbols)
      mockGetFileReferencesByPath.mockResolvedValue(emptyRefs)

      const urlState = makeUrlState({ diffCommit: 'commit-a' })
      const { result } = await renderDiffStateHook(makeParams(urlState))

      await vi.waitFor(() => {
        expect(result.current.diffContent).toEqual(content)
      })
      expect(result.current.diffRenameInfo).toBeNull()
      expect(mockResolveFilePath).not.toHaveBeenCalled()
    })
  })
})
