import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useBrowseState } from './useBrowseState'
import * as api from '@/lib/api'

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
  getFileContentByPathAtCommit: vi.fn(),
  getFileSymbolsByPath: vi.fn(),
  getFileReferencesByPath: vi.fn(),
  getSymbol: vi.fn(),
  getFileHistory: vi.fn(),
}))

const mockGetRepositories = vi.mocked(api.getRepositories)
const mockGetRepositoryByName = vi.mocked(api.getRepositoryByName)
const mockGetRepositoryTreeByName = vi.mocked(api.getRepositoryTreeByName)
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
    it('should parse search query from URL', () => {
      mockSearchParams = new URLSearchParams('q=MyClass')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.searchQuery).toBe('MyClass')
    })

    it('should default search query to empty string', () => {
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.searchQuery).toBe('')
    })

    it('should parse drawer state from URL (closed)', () => {
      mockSearchParams = new URLSearchParams('drawer=0')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.drawerOpen).toBe(false)
    })

    it('should default drawer to open', () => {
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.drawerOpen).toBe(true)
    })

    it('should parse refs panel state from URL (open)', () => {
      mockSearchParams = new URLSearchParams('refs=1')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.refsPanelOpen).toBe(true)
    })

    it('should default refs panel to closed', () => {
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.refsPanelOpen).toBe(false)
    })

    it('should parse tree panel side from URL', () => {
      mockSearchParams = new URLSearchParams('tp=r')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.treePanel).toBe('right')
    })

    it('should default tree panel to left', () => {
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.treePanel).toBe('left')
    })

    it('should parse ref panel side from URL', () => {
      mockSearchParams = new URLSearchParams('rp=r')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.refPanel).toBe('right')
    })

    it('should parse active panel from URL', () => {
      mockSearchParams = new URLSearchParams('ap=r')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.activePanel).toBe('right')
    })

    it('should parse diff mode from URL', () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.diffMode).toBe(true)
      expect(result.current.urlState.selectedCommit).toBe('abc123')
      expect(result.current.urlState.diffCommit).toBe('def456')
    })

    it('should parse highlight line from URL', () => {
      mockSearchParams = new URLSearchParams('line=42')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.highlightLine).toBe(42)
    })

    it('should parse all params together', () => {
      mockSearchParams = new URLSearchParams(
        'q=MyClass&refs=1&drawer=0&tp=r&rp=r&ap=r&commit=abc&diff=def&line=10'
      )
      const { result } = renderHook(() => useBrowseState())

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
  })

  describe('URL state updates', () => {
    it('should update search query in URL', async () => {
      const { result } = renderHook(() => useBrowseState())

      act(() => {
        result.current.actions.setSearchQuery('NewSearch')
      })

      expect(mockSetSearchParams).toHaveBeenCalled()
      expect(mockSearchParams.get('q')).toBe('NewSearch')
    })

    it('should remove search query from URL when empty', async () => {
      mockSearchParams = new URLSearchParams('q=OldSearch')
      const { result } = renderHook(() => useBrowseState())

      act(() => {
        result.current.actions.setSearchQuery('')
      })

      expect(mockSearchParams.has('q')).toBe(false)
    })

    it('should toggle drawer state in URL', async () => {
      const { result } = renderHook(() => useBrowseState())

      // Initially open (no drawer param)
      expect(result.current.urlState.drawerOpen).toBe(true)

      act(() => {
        result.current.actions.toggleDrawer()
      })

      expect(mockSearchParams.get('drawer')).toBe('0')
    })

    it('should update tree panel in URL', async () => {
      const { result } = renderHook(() => useBrowseState())

      act(() => {
        result.current.actions.setTreePanel('right')
      })

      expect(mockSearchParams.get('tp')).toBe('r')
    })

    it('should update ref panel in URL', async () => {
      const { result } = renderHook(() => useBrowseState())

      act(() => {
        result.current.actions.setRefPanel('right')
      })

      expect(mockSearchParams.get('rp')).toBe('r')
    })

    it('should update active panel in URL', async () => {
      const { result } = renderHook(() => useBrowseState())

      act(() => {
        result.current.actions.setActivePanel('right')
      })

      expect(mockSearchParams.get('ap')).toBe('r')
    })
  })

  describe('UI state exposure', () => {
    it('should expose drawer state through uiState', () => {
      mockSearchParams = new URLSearchParams('drawer=0')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.uiState.drawerOpen).toBe(false)
    })

    it('should expose refs panel state through uiState', () => {
      mockSearchParams = new URLSearchParams('refs=1')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.uiState.refsPanelOpen).toBe(true)
    })

    it('should expose search query through uiState', () => {
      mockSearchParams = new URLSearchParams('q=Test')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.uiState.searchQuery).toBe('Test')
    })
  })

  describe('diff state exposure', () => {
    it('should expose panel states through diffState', () => {
      mockSearchParams = new URLSearchParams('tp=r&rp=r&ap=r')
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.diffState.treePanel).toBe('right')
      expect(result.current.diffState.refPanel).toBe('right')
      expect(result.current.diffState.activePanel).toBe('right')
    })
  })

  describe('backwards compatibility', () => {
    it('should work with no URL params (all defaults)', () => {
      const { result } = renderHook(() => useBrowseState())

      expect(result.current.urlState.searchQuery).toBe('')
      expect(result.current.urlState.drawerOpen).toBe(true)
      expect(result.current.urlState.refsPanelOpen).toBe(false)
      expect(result.current.urlState.treePanel).toBe('left')
      expect(result.current.urlState.refPanel).toBe('left')
      expect(result.current.urlState.activePanel).toBe('left')
      expect(result.current.urlState.diffMode).toBe(false)
    })

    it('should work with only legacy params (commit, line)', () => {
      mockSearchParams = new URLSearchParams('commit=abc123&line=50')
      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

      // Wait for fileVersions to load
      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(3)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      // Should navigate with diff param set to the next version
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('diff=def456')
      )
    })

    it('should not enter diff mode when only one version exists', async () => {
      mockGetFileHistory.mockResolvedValue({
        versions: [mockVersions[0]!],
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 1,
      })

      const { result } = renderHook(() => useBrowseState())

      // Wait for fileVersions to load
      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(1)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      // Should NOT navigate since there's no other version to diff against
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('should preserve UI state when entering diff mode', async () => {
      mockSearchParams = new URLSearchParams('drawer=0&refs=1&q=TestQuery&line=42')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 3,
      })

      const { result } = renderHook(() => useBrowseState())

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(3)
      })

      act(() => {
        result.current.actions.enterDiffMode()
      })

      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringMatching(/drawer=0.*|.*drawer=0/)
      )
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringMatching(/refs=1.*|.*refs=1/)
      )
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringMatching(/q=TestQuery.*|.*q=TestQuery/)
      )
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringMatching(/line=42.*|.*line=42/)
      )
    })

    it('should exit diff mode and clear diff params', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123&diff=def456')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 3,
      })

      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.changeVersion('def456')
      })

      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('commit=def456')
      )
    })

    it('should preserve UI state when changing version', async () => {
      mockSearchParams = new URLSearchParams('drawer=0&q=TestQuery')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = renderHook(() => useBrowseState())

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.changeVersion('def456')
      })

      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringMatching(/drawer=0.*|.*drawer=0/)
      )
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringMatching(/q=TestQuery.*|.*q=TestQuery/)
      )
    })

    it('should clear commit param when changing to null (latest)', async () => {
      mockSearchParams = new URLSearchParams('commit=abc123')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

      await vi.waitFor(() => {
        expect(result.current.dataState.fileVersions.length).toBe(2)
      })

      act(() => {
        result.current.actions.changeDiffVersion('ghi789')
      })

      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('diff=ghi789')
      )
    })

    it('should clear refs panel state when changing version', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')
      mockGetFileHistory.mockResolvedValue({
        versions: mockVersions,
        path: 'src/main.py',
        repository_name: 'test-repo',
        total: 2,
      })

      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

      // Wait for initial load
      await vi.waitFor(() => {
        expect(result.current.urlState.refsPanelOpen).toBe(true)
      })

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

      const { result } = renderHook(() => useBrowseState())

      await vi.waitFor(() => {
        expect(result.current.urlState.refsPanelOpen).toBe(true)
      })

      act(() => {
        result.current.actions.closeRefsPanel()
      })

      // Should have called setSearchParams to remove refs
      expect(mockSetSearchParams).toHaveBeenCalled()
      expect(mockSearchParams.has('refs')).toBe(false)
    })

    it('should preserve search query when closing refs panel', async () => {
      mockSearchParams = new URLSearchParams('refs=1&q=TestSymbol')

      const { result } = renderHook(() => useBrowseState())

      await vi.waitFor(() => {
        expect(result.current.urlState.refsPanelOpen).toBe(true)
        expect(result.current.urlState.searchQuery).toBe('TestSymbol')
      })

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

      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

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

      const { result } = renderHook(() => useBrowseState())

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

    it('should navigate to symbol file and open refs panel', () => {
      const { result } = renderHook(() => useBrowseState())

      act(() => {
        result.current.actions.navigateToSymbol(mockSymbol)
      })

      // Should navigate to the symbol's file with line number
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('src/myclass.py')
      )
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('line=42')
      )

      // Should open refs panel (refs=1 in URL)
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('refs=1')
      )

      // Should include symbol name in search query
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('q=__init__')
      )
    })

    it('should set refs panel state when navigating to symbol', () => {
      const { result } = renderHook(() => useBrowseState())

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

    it('should open refs panel by name when symbol has no file_path', () => {
      const symbolWithoutPath = {
        ...mockSymbol,
        file_path: null,
      }

      const { result } = renderHook(() => useBrowseState())

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

    it('should preserve drawer state when navigating', () => {
      mockSearchParams = new URLSearchParams('drawer=0')

      const { result } = renderHook(() => useBrowseState())

      act(() => {
        result.current.actions.navigateToSymbol(mockSymbol)
      })

      // Should preserve drawer=0 in navigation
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining('drawer=0')
      )
    })
  })
})
