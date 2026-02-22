import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, RenderHookResult } from '@testing-library/react'
import { useBrowseState } from './useBrowseState'
import * as api from '@/lib/api'

/**
 * Helper to properly render hooks with async effects.
 *
 * The useBrowseState hook has multiple useEffect hooks that fire asynchronously,
 * causing state updates after initial render. Wrapping the entire render + settling
 * in act() ensures React properly handles all async updates without warnings.
 */
async function renderBrowseStateHook(): Promise<
  RenderHookResult<ReturnType<typeof useBrowseState>, unknown>
> {
  let result: RenderHookResult<ReturnType<typeof useBrowseState>, unknown>
  await act(async () => {
    result = renderHook(() => useBrowseState())
    // Allow time for all async effects to settle
    await new Promise((resolve) => setTimeout(resolve, 50))
  })
  return result!
}

// Mock react-router-dom
const mockNavigate = vi.fn()
const mockSetSearchParams = vi.fn()
let mockSearchParams = new URLSearchParams()

vi.mock('react-router-dom', () => ({
  useParams: () => ({ repoName: 'test-repo', '*': 'src/main.py' }),
  useNavigate: () => mockNavigate,
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
}))

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
  getSymbol: vi.fn(),
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

describe('useBrowseState', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    mockSetSearchParams.mockImplementation((updater) => {
      if (typeof updater === 'function') {
        mockSearchParams = updater(mockSearchParams)
      } else {
        mockSearchParams = updater
      }
    })

    // Default mock implementations
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
    mockGetFileHistory.mockResolvedValue({ versions: [], path: '', repository_name: '', total: 0 })
    mockGetFileContentByPathAtCommit.mockResolvedValue({
      id: 1,
      path: 'src/main.py',
      content: 'print("hello")',
      language: 'python',
      line_count: 1,
      size_bytes: 15,
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

  describe('URL state parsing', () => {
    it('should parse search query from URL', async () => {
      mockSearchParams = new URLSearchParams('q=MyClass')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.searchQuery).toBe('MyClass')
    })

    it('should default search query to empty string', async () => {
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.searchQuery).toBe('')
    })

    it('should parse drawer state from URL (closed)', async () => {
      mockSearchParams = new URLSearchParams('drawer=0')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.drawerOpen).toBe(false)
    })

    it('should default drawer to open', async () => {
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.drawerOpen).toBe(true)
    })

    it('should parse refs panel state from URL (open)', async () => {
      mockSearchParams = new URLSearchParams('refs=1')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.refsPanelOpen).toBe(true)
    })

    it('should default refs panel to closed', async () => {
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.refsPanelOpen).toBe(false)
    })

    it('should parse tree panel side from URL', async () => {
      mockSearchParams = new URLSearchParams('tp=r')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.treePanel).toBe('right')
    })

    it('should default tree panel to left', async () => {
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.treePanel).toBe('left')
    })

    it('should parse ref panel side from URL', async () => {
      mockSearchParams = new URLSearchParams('rp=r')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.refPanel).toBe('right')
    })

    it('should parse active panel from URL', async () => {
      mockSearchParams = new URLSearchParams('ap=r')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.activePanel).toBe('right')
    })

    it('should parse diff mode from URL', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.diffMode).toBe(true)
      expect(result.current.urlState.selectedCommit).toBe('abc123')
      expect(result.current.urlState.diffCommit).toBe('def456')
    })

    it('should parse highlight line from URL', async () => {
      mockSearchParams = new URLSearchParams('line=42')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.highlightLine).toBe(42)
    })

    it('should parse all params together', async () => {
      mockSearchParams = new URLSearchParams(
        'q=MyClass&refs=1&drawer=0&tp=r&rp=r&ap=r&commit=abc&diff=def&line=10'
      )
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState).toMatchObject({
        searchQuery: 'MyClass',
        refsPanelOpen: true,
        drawerOpen: false,
        treePanel: 'right',
        refPanel: 'right',
        activePanel: 'right',
        selectedCommit: 'abc',
        diffCommit: 'def',
        diffMode: true,
        highlightLine: 10,
      })
    })

    it('should parse changedOnly from URL (enabled)', async () => {
      mockSearchParams = new URLSearchParams('co=1')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.changedOnly).toBe(true)
    })

    it('should default changedOnly to false when not in URL', async () => {
      mockSearchParams = new URLSearchParams('')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.changedOnly).toBe(false)
    })

    it('should parse changedOnly with other params', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&co=1&branch=main')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.changedOnly).toBe(true)
      expect(result.current.urlState.selectedCommit).toBe('abc123')
      expect(result.current.urlState.selectedBranch).toBe('main')
    })

    it('should parse viewMode raw from URL', async () => {
      mockSearchParams = new URLSearchParams('view=raw')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.viewMode).toBe('raw')
    })

    it('should parse viewMode rendered from URL', async () => {
      mockSearchParams = new URLSearchParams('view=rendered')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.viewMode).toBe('rendered')
    })

    it('should default viewMode to null when not in URL', async () => {
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.viewMode).toBeNull()
    })

    it('should default viewMode to null for unknown values', async () => {
      mockSearchParams = new URLSearchParams('view=invalid')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.viewMode).toBeNull()
    })
  })

  describe('URL state updates', () => {
    it('should update search query in URL', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setSearchQuery('NewSearch')
      })

      expect(mockSetSearchParams).toHaveBeenCalled()
      expect(mockSearchParams.get('q')).toBe('NewSearch')
    })

    it('should remove search query from URL when empty', async () => {
      mockSearchParams = new URLSearchParams('q=OldSearch')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setSearchQuery('')
      })

      expect(mockSearchParams.has('q')).toBe(false)
    })

    it('should toggle drawer state in URL', async () => {
      const { result } = await renderBrowseStateHook()

      // Initially open (no drawer param)
      expect(result.current.urlState.drawerOpen).toBe(true)

      act(() => {
        result.current.actions.toggleDrawer()
      })

      expect(mockSearchParams.get('drawer')).toBe('0')
    })

    it('should update tree panel in URL', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setTreePanel('right')
      })

      expect(mockSearchParams.get('tp')).toBe('r')
    })

    it('should update ref panel in URL', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setRefPanel('right')
      })

      expect(mockSearchParams.get('rp')).toBe('r')
    })

    it('should update active panel in URL', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setActivePanel('right')
      })

      expect(mockSearchParams.get('ap')).toBe('r')
    })

    it('should set changedOnly in URL', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setChangedOnly(true)
      })

      expect(mockSearchParams.get('co')).toBe('1')
    })

    it('should remove changedOnly from URL when set to false', async () => {
      mockSearchParams = new URLSearchParams('co=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setChangedOnly(false)
      })

      expect(mockSearchParams.get('co')).toBeNull()
    })

    it('should toggle changedOnly on when currently off', async () => {
      mockSearchParams = new URLSearchParams('')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.toggleChangedOnly()
      })
      expect(mockSearchParams.get('co')).toBe('1')
    })

    it('should toggle changedOnly off when currently on', async () => {
      mockSearchParams = new URLSearchParams('co=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.toggleChangedOnly()
      })
      expect(mockSearchParams.get('co')).toBeNull()
    })

    it('should set viewMode to raw in URL', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setViewMode('raw')
      })

      expect(mockSearchParams.get('view')).toBe('raw')
    })

    it('should clear viewMode from URL when set to null', async () => {
      mockSearchParams = new URLSearchParams('view=raw')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.setViewMode(null)
      })

      expect(mockSearchParams.has('view')).toBe(false)
    })
  })

  describe('UI state exposure', () => {
    it('should expose drawer state through uiState', async () => {
      mockSearchParams = new URLSearchParams('drawer=0')
      const { result } = await renderBrowseStateHook()
      expect(result.current.uiState.drawerOpen).toBe(false)
    })

    it('should expose refs panel state through uiState', async () => {
      mockSearchParams = new URLSearchParams('refs=1')
      const { result } = await renderBrowseStateHook()
      expect(result.current.uiState.refsPanelOpen).toBe(true)
    })

    it('should expose search query through uiState', async () => {
      mockSearchParams = new URLSearchParams('q=Test')
      const { result } = await renderBrowseStateHook()
      expect(result.current.uiState.searchQuery).toBe('Test')
    })
  })

  describe('diff state exposure', () => {
    it('should expose panel states through diffState', async () => {
      mockSearchParams = new URLSearchParams('tp=r&rp=r&ap=r')
      const { result } = await renderBrowseStateHook()
      expect(result.current.diffState.treePanel).toBe('right')
      expect(result.current.diffState.refPanel).toBe('right')
      expect(result.current.diffState.activePanel).toBe('right')
    })
  })

  describe('backwards compatibility', () => {
    it('should work with no URL params (all defaults)', async () => {
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.searchQuery).toBe('')
      expect(result.current.urlState.drawerOpen).toBe(true)
      expect(result.current.urlState.refsPanelOpen).toBe(false)
      expect(result.current.urlState.treePanel).toBe('left')
      expect(result.current.urlState.refPanel).toBe('left')
      expect(result.current.urlState.activePanel).toBe('left')
      expect(result.current.urlState.diffMode).toBe(false)
    })

    it('should work with only legacy params (commit, line)', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&line=50')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.selectedCommit).toBe('abc123')
      expect(result.current.urlState.highlightLine).toBe(50)
      // All new params should have defaults
      expect(result.current.urlState.drawerOpen).toBe(true)
      expect(result.current.urlState.refsPanelOpen).toBe(false)
    })
  })

  describe('diff mode actions', () => {
    const mockVersions = [
      {
        commit_id: 1,
        commit_hash: 'abc123',
        short_hash: 'abc123',
        commit_date: '2024-01-03',
        message: 'Latest commit',
        content_hash: 'hash1',
      },
      {
        commit_id: 2,
        commit_hash: 'def456',
        short_hash: 'def456',
        commit_date: '2024-01-02',
        message: 'Previous commit',
        content_hash: 'hash2',
      },
      {
        commit_id: 3,
        commit_hash: 'ghi789',
        short_hash: 'ghi789',
        commit_date: '2024-01-01',
        message: 'Oldest commit',
        content_hash: 'hash3',
      },
    ]

    it('should enter diff mode by navigating with diff param', async () => {
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 3,
      })

      const { result } = await renderBrowseStateHook()

      // Wait for fileVersions to load
      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(3)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      // Should navigate with diff param set to the next version
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('diff=def456'))
    })

    it('should enter cross-branch diff mode when only one version exists', async () => {
      mockGetFileHistory.mockResolvedValue({
        versions: [mockVersions[0]!],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 1,
      })

      const { result } = await renderBrowseStateHook()

      // Wait for fileVersions to load
      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(1)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      // Should navigate with diffBranch for cross-branch comparison
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('diffBranch='))
      // Should NOT have a diff param (since no other version)
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toMatch(/[?&]diff=/)
    })

    it('should preserve drawer state but clear search context when entering diff mode', async () => {
      mockSearchParams = new URLSearchParams('drawer=0&refs=1&q=TestQuery&line=42')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 3,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(3)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      // Drawer state and line should be preserved
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringMatching(/drawer=0.*|.*drawer=0/))
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringMatching(/line=42.*|.*line=42/))
      // Search context should be cleared (not preserved)
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('refs=')
      expect(navigatedUrl).not.toContain('q=')
    })

    it('should exit diff mode and clear diff params', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 3,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(3)
      })

      act(() => {
        result.current.actions.exitDiffMode()
      })

      // Should navigate without diff param
      expect(mockNavigate).toHaveBeenCalled()
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('diff=')
    })

    it('should switch to right panel version when closing left panel', async () => {
      // In diff mode with left=abc123 (main) and right=def456 (feature branch)
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&diffBranch=feature')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 3,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(3)
      })

      act(() => {
        result.current.actions.closePanel('left')
      })

      // Should navigate to the right panel's version and branch
      expect(mockNavigate).toHaveBeenCalled()
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('commit=def456')
      expect(navigatedUrl).toContain('branch=feature')
      // Should not have diff params
      expect(navigatedUrl).not.toContain('diff=')
      expect(navigatedUrl).not.toContain('diffBranch=')
    })

    it('should preserve selectedBranch when closing left panel in same-branch diff mode', async () => {
      // Same-branch diff mode: diff param set, no diffBranch
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&branch=feature')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 3,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(3)
      })

      act(() => {
        result.current.actions.closePanel('left')
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      // Should fall back to selectedBranch since diffBranch is absent
      expect(navigatedUrl).toContain('branch=feature')
    })

    it('should switch to left panel version when closing right panel', async () => {
      // In diff mode with left=abc123 (main) and right=def456 (feature branch)
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&branch=main')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 3,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(3)
      })

      act(() => {
        result.current.actions.closePanel('right')
      })

      // Should keep the left panel's version (exit diff mode)
      expect(mockNavigate).toHaveBeenCalled()
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('commit=abc123')
      expect(navigatedUrl).toContain('branch=main')
      // Should not have diff params
      expect(navigatedUrl).not.toContain('diff=')
    })
  })

  describe('version change actions', () => {
    const mockVersions = [
      {
        commit_id: 1,
        commit_hash: 'abc123',
        short_hash: 'abc123',
        commit_date: '2024-01-03',
        message: 'Latest commit',
        content_hash: 'hash1',
      },
      {
        commit_id: 2,
        commit_hash: 'def456',
        short_hash: 'def456',
        commit_date: '2024-01-02',
        message: 'Previous commit',
        content_hash: 'hash2',
      },
    ]

    it('should change version by navigating with commit param', async () => {
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.changeVersion('def456')
      })

      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('commit=def456'))
    })

    it('should preserve drawer state but clear search context when changing version', async () => {
      mockSearchParams = new URLSearchParams('drawer=0&q=TestQuery')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.changeVersion('def456')
      })

      // Drawer state should be preserved
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringMatching(/drawer=0.*|.*drawer=0/))
      // Search context should be cleared (not preserved)
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('q=')
    })

    it('should clear commit param when changing to null (latest)', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.changeVersion(null)
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('commit=')
    })

    it('should change diff version by updating diff param', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.changeDiffVersion('ghi789')
      })

      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('diff=ghi789'))
    })

    it('should clear refs panel state when changing version', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      // Verify refs panel is initially open from URL
      expect(result.current.urlState.refsPanelOpen).toBe(true)

      act(() => {
        result.current.actions.changeVersion('def456')
      })

      // Should navigate without refs param (refs panel closed)
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('refs=')

      // Verify navigate builds URL without refs (this is the key behavior)
      // Note: In real usage, navigation would change the URL and refs panel
      // would close. In tests with mocks, the URL doesn't actually change,
      // so the refs restoration effect may re-set searchByName.
      expect(result.current.refsState.selectedSymbol).toBeNull()
    })

    it('should only use navigate (not setSearchParams) when changing version to avoid race conditions', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      // Clear any previous calls from initialization
      mockSetSearchParams.mockClear()
      mockNavigate.mockClear()

      act(() => {
        result.current.actions.changeVersion('def456')
      })

      // Should use navigate, NOT setSearchParams, to avoid race conditions
      expect(mockNavigate).toHaveBeenCalledTimes(1)
      // setSearchParams should NOT be called during version change
      // (URL updates should be done via navigate only)
      expect(mockSetSearchParams).not.toHaveBeenCalled()
    })

    it('should only use navigate (not setSearchParams) when changing diff version', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&refs=1')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      // Clear any previous calls from initialization
      mockSetSearchParams.mockClear()
      mockNavigate.mockClear()

      act(() => {
        result.current.actions.changeDiffVersion('ghi789')
      })

      // Should use navigate, NOT setSearchParams, to avoid race conditions
      expect(mockNavigate).toHaveBeenCalledTimes(1)
      expect(mockSetSearchParams).not.toHaveBeenCalled()
    })
  })

  describe('closeRefsPanel action', () => {
    it('should clear refs panel React state', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')

      const { result } = await renderBrowseStateHook()

      expect(result.current.urlState.refsPanelOpen).toBe(true)

      act(() => {
        result.current.actions.closeRefsPanel()
      })

      // Should clear React state
      expect(result.current.refsState.selectedSymbol).toBeNull()
      expect(result.current.refsState.searchByName).toBeNull()
      expect(result.current.refsState.isDirectDefinition).toBe(false)
    })

    it('should remove refs param from URL', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')

      const { result } = await renderBrowseStateHook()

      expect(result.current.urlState.refsPanelOpen).toBe(true)

      act(() => {
        result.current.actions.closeRefsPanel()
      })

      // Should have called setSearchParams to remove refs
      expect(mockSetSearchParams).toHaveBeenCalled()
      expect(mockSearchParams.has('refs')).toBe(false)
    })

    it('should preserve search query when closing refs panel', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')

      const { result } = await renderBrowseStateHook()

      expect(result.current.urlState.refsPanelOpen).toBe(true)
      expect(result.current.urlState.searchQuery).toBe('TestSymbol')

      act(() => {
        result.current.actions.closeRefsPanel()
      })

      // Should preserve q param (search query is independent of refs panel)
      expect(mockSearchParams.get('q')).toBe('TestSymbol')
    })
  })

  describe('refs panel restoration from URL', () => {
    it('should initialize searchByName from URL when refs panel is open', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')

      const { result } = await renderBrowseStateHook()

      // Wait for repository to load and restoration effect to run
      await vi.waitFor(() => {
        expect(result.current.dataState.repository).not.toBeNull()
      })

      // The restoration effect should have set searchByName
      await vi.waitFor(() => {
        expect(result.current.refsState.searchByName).toEqual({
          name: 'TestSymbol',
          repositoryId: 1,
        })
      })
    })

    it('should not restore if refs panel is closed', async () => {
      // refs=0 or no refs param means closed
      mockSearchParams = new URLSearchParams('q=TestSymbol')

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.repository).not.toBeNull()
      })

      // Give time for any effects to run
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should NOT set searchByName since refs panel is closed
      expect(result.current.refsState.searchByName).toBeNull()
    })

    it('should not restore if no search query in URL', async () => {
      mockSearchParams = new URLSearchParams('refs=1')

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.repository).not.toBeNull()
      })

      // Give time for any effects to run
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should NOT set searchByName since there's no query
      expect(result.current.refsState.searchByName).toBeNull()
    })

    it('should not restore if searchByName is already set', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.repository).not.toBeNull()
      })

      // First restoration happens
      await vi.waitFor(() => {
        expect(result.current.refsState.searchByName).toEqual({
          name: 'TestSymbol',
          repositoryId: 1,
        })
      })

      // Manually set a different searchByName
      act(() => {
        result.current.actions.openRefsPanelByName('DifferentSymbol', 1)
      })

      // Should have the new value, not reverted to URL value
      expect(result.current.refsState.searchByName).toEqual({
        name: 'DifferentSymbol',
        repositoryId: 1,
      })
    })
  })

  describe('navigateToSymbol action', () => {
    const mockSymbol = {
      id: 123,
      name: '__init__',
      qualified_name: 'MyClass.__init__',
      kind: 'method',
      file_id: 1,
      file_path: 'src/myclass.py',
      repository_id: 1,
      commit_id: 1,
      start_line: 42,
      start_column: 4,
      end_line: 50,
      end_column: 0,
      signature: 'def __init__(self)',
      docstring: null,
    }

    it('should navigate to symbol file and open refs panel', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToSymbol(mockSymbol)
      })

      // Should navigate to the symbol's file with line number
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('src/myclass.py'))
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('line=42'))

      // Should open refs panel (refs=1 in URL)
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('refs=1'))

      // Should include symbol name in search query
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('q=__init__'))
    })

    it('should set refs panel state when navigating to symbol', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToSymbol(mockSymbol)
      })

      // Should set selectedSymbol
      expect(result.current.refsState.selectedSymbol).toEqual(mockSymbol)
      // Should clear searchByName (using full symbol instead)
      expect(result.current.refsState.searchByName).toBeNull()
      // Should mark as direct definition
      expect(result.current.refsState.isDirectDefinition).toBe(true)
    })

    it('should open refs panel by name when symbol has no file_path', async () => {
      const symbolWithoutPath = {
        ...mockSymbol,
        file_path: null,
      }

      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToSymbol(symbolWithoutPath)
      })

      // Should NOT navigate (no file_path)
      expect(mockNavigate).not.toHaveBeenCalled()

      // Should use updateUrlParams to open refs panel
      expect(mockSetSearchParams).toHaveBeenCalled()
      expect(mockSearchParams.get('refs')).toBe('1')
      expect(mockSearchParams.get('q')).toBe('__init__')
    })

    it('should preserve drawer state when navigating', async () => {
      mockSearchParams = new URLSearchParams('drawer=0')

      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToSymbol(mockSymbol)
      })

      // Should preserve drawer=0 in navigation
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('drawer=0'))
    })
  })

  describe('branch URL state', () => {
    it('should parse branch from URL', async () => {
      mockSearchParams = new URLSearchParams('branch=feature')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.selectedBranch).toBe('feature')
    })

    it('should default branch to null when not in URL', async () => {
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.selectedBranch).toBeNull()
    })

    it('should parse diffBranch from URL', async () => {
      mockSearchParams = new URLSearchParams('branch=main&diffBranch=feature')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.diffBranch).toBe('feature')
    })

    it('should default diffBranch to null when not in URL', async () => {
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.diffBranch).toBeNull()
    })

    it('should parse branch with other params', async () => {
      mockSearchParams = new URLSearchParams('q=MyClass&refs=1&branch=develop&commit=abc123')
      const { result } = await renderBrowseStateHook()
      expect(result.current.urlState.selectedBranch).toBe('develop')
      expect(result.current.urlState.searchQuery).toBe('MyClass')
      expect(result.current.urlState.refsPanelOpen).toBe(true)
      expect(result.current.urlState.selectedCommit).toBe('abc123')
    })
  })

  describe('branch change actions', () => {
    it('should change branch by navigating with branch param', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.changeBranch('feature')
      })

      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('branch=feature'))
    })

    it('should remove branch param when changing to null (default)', async () => {
      mockSearchParams = new URLSearchParams('branch=feature')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.changeBranch(null)
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('branch=')
    })

    it('should clear commit when changing branch', async () => {
      mockSearchParams = new URLSearchParams('branch=main&commit=abc123')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.changeBranch('feature')
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('commit=')
      expect(navigatedUrl).toContain('branch=feature')
    })

    it('should preserve drawer state when changing branch', async () => {
      mockSearchParams = new URLSearchParams('drawer=0&branch=main')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.changeBranch('feature')
      })

      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('drawer=0'))
    })

    it('should change diffBranch by navigating with diffBranch param', async () => {
      mockSearchParams = new URLSearchParams('branch=main&diff=abc123')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.changeDiffBranch('feature')
      })

      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('diffBranch=feature'))
    })

    it('should remove diffBranch param when changing to null', async () => {
      mockSearchParams = new URLSearchParams('diffBranch=feature')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.changeDiffBranch(null)
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('diffBranch=')
    })
  })

  describe('branch preservation in navigation', () => {
    it('should preserve branch when navigating to file', async () => {
      mockSearchParams = new URLSearchParams('branch=feature')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToFile('src/other.py')
      })

      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('branch=feature'))
    })

    it('should preserve branch when entering diff mode', async () => {
      mockSearchParams = new URLSearchParams('branch=feature')
      mockGetFileHistory.mockResolvedValue({
        versions: [
          {
            commit_id: 1,
            commit_hash: 'abc123',
            short_hash: 'abc123',
            commit_date: '2024-01-03',
            message: 'Latest',
            content_hash: 'hash1',
          },
          {
            commit_id: 2,
            commit_hash: 'def456',
            short_hash: 'def456',
            commit_date: '2024-01-02',
            message: 'Previous',
            content_hash: 'hash2',
          },
        ],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('branch=feature'))
    })

    it('should preserve branch when changing version', async () => {
      mockSearchParams = new URLSearchParams('branch=feature')
      mockGetFileHistory.mockResolvedValue({
        versions: [
          {
            commit_id: 1,
            commit_hash: 'abc123',
            short_hash: 'abc123',
            commit_date: '2024-01-03',
            message: 'Latest',
            content_hash: 'hash1',
          },
          {
            commit_id: 2,
            commit_hash: 'def456',
            short_hash: 'def456',
            commit_date: '2024-01-02',
            message: 'Previous',
            content_hash: 'hash2',
          },
        ],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.changeVersion('def456')
      })

      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('branch=feature'))
    })
  })

  describe('handleRefPanelClick in diff mode', () => {
    it('should use diffCommit when refPanel is right', async () => {
      // In diff mode with refs panel showing the right (diff) side
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&rp=r&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleRefPanelClick({
          source_file_path: 'src/other.py',
          source_line: 42,
        })
      })

      // Should navigate with diffCommit (def456), not selectedCommit
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('commit=def456'))
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('line=42'))
    })

    it('should use selectedCommit when refPanel is left', async () => {
      // In diff mode with refs panel showing the left (selected) side
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleRefPanelClick({
          source_file_path: 'src/other.py',
          source_line: 42,
        })
      })

      // Should navigate with selectedCommit (abc123), not diffCommit
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('commit=abc123'))
    })

    it('should use refPanel not activePanel to determine commit', async () => {
      // Bug regression test: activePanel is right (user last clicked right panel),
      // but refPanel is left (references are for left panel's code).
      // Should use left side's commit.
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&ap=r&refs=1')
      const { result } = await renderBrowseStateHook()

      // Verify initial state: activePanel is right, refPanel is left
      expect(result.current.urlState.activePanel).toBe('right')
      expect(result.current.urlState.refPanel).toBe('left')

      act(() => {
        result.current.actions.handleRefPanelClick({
          source_file_path: 'src/other.py',
          source_line: 42,
        })
      })

      // Should use selectedCommit (abc123) because refPanel is 'left',
      // even though activePanel is 'right'
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('commit=abc123'))
    })

    it('should preserve diffBranch when refPanel is right', async () => {
      // Bug regression test: when viewing references for the right (diff) panel
      // which is on a different branch, clicking should navigate to that branch
      mockSearchParams = new URLSearchParams('commit=abc123&diffBranch=feature-branch&rp=r&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleRefPanelClick({
          source_file_path: 'src/other.py',
          source_line: 42,
        })
      })

      // Should navigate with diffBranch preserved
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('branch=feature-branch'))
    })

    it('should preserve selectedBranch when refPanel is left', async () => {
      // When viewing references for the left panel on a specific branch
      mockSearchParams = new URLSearchParams('branch=develop&diffBranch=feature&rp=l&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleRefPanelClick({
          source_file_path: 'src/other.py',
          source_line: 42,
        })
      })

      // Should navigate with selectedBranch (develop), not diffBranch
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('branch=develop'))
      expect(mockNavigate).not.toHaveBeenCalledWith(expect.stringContaining('branch=feature'))
    })

    it('should fall back to selectedBranch when refPanel is right in same-branch diff mode', async () => {
      // Same-branch diff mode: diff param set, no diffBranch, refPanel on right
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&branch=feature&rp=r&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleRefPanelClick({
          source_file_path: 'src/other.py',
          source_line: 42,
        })
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      // Should fall back to selectedBranch since diffBranch is absent
      expect(navigatedUrl).toContain('branch=feature')
    })
  })

  describe('handleDefinitionClick in diff mode', () => {
    const mockSymbol = {
      id: 123,
      name: 'TestClass',
      qualified_name: 'module.TestClass',
      kind: 'class',
      file_id: 1,
      file_path: 'src/target.py',
      repository_id: 1,
      commit_id: 1,
      start_line: 10,
      start_column: 0,
      end_line: 50,
      end_column: 0,
      signature: null,
      docstring: null,
    }

    it('should use diffCommit when refPanel is right', async () => {
      // In diff mode with refs panel showing the right (diff) side
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&rp=r&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleDefinitionClick(mockSymbol)
      })

      // Should navigate with diffCommit (def456), not selectedCommit
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('commit=def456'))
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('line=10'))
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('src/target.py'))
    })

    it('should use selectedCommit when refPanel is left', async () => {
      // In diff mode with refs panel showing the left (selected) side
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleDefinitionClick(mockSymbol)
      })

      // Should navigate with selectedCommit (abc123), not diffCommit
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('commit=abc123'))
    })

    it('should use refPanel not activePanel to determine commit', async () => {
      // Bug regression test: activePanel is right (user last clicked right panel),
      // but refPanel is left (references are for left panel's code).
      // Should use left side's commit.
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&ap=r&refs=1')
      const { result } = await renderBrowseStateHook()

      // Verify initial state: activePanel is right, refPanel is left
      expect(result.current.urlState.activePanel).toBe('right')
      expect(result.current.urlState.refPanel).toBe('left')

      act(() => {
        result.current.actions.handleDefinitionClick(mockSymbol)
      })

      // Should use selectedCommit (abc123) because refPanel is 'left',
      // even though activePanel is 'right'
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('commit=abc123'))
    })

    it('should not navigate if symbol has no file_path', async () => {
      const symbolWithoutPath = { ...mockSymbol, file_path: null }
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleDefinitionClick(symbolWithoutPath)
      })

      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('should preserve diffBranch when refPanel is right', async () => {
      // Bug regression test: when viewing definition for the right (diff) panel
      // which is on a different branch, clicking should navigate to that branch
      mockSearchParams = new URLSearchParams('commit=abc123&diffBranch=feature-branch&rp=r&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleDefinitionClick(mockSymbol)
      })

      // Should navigate with diffBranch preserved
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('branch=feature-branch'))
    })

    it('should preserve selectedBranch when refPanel is left', async () => {
      // When viewing definition for the left panel on a specific branch
      mockSearchParams = new URLSearchParams('branch=develop&diffBranch=feature&rp=l&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleDefinitionClick(mockSymbol)
      })

      // Should navigate with selectedBranch (develop), not diffBranch
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('branch=develop'))
      expect(mockNavigate).not.toHaveBeenCalledWith(expect.stringContaining('branch=feature'))
    })

    it('should fall back to selectedBranch when refPanel is right in same-branch diff mode', async () => {
      // Same-branch diff mode: diff param set, no diffBranch, refPanel on right
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&branch=feature&rp=r&refs=1')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleDefinitionClick(mockSymbol)
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      // Should fall back to selectedBranch since diffBranch is absent
      expect(navigatedUrl).toContain('branch=feature')
    })
  })

  describe('file path encoding', () => {
    it('should encode special characters in file paths when navigating to file', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToFile('src/my file.ts')
      })

      // Space should be encoded as %20
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('src/my%20file.ts'))
    })

    it('should encode hash and question mark in file paths', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToFile('src/file#1.ts')
      })

      // Hash should be encoded as %23
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('src/file%231.ts'))
    })

    it('should preserve directory separators when encoding file paths', async () => {
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToFile('src/components/MyComponent.tsx')
      })

      // Slashes should NOT be encoded
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('src/components/MyComponent.tsx')
      )
      // Should not contain encoded slashes
      expect(mockNavigate).not.toHaveBeenCalledWith(expect.stringContaining('%2F'))
    })

    it('should encode special characters in symbol file paths', async () => {
      const symbolWithSpecialPath = {
        id: 123,
        name: 'TestSymbol',
        qualified_name: 'module.TestSymbol',
        kind: 'function',
        file_id: 1,
        file_path: 'src/my file.py',
        repository_id: 1,
        commit_id: 1,
        start_line: 10,
        start_column: 0,
        end_line: 20,
        end_column: 0,
        signature: null,
        docstring: null,
      }

      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToSymbol(symbolWithSpecialPath)
      })

      // Space should be encoded
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('src/my%20file.py'))
    })
  })

  describe('resetToFileTree action', () => {
    it('should navigate to repo root preserving branch, drawer, and changedOnly', async () => {
      mockSearchParams = new URLSearchParams(
        'branch=feature&drawer=0&co=1&commit=abc123&line=42&refs=1&q=MyClass'
      )
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.resetToFileTree()
      })

      expect(mockNavigate).toHaveBeenCalled()
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      // Should navigate to repo root (no file path)
      expect(navigatedUrl).toMatch(/^\/browse\/test-repo\?/)
      expect(navigatedUrl).not.toContain('src/main.py')
      // Should preserve branch, drawer, changedOnly
      expect(navigatedUrl).toContain('branch=feature')
      expect(navigatedUrl).toContain('drawer=0')
      expect(navigatedUrl).toContain('co=1')
      // Should NOT preserve line, commit, diff, refs, search query
      expect(navigatedUrl).not.toContain('line=')
      expect(navigatedUrl).not.toContain('commit=')
      expect(navigatedUrl).not.toContain('refs=')
      expect(navigatedUrl).not.toContain('q=')
    })

    it('should clear line, commit, diff, refs, and search params', async () => {
      mockSearchParams = new URLSearchParams(
        'commit=abc123&diff=def456&line=10&refs=1&q=Test&tp=r&rp=r&ap=r&diffBranch=other'
      )
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.resetToFileTree()
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('commit=')
      expect(navigatedUrl).not.toContain('diff=')
      expect(navigatedUrl).not.toContain('line=')
      expect(navigatedUrl).not.toContain('refs=')
      expect(navigatedUrl).not.toContain('q=')
      expect(navigatedUrl).not.toContain('tp=')
      expect(navigatedUrl).not.toContain('rp=')
      expect(navigatedUrl).not.toContain('ap=')
      expect(navigatedUrl).not.toContain('diffBranch=')
    })

    it('should reset refs panel state and navigate without refs params', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')
      const { result } = await renderBrowseStateHook()

      // Wait for repository to load
      await vi.waitFor(() => {
        expect(result.current.dataState.repository).not.toBeNull()
      })

      act(() => {
        result.current.actions.resetToFileTree()
      })

      // Should clear selectedSymbol
      expect(result.current.refsState.selectedSymbol).toBeNull()
      // Navigate URL should not contain refs or q params
      // (Note: in tests, the URL doesn't actually change so the refs restoration
      // effect may re-set searchByName. In real usage, navigation would change the
      // URL and refs panel would close. Verify via navigate call.)
      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('refs=')
      expect(navigatedUrl).not.toContain('q=')
    })

    it('should navigate to repo root with no params when defaults are used', async () => {
      mockSearchParams = new URLSearchParams('')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.resetToFileTree()
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      // Should navigate to bare repo root with no query string
      expect(navigatedUrl).toBe('/browse/test-repo')
    })
  })

  describe('fileChangedInCommit computed state', () => {
    const mockVersions = [
      {
        commit_id: 1,
        commit_hash: 'abc123',
        short_hash: 'abc123',
        commit_date: '2024-01-03',
        message: 'Latest commit',
        content_hash: 'hash1',
      },
      {
        commit_id: 2,
        commit_hash: 'def456',
        short_hash: 'def456',
        commit_date: '2024-01-02',
        message: 'Previous commit',
        content_hash: 'hash2',
      },
    ]

    it('should be true when selectedCommit is in fileVersions', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      expect(result.current.computedState.fileChangedInCommit).toBe(true)
    })

    it('should be false when selectedCommit is not in fileVersions', async () => {
      mockSearchParams = new URLSearchParams('commit=xyz999')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      expect(result.current.computedState.fileChangedInCommit).toBe(false)
    })

    it('should be true when no selectedCommit (viewing latest)', async () => {
      mockSearchParams = new URLSearchParams('')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      // No selectedCommit means viewing latest, so file is considered "changed"
      expect(result.current.computedState.fileChangedInCommit).toBe(true)
    })
  })

  describe('changedOnly preservation', () => {
    it('should preserve co=1 in URL when navigating to a file with changedOnly enabled', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&co=1&branch=main')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToFile('src/other.py')
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('co=1')
      expect(navigatedUrl).toContain('commit=abc123')
      expect(navigatedUrl).toContain('branch=main')
    })

    it('should not include co param when changedOnly is false', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToFile('src/other.py')
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('co=')
    })

    it('should preserve co=1 when entering diff mode', async () => {
      mockSearchParams = new URLSearchParams('co=1&branch=main')
      const mockVersions = [
        {
          commit_id: 1,
          commit_hash: 'abc123',
          short_hash: 'abc123',
          commit_date: '2024-01-02',
          message: 'Latest',
          content_hash: 'hash1',
        },
        {
          commit_id: 2,
          commit_hash: 'def456',
          short_hash: 'def456',
          commit_date: '2024-01-01',
          message: 'Previous',
          content_hash: 'hash2',
        },
      ]
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('co=1')
      expect(navigatedUrl).toContain('diff=def456')
    })

    it('should preserve co=1 when exiting diff mode', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&co=1&branch=main')
      mockGetFileHistory.mockResolvedValue({
        versions: [],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 0,
      })

      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.exitDiffMode()
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('co=1')
      expect(navigatedUrl).not.toContain('diff=')
    })

    it('should not include co param when entering diff mode with changedOnly false', async () => {
      mockSearchParams = new URLSearchParams('branch=main')
      const mockVersions = [
        {
          commit_id: 1,
          commit_hash: 'abc123',
          short_hash: 'abc123',
          commit_date: '2024-01-02',
          message: 'Latest',
          content_hash: 'hash1',
        },
        {
          commit_id: 2,
          commit_hash: 'def456',
          short_hash: 'def456',
          commit_date: '2024-01-01',
          message: 'Previous',
          content_hash: 'hash2',
        },
      ]
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).not.toContain('co=')
    })

    it('should preserve co=1 when changing diff version', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&co=1&branch=main')
      mockGetFileHistory.mockResolvedValue({
        versions: [],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 0,
      })

      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.changeDiffVersion('ghi789')
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('co=1')
      expect(navigatedUrl).toContain('diff=ghi789')
    })

    it('should preserve co=1 when changing diff branch', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diffBranch=main&co=1&branch=main')
      mockGetFileHistory.mockResolvedValue({
        versions: [],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 0,
      })

      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.changeDiffBranch('feature')
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('co=1')
      expect(navigatedUrl).toContain('diffBranch=feature')
    })

    it('should preserve co=1 when navigating to a line', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&co=1&branch=main')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.navigateToLine(42)
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('co=1')
      expect(navigatedUrl).toContain('line=42')
    })

    it('should preserve co=1 when clicking a diff line', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456&co=1&branch=main')
      const { result } = await renderBrowseStateHook()

      act(() => {
        result.current.actions.handleDiffLineClick(10, 'right')
      })

      const navigatedUrl = mockNavigate.mock.calls[0]?.[0] as string
      expect(navigatedUrl).toContain('co=1')
      expect(navigatedUrl).toContain('line=10')
    })

    it('should clear file selection when changedOnly is on and file is not in tree', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&co=1')

      // Return a tree that does NOT contain the current file (src/main.py)
      mockGetRepositoryTreeByName.mockResolvedValue({
        root: [
          {
            name: 'changed.py',
            path: 'src/changed.py',
            type: 'file',
            file_id: 1,
            language: 'python',
            children: null,
          },
        ],
        repository_id: 1,
        repository_name: 'test-repo',
        total_files: 1,
        total_directories: 0,
      })

      const { result } = await renderBrowseStateHook()

      // Wait for tree to load
      await vi.waitFor(() => {
        expect(result.current.dataState.treeNodes.length).toBe(1)
      })

      // The useEffect should have called navigate to clear the file path
      await vi.waitFor(() => {
        const navCalls = mockNavigate.mock.calls
        const clearCall = navCalls.find(
          (call) => typeof call[0] === 'string' && !call[0].includes('src/main.py')
        )
        expect(clearCall).toBeDefined()
      })

      // The clearing navigation should go to the repo root (no file path)
      const clearCall = mockNavigate.mock.calls.find(
        (call) => typeof call[0] === 'string' && !call[0].includes('src/main.py')
      )
      expect(clearCall![0]).toContain('/browse/test-repo')
    })

    it('should not clear file selection when file is in the changed-files tree', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&co=1')

      // Return a tree that DOES contain the current file (src/main.py)
      mockGetRepositoryTreeByName.mockResolvedValue({
        root: [
          {
            name: 'main.py',
            path: 'src/main.py',
            type: 'file',
            file_id: 1,
            language: 'python',
            children: null,
          },
          {
            name: 'other.py',
            path: 'src/other.py',
            type: 'file',
            file_id: 2,
            language: 'python',
            children: null,
          },
        ],
        repository_id: 1,
        repository_name: 'test-repo',
        total_files: 2,
        total_directories: 0,
      })

      mockNavigate.mockClear()
      const { result } = await renderBrowseStateHook()

      // Wait for tree to load
      await vi.waitFor(() => {
        expect(result.current.dataState.treeNodes.length).toBe(2)
      })

      // Give time for effects to settle
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Navigate should NOT have been called to clear the file
      // (it may have been called for other reasons during init, so check
      // that no call removes the file path)
      const clearCalls = mockNavigate.mock.calls.filter(
        (call) =>
          typeof call[0] === 'string' &&
          call[0].includes('/browse/test-repo') &&
          !call[0].includes('src/main.py')
      )
      expect(clearCalls.length).toBe(0)
    })

    it('should not clear file selection when changedOnly is off', async () => {
      // No co=1 param — changedOnly is false
      mockSearchParams = new URLSearchParams('commit=abc123')

      // Return a tree that does NOT contain the current file
      mockGetRepositoryTreeByName.mockResolvedValue({
        root: [
          {
            name: 'changed.py',
            path: 'src/changed.py',
            type: 'file',
            file_id: 1,
            language: 'python',
            children: null,
          },
        ],
        repository_id: 1,
        repository_name: 'test-repo',
        total_files: 1,
        total_directories: 0,
      })

      mockNavigate.mockClear()
      const { result } = await renderBrowseStateHook()

      // Wait for tree to load
      await vi.waitFor(() => {
        expect(result.current.dataState.treeNodes.length).toBe(1)
      })

      // Give time for effects to settle
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Navigate should NOT have been called to clear the file since changedOnly is off
      const clearCalls = mockNavigate.mock.calls.filter(
        (call) =>
          typeof call[0] === 'string' &&
          call[0].includes('/browse/test-repo') &&
          !call[0].includes('src/main.py')
      )
      expect(clearCalls.length).toBe(0)
    })

    it('should find files in nested tree directories', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&co=1')

      // Return a nested tree where the file is inside a directory
      mockGetRepositoryTreeByName.mockResolvedValue({
        root: [
          {
            name: 'src',
            path: 'src',
            type: 'directory',
            file_id: null,
            language: null,
            children: [
              {
                name: 'main.py',
                path: 'src/main.py',
                type: 'file',
                file_id: 1,
                language: 'python',
                children: null,
              },
            ],
          },
        ],
        repository_id: 1,
        repository_name: 'test-repo',
        total_files: 1,
        total_directories: 1,
      })

      mockNavigate.mockClear()
      const { result } = await renderBrowseStateHook()

      // Wait for tree to load
      await vi.waitFor(() => {
        expect(result.current.dataState.treeNodes.length).toBe(1)
      })

      // Give time for effects to settle
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Navigate should NOT have been called to clear the file since it IS in the tree (nested)
      const clearCalls = mockNavigate.mock.calls.filter(
        (call) =>
          typeof call[0] === 'string' &&
          call[0].includes('/browse/test-repo') &&
          !call[0].includes('src/main.py')
      )
      expect(clearCalls.length).toBe(0)
    })
  })

  describe('leftCommit uses latestBranchCommit fallback', () => {
    it('should use latestBranchCommit for leftCommit when no selectedCommit', async () => {
      // Regression: leftCommit fell through to fileVersions[0].commit_hash,
      // which could differ from the branch HEAD shown in the header.
      mockSearchParams = new URLSearchParams('branch=feature')

      // latestBranchCommit comes from getCommits — return branch HEAD commit
      mockGetCommits.mockResolvedValue({
        commits: [
          {
            hash: 'branch-head-abc',
            short_hash: 'branch',
            message: 'Branch HEAD commit',
            author_name: 'Test',
            author_email: 'test@test.com',
            commit_date: '2024-01-03',
            is_indexed: true,
            tags: [],
            is_branch_specific: true,
            is_merge_base: false,
          },
        ],
        total: 1,
      })

      // fileVersions[0] is a different commit (latest that modified the file)
      mockGetFileHistory.mockResolvedValue({
        versions: [
          {
            commit_id: 5,
            commit_hash: 'file-version-xyz',
            short_hash: 'file-v',
            commit_date: '2024-01-02',
            message: 'Last file change',
            content_hash: 'hash1',
          },
        ],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 1,
      })

      const { result } = await renderBrowseStateHook()

      // Wait for latestBranchCommit to resolve
      await vi.waitFor(() => {
        expect(result.current.computedState.leftCommit).toBe('branch-head-abc')
      })

      // leftCommit should be the branch HEAD, NOT the file version
      expect(result.current.computedState.leftCommit).not.toBe('file-version-xyz')
    })

    it('should use latestBranchCommit for treeCommit in diff mode when treePanel is left', async () => {
      // In diff mode with treePanel=left, treeCommit = leftCommit.
      // leftCommit should use latestBranchCommit (branch HEAD), not fileVersions[0].
      mockSearchParams = new URLSearchParams('diff=other-commit&branch=feature&co=1')

      mockGetCommits.mockResolvedValue({
        commits: [
          {
            hash: 'branch-head-abc',
            short_hash: 'branch',
            message: 'Branch HEAD commit',
            author_name: 'Test',
            author_email: 'test@test.com',
            commit_date: '2024-01-03',
            is_indexed: true,
            tags: [],
            is_branch_specific: true,
            is_merge_base: false,
          },
        ],
        total: 1,
      })

      mockGetFileHistory.mockResolvedValue({
        versions: [
          {
            commit_id: 5,
            commit_hash: 'file-version-xyz',
            short_hash: 'file-v',
            commit_date: '2024-01-02',
            message: 'Last file change',
            content_hash: 'hash1',
          },
        ],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 1,
      })

      const { result } = await renderBrowseStateHook()

      // Wait for latestBranchCommit to resolve
      await vi.waitFor(() => {
        expect(result.current.computedState.leftCommit).toBe('branch-head-abc')
      })

      // In diff mode with treePanel=left (default), treeCommit should equal leftCommit
      expect(result.current.computedState.treeCommit).toBe('branch-head-abc')
    })

    it('should still use selectedCommit for leftCommit when explicitly set', async () => {
      // When a specific commit is selected, it should take priority over latestBranchCommit
      mockSearchParams = new URLSearchParams('commit=explicit-commit&branch=feature')

      mockGetCommits.mockResolvedValue({
        commits: [
          {
            hash: 'branch-head-abc',
            short_hash: 'branch',
            message: 'Branch HEAD commit',
            author_name: 'Test',
            author_email: 'test@test.com',
            commit_date: '2024-01-03',
            is_indexed: true,
            tags: [],
            is_branch_specific: true,
            is_merge_base: false,
          },
        ],
        total: 1,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.repository).not.toBeNull()
      })

      // leftCommit should be the explicitly selected commit
      expect(result.current.computedState.leftCommit).toBe('explicit-commit')
    })

    it('should fall back to fileVersions when latestBranchCommit is also null', async () => {
      // Edge case: no branch selected, no commits loaded, but file history exists
      mockSearchParams = new URLSearchParams('')

      mockGetCommits.mockResolvedValue({ commits: [], total: 0 })

      mockGetFileHistory.mockResolvedValue({
        versions: [
          {
            commit_id: 5,
            commit_hash: 'file-version-xyz',
            short_hash: 'file-v',
            commit_date: '2024-01-02',
            message: 'Last file change',
            content_hash: 'hash1',
          },
        ],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 1,
      })

      const { result } = await renderBrowseStateHook()

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(1)
      })

      // With no selectedCommit and no latestBranchCommit, falls back to fileVersions[0]
      expect(result.current.computedState.leftCommit).toBe('file-version-xyz')
    })
  })

  describe('changedOnly tree loading timing (issue #89)', () => {
    it('should not load unfiltered tree when changedOnly is true and treeCommit is pending', async () => {
      // Regression test: when co=1 is set but no specific commit is selected,
      // treeCommit falls back to latestBranchCommit which starts as null.
      // The tree should NOT be loaded unfiltered while waiting for latestBranchCommit.
      mockSearchParams = new URLSearchParams('co=1&branch=feature')

      // Mock getCommits to return a latest indexed commit
      mockGetCommits.mockResolvedValue({
        commits: [
          {
            hash: 'latest-abc',
            short_hash: 'latest',
            message: 'Latest commit',
            author_name: 'Test',
            author_email: 'test@test.com',
            commit_date: '2024-01-01',
            is_indexed: true,
            tags: [],
            is_branch_specific: true,
            is_merge_base: false,
          },
        ],
        total: 1,
      })

      await renderBrowseStateHook()

      // Wait for the tree to be loaded with changedOnly
      await vi.waitFor(() => {
        const changedOnlyCall = mockGetRepositoryTreeByName.mock.calls.find(
          (call) => call[3] === true
        )
        expect(changedOnlyCall).toBeDefined()
      })

      // There should be NO calls that loaded the unfiltered tree
      // (i.e., no calls where changedOnly was false/undefined)
      const unfilteredCalls = mockGetRepositoryTreeByName.mock.calls.filter(
        (call) => call[3] !== true
      )
      expect(unfilteredCalls).toHaveLength(0)
    })

    it('should load filtered tree once latestBranchCommit resolves', async () => {
      mockSearchParams = new URLSearchParams('co=1&branch=feature')

      mockGetCommits.mockResolvedValue({
        commits: [
          {
            hash: 'commit-xyz',
            short_hash: 'commit',
            message: 'Feature commit',
            author_name: 'Test',
            author_email: 'test@test.com',
            commit_date: '2024-01-01',
            is_indexed: true,
            tags: [],
            is_branch_specific: true,
            is_merge_base: false,
          },
        ],
        total: 1,
      })

      await renderBrowseStateHook()

      // Once latestBranchCommit resolves, the tree should be loaded with:
      // - the commit hash as the treeCommit
      // - changedOnly = true
      await vi.waitFor(() => {
        const changedOnlyCall = mockGetRepositoryTreeByName.mock.calls.find(
          (call) => call[0] === 'test-repo' && call[1] === 'commit-xyz' && call[3] === true
        )
        expect(changedOnlyCall).toBeDefined()
      })
    })

    it('should load tree normally when changedOnly is false even without treeCommit', async () => {
      // When changedOnly is false, the tree should load regardless of treeCommit
      mockSearchParams = new URLSearchParams('branch=feature')

      mockGetCommits.mockResolvedValue({ commits: [], total: 0 })

      await renderBrowseStateHook()

      // Tree should have been loaded (changedOnly=false, so no commit needed)
      expect(mockGetRepositoryTreeByName).toHaveBeenCalled()
    })

    it('should load filtered tree immediately when selectedCommit is provided', async () => {
      // When a specific commit is selected, treeCommit doesn't depend on latestBranchCommit
      mockSearchParams = new URLSearchParams('co=1&commit=abc123&branch=feature')

      await renderBrowseStateHook()

      // Tree should have been loaded with the specific commit and changedOnly=true
      await vi.waitFor(() => {
        const call = mockGetRepositoryTreeByName.mock.calls.find(
          (c) => c[0] === 'test-repo' && c[1] === 'abc123' && c[3] === true
        )
        expect(call).toBeDefined()
      })
    })
  })
})
