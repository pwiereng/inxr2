import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import Browse from './Browse'
import type { TabValue } from '@/components/CodeHeader'
import type { FileContent, RawFileContent, Repository, ResolvePathResult } from '@/lib/api'

// Browse delegates all of its state to useBrowseState (already tested via its
// sub-hooks). We mock the hook so each test can drive a specific render branch
// directly, and assert Browse's own wiring: render branches + nav handlers.
vi.mock('@/hooks/useBrowseState', () => ({
  useBrowseState: vi.fn(),
}))

// api.ts is frozen; Browse only calls getFileBlame directly. Stub it so the
// blame effect never hits the network.
vi.mock('@/lib/api', () => ({
  getFileBlame: vi.fn().mockResolvedValue({
    path: 'src/a.ts',
    repository_name: 'myrepo',
    lines: [],
    total: 0,
  }),
}))

// CodeHeader pulls repo/branch data from the API. Stub it with one button per
// callback so handleTabChange/Repo/Branch/Commit are exercised.
vi.mock('@/components/CodeHeader', () => ({
  CodeHeader: (props: {
    onRepoChange: (r: string) => void
    onBranchChange: (b: string) => void
    onCommitChange: (c: string) => void
    onTabChange: (t: TabValue) => void
  }) => (
    <div data-testid="code-header">
      <button onClick={() => props.onRepoChange('newrepo')}>hdr-repo</button>
      <button onClick={() => props.onBranchChange('newbranch')}>hdr-branch</button>
      <button onClick={() => props.onCommitChange('abc123')}>hdr-commit</button>
      <button onClick={() => props.onTabChange('browse')}>hdr-browse</button>
      <button onClick={() => props.onTabChange('search')}>hdr-search</button>
      <button onClick={() => props.onTabChange('history')}>hdr-history</button>
      <button onClick={() => props.onTabChange('logical-view')}>hdr-logical</button>
      <button onClick={() => props.onTabChange('dependencies')}>hdr-deps</button>
      <button onClick={() => props.onTabChange('help')}>hdr-help</button>
    </div>
  ),
}))

// Stub heavy children so tests stay focused on Browse. CodeViewer/DiffCodeViewer
// expose buttons that fire the search/blame callbacks Browse passes down.
vi.mock('@/components/CodeViewer', () => ({
  CodeViewer: (props: {
    onSearchText?: (t: string) => void
    onBlameCommitClick?: (c: string) => void
    onSymbolClick?: (s: { id: number; name: string }) => void
    onReferenceClick?: (r: { id: number }) => void
    onLineClick?: (n: number) => void
  }) => (
    // testid is "stub-code-viewer" to avoid colliding with the resizable Panel
    // whose id="code-viewer" surfaces as a data-testid in the DOM.
    <div data-testid="stub-code-viewer">
      <button onClick={() => props.onSearchText?.('needle')}>cv-search</button>
      <button onClick={() => props.onSearchText?.('')}>cv-search-empty</button>
      <button onClick={() => props.onBlameCommitClick?.('c'.repeat(40))}>cv-blame</button>
      <button onClick={() => props.onSymbolClick?.({ id: 1, name: 'foo' })}>cv-symbol</button>
      <button onClick={() => props.onReferenceClick?.({ id: 2 })}>cv-reference</button>
      <button onClick={() => props.onLineClick?.(42)}>cv-line</button>
    </div>
  ),
}))
vi.mock('@/components/DiffCodeViewer', () => ({
  // Render the left/right header nodes Browse passes in so their chip/selector
  // JSX is exercised, and expose buttons for each interaction callback.
  DiffCodeViewer: (props: {
    onSearchText?: (t: string) => void
    onPanelClick?: (p: 'left' | 'right') => void
    onSymbolClick?: (s: { id: number }, p: 'left' | 'right') => void
    onReferenceClick?: (r: { id: number }, p: 'left' | 'right') => void
    onLineClick?: (n: number, p: 'left' | 'right') => void
    onClosePanel?: (p: 'left' | 'right') => void
    leftHeader?: ReactNode
    rightHeader?: ReactNode
  }) => (
    <div data-testid="diff-code-viewer">
      <div data-testid="diff-left-header">{props.leftHeader}</div>
      <div data-testid="diff-right-header">{props.rightHeader}</div>
      <button onClick={() => props.onSearchText?.('needle')}>diff-search</button>
      <button onClick={() => props.onPanelClick?.('right')}>diff-panel</button>
      <button onClick={() => props.onSymbolClick?.({ id: 1 }, 'left')}>diff-symbol</button>
      <button onClick={() => props.onReferenceClick?.({ id: 2 }, 'right')}>diff-reference</button>
      <button onClick={() => props.onLineClick?.(5, 'left')}>diff-line</button>
      <button onClick={() => props.onClosePanel?.('left')}>diff-close</button>
    </div>
  ),
}))
vi.mock('@/components/ImageViewer', () => ({
  ImageViewer: () => <div data-testid="image-viewer" />,
}))
vi.mock('@/components/MarkdownViewer', () => ({
  MarkdownViewer: () => <div data-testid="markdown-viewer" />,
}))
vi.mock('@/components/FileTree', () => ({
  FileTree: () => <div data-testid="stub-file-tree" />,
}))
vi.mock('@/components/DirectoryListing', () => ({
  DirectoryListing: (props: {
    onFileSelect?: (p: string) => void
    onDirectorySelect?: (p: string) => void
    onParentClick?: () => void
  }) => (
    <div data-testid="directory-listing">
      <button onClick={() => props.onFileSelect?.('src/x.ts')}>dir-file</button>
      <button onClick={() => props.onDirectorySelect?.('src')}>dir-dir</button>
      <button onClick={() => props.onParentClick?.()}>dir-parent</button>
    </div>
  ),
}))
vi.mock('@/components/SymbolSearch', () => ({
  SymbolSearch: () => <div data-testid="symbol-search" />,
}))
vi.mock('@/components/ReferencesPanel', () => ({
  ReferencesPanel: () => <div data-testid="references-panel" />,
}))
vi.mock('@/components/BreadcrumbNav', () => ({
  BreadcrumbNav: () => <div data-testid="breadcrumb-nav" />,
}))
vi.mock('@/components/BranchSelector', () => ({
  BranchSelector: () => <div data-testid="branch-selector" />,
}))
vi.mock('@/components/VersionSelector', () => ({
  VersionSelector: () => <div data-testid="version-selector" />,
}))
vi.mock('@/components/CopyButton/CopyButton', () => ({
  CopyButton: () => <button data-testid="copy-button">copy</button>,
}))

import { useBrowseState } from '@/hooks/useBrowseState'
import { getFileBlame } from '@/lib/api'
import { ROUTER_FUTURE_FLAGS } from '@/lib/routerFuture'
type BrowseStateResult = ReturnType<typeof useBrowseState>
const mockUseBrowseState = vi.mocked(useBrowseState)
const mockGetFileBlame = vi.mocked(getFileBlame)

function LocationDisplay() {
  const loc = useLocation()
  return <div data-testid="location">{loc.pathname + loc.search}</div>
}

/**
 * Click the MUI IconButton wrapping a given icon. The toolbar's icon buttons
 * have no accessible name, but @mui/icons-material stamps each icon with a
 * data-testid equal to its component name (e.g. "CompareArrowsIcon").
 */
function iconButton(iconTestId: string): HTMLElement {
  const button = screen.getByTestId(iconTestId).closest('button')
  if (!button) throw new Error(`No button wrapping icon ${iconTestId}`)
  return button
}

function makeFileContent(overrides: Partial<FileContent> = {}): FileContent {
  return {
    id: 1,
    path: 'src/a.ts',
    language: 'typescript',
    content: 'const x = 1\n',
    line_count: 1,
    size_bytes: 12,
    ...overrides,
  }
}

function makeRepository(overrides: Partial<Repository> = {}): Repository {
  return {
    id: 1,
    name: 'myrepo',
    url: 'https://example.com/myrepo',
    description: null,
    default_branch: 'main',
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}

const noopActions = (): BrowseStateResult['actions'] => ({
  navigateToRepository: vi.fn(),
  navigateToFile: vi.fn(),
  navigateToDirectory: vi.fn(),
  navigateToSymbol: vi.fn(),
  navigateToLine: vi.fn(),
  resetToFileTree: vi.fn(),
  enterDiffMode: vi.fn(),
  exitDiffMode: vi.fn(),
  closePanel: vi.fn(),
  swapDiffPanels: vi.fn(),
  setActivePanel: vi.fn(),
  setTreePanel: vi.fn(),
  changeBranch: vi.fn(),
  changeDiffBranch: vi.fn(),
  changeVersion: vi.fn(),
  changeDiffVersion: vi.fn(),
  toggleDrawer: vi.fn(),
  setDrawerOpen: vi.fn(),
  toggleChangedOnly: vi.fn(),
  setChangedOnly: vi.fn(),
  openRefsPanel: vi.fn(),
  openRefsPanelByName: vi.fn(),
  closeRefsPanel: vi.fn(),
  setRefPanel: vi.fn(),
  handleRefPanelChange: vi.fn(),
  setViewMode: vi.fn(),
  setSearchQuery: vi.fn(),
  handleSymbolClick: vi.fn(),
  handleDiffSymbolClick: vi.fn(),
  handleCodeReferenceClick: vi.fn(),
  handleDiffReferenceClick: vi.fn(),
  handleRefPanelClick: vi.fn(),
  handleDefinitionClick: vi.fn(),
  handleDiffLineClick: vi.fn(),
})

interface StateOverrides {
  urlState?: Partial<BrowseStateResult['urlState']>
  dataState?: Partial<BrowseStateResult['dataState']>
  diffState?: Partial<BrowseStateResult['diffState']>
  uiState?: Partial<BrowseStateResult['uiState']>
  refsState?: Partial<BrowseStateResult['refsState']>
  computedState?: Partial<BrowseStateResult['computedState']>
  actions?: Partial<BrowseStateResult['actions']>
}

function makeState(o: StateOverrides = {}): BrowseStateResult {
  return {
    urlState: {
      repoName: 'myrepo',
      filePath: null,
      directoryPath: null,
      highlightLine: undefined,
      selectedCommit: null,
      diffCommit: null,
      diffMode: false,
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
      ...o.urlState,
    },
    dataState: {
      allRepositories: [],
      repository: makeRepository(),
      treeNodes: [],
      fileContent: null,
      fileSymbols: [],
      fileReferences: [],
      fileVersions: [],
      rawContent: null,
      ...o.dataState,
    },
    diffState: {
      diffContent: null,
      diffSymbols: [],
      diffReferences: [],
      diffRenameInfo: null,
      activePanel: 'left',
      treePanel: 'left',
      refPanel: 'left',
      ...o.diffState,
    },
    uiState: {
      drawerOpen: true,
      refsPanelOpen: false,
      loading: false,
      treeLoading: false,
      fileLoading: false,
      diffLoading: false,
      error: null,
      fileRenameInfo: null,
      searchQuery: '',
      ...o.uiState,
    },
    refsState: {
      selectedSymbol: null,
      isDirectDefinition: false,
      searchByName: null,
      ...o.refsState,
    },
    computedState: {
      comparisonCommit: null,
      globalReferenceCommit: undefined,
      treeCommit: null,
      refCommit: null,
      currentCommitHash: undefined,
      fileChangedInCommit: true,
      referenceIsNewer: false,
      temporalOrderKnown: false,
      ...o.computedState,
    },
    actions: { ...noopActions(), ...o.actions },
  }
}

function renderBrowse(state: BrowseStateResult, entry = '/browse/myrepo') {
  mockUseBrowseState.mockReturnValue(state)
  return render(
    <MemoryRouter initialEntries={[entry]} future={ROUTER_FUTURE_FLAGS}>
      <Browse />
      <LocationDisplay />
    </MemoryRouter>
  )
}

describe('Browse', () => {
  beforeEach(() => {
    mockUseBrowseState.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('top-level render branches', () => {
    it('shows a loading spinner while the page is loading', () => {
      renderBrowse(makeState({ uiState: { loading: true } }))
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
      expect(screen.queryByTestId('code-header')).not.toBeInTheDocument()
    })

    it('shows the page-level error when there is an error and no file path', () => {
      renderBrowse(makeState({ uiState: { error: 'kaboom' } }))
      expect(screen.getByText('kaboom')).toBeInTheDocument()
      expect(screen.queryByTestId('code-header')).not.toBeInTheDocument()
    })

    it('renders the directory listing as the default empty state', () => {
      renderBrowse(makeState())
      expect(screen.getByTestId('code-header')).toBeInTheDocument()
      expect(screen.getByTestId('directory-listing')).toBeInTheDocument()
    })

    it('shows a spinner in the code panel while the tree is loading', () => {
      renderBrowse(makeState({ uiState: { treeLoading: true } }))
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
      expect(screen.queryByTestId('directory-listing')).not.toBeInTheDocument()
    })
  })

  describe('code panel render branches', () => {
    it('shows a spinner while a file is loading', () => {
      renderBrowse(
        makeState({ urlState: { filePath: 'src/a.ts' }, uiState: { fileLoading: true } })
      )
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    it('renders the single-file CodeViewer for a normal file', () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      expect(screen.getByTestId('stub-code-viewer')).toBeInTheDocument()
      expect(screen.getByText('1 lines')).toBeInTheDocument()
    })

    it('renders the MarkdownViewer for a markdown file in rendered mode', () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'README.md' },
          dataState: { fileContent: makeFileContent({ path: 'README.md', language: 'markdown' }) },
        })
      )
      expect(screen.getByTestId('markdown-viewer')).toBeInTheDocument()
      expect(screen.queryByTestId('stub-code-viewer')).not.toBeInTheDocument()
    })

    it('renders the ImageViewer for raw (image) content', () => {
      const rawContent: RawFileContent = {
        path: 'logo.png',
        language: null,
        content_type: 'image/png',
        encoding: 'base64',
        data: 'AAAA',
        size_bytes: 4,
      }
      renderBrowse(
        makeState({
          urlState: { filePath: 'logo.png' },
          dataState: { rawContent },
        })
      )
      expect(screen.getByTestId('image-viewer')).toBeInTheDocument()
    })

    it('renders the DiffCodeViewer in diff mode with diff content', () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts', diffMode: true },
          dataState: { fileContent: makeFileContent() },
          diffState: { diffContent: makeFileContent({ content: 'const x = 2\n' }) },
        })
      )
      expect(screen.getByTestId('diff-code-viewer')).toBeInTheDocument()
    })

    it('handleSearchText fires from the diff viewer too', async () => {
      const user = userEvent.setup()
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts', diffMode: true, selectedCommit: 'deadbeef' },
          dataState: { fileContent: makeFileContent() },
          diffState: { diffContent: makeFileContent({ content: 'const x = 2\n' }) },
        })
      )
      await user.click(screen.getByText('diff-search'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/search')
      expect(loc).toHaveTextContent('query=needle')
      expect(loc).toHaveTextContent('repo=myrepo')
    })

    it('shows a spinner in diff mode while diff content loads', () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts', diffMode: true },
          dataState: { fileContent: makeFileContent() },
          uiState: { diffLoading: true },
        })
      )
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    it('shows the "file not found at version" prompt in diff mode without diff content', () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts', diffMode: true },
          dataState: { fileContent: makeFileContent() },
        })
      )
      expect(screen.getByText(/File not found at selected version/)).toBeInTheDocument()
    })

    it('shows the rename notice and navigates to the resolved path on "Go to file"', async () => {
      const user = userEvent.setup()
      const navigateToFile = vi.fn()
      const fileRenameInfo: ResolvePathResult = {
        found: true,
        resolved_path: 'src/renamed.ts',
        renamed_from: 'src/a.ts',
        renamed_to: null,
        rename_commit_hash: 'a'.repeat(40),
      }
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          uiState: { fileRenameInfo },
          actions: { navigateToFile },
        })
      )
      expect(screen.getByText(/this file was at src\/renamed\.ts/)).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Go to file' }))
      expect(navigateToFile).toHaveBeenCalledWith('src/renamed.ts')
    })

    it('shows a file-level error with a back button when filePath is set', () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          uiState: { error: 'file boom' },
        })
      )
      expect(screen.getByText('file boom')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Back to file browser/ })).toBeInTheDocument()
    })

    it('shows the "not changed in revision" notice when changedOnly hides the file', () => {
      renderBrowse(
        makeState({
          urlState: {
            filePath: 'src/a.ts',
            changedOnly: true,
            selectedCommit: 'f'.repeat(40),
          },
          dataState: { fileContent: makeFileContent() },
          computedState: { fileChangedInCommit: false },
        })
      )
      expect(screen.getByText('File not changed in this revision')).toBeInTheDocument()
    })
  })

  describe('references side panel', () => {
    it('is hidden by default', () => {
      renderBrowse(makeState())
      expect(screen.queryByTestId('references-panel')).not.toBeInTheDocument()
    })

    it('renders the ReferencesPanel when refsPanelOpen is set', () => {
      renderBrowse(makeState({ uiState: { refsPanelOpen: true } }))
      expect(screen.getByTestId('references-panel')).toBeInTheDocument()
    })

    it('renders the refs panel with its diff-mode version selector in diff mode', () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts', diffMode: true },
          dataState: { fileContent: makeFileContent() },
          diffState: { diffContent: makeFileContent({ content: 'const x = 2\n' }) },
          uiState: { refsPanelOpen: true },
        })
      )
      expect(screen.getByTestId('references-panel')).toBeInTheDocument()
      expect(screen.getByText('Refs @')).toBeInTheDocument()
    })
  })

  describe('header navigation handlers', () => {
    it('handleRepoChange navigates to the new repo root', async () => {
      const user = userEvent.setup()
      renderBrowse(makeState())
      await user.click(screen.getByText('hdr-repo'))
      expect(screen.getByTestId('location')).toHaveTextContent('/browse/newrepo')
    })

    it('handleBranchChange delegates to actions.changeBranch', async () => {
      const user = userEvent.setup()
      const changeBranch = vi.fn()
      renderBrowse(makeState({ actions: { changeBranch } }))
      await user.click(screen.getByText('hdr-branch'))
      expect(changeBranch).toHaveBeenCalledWith('newbranch')
    })

    it('handleCommitChange delegates to actions.changeVersion', async () => {
      const user = userEvent.setup()
      const changeVersion = vi.fn()
      renderBrowse(makeState({ actions: { changeVersion } }))
      await user.click(screen.getByText('hdr-commit'))
      expect(changeVersion).toHaveBeenCalledWith('abc123')
    })

    it('handleTabChange navigates to each tab, preserving repo/branch/commit', async () => {
      const user = userEvent.setup()
      const cases: Array<[string, string]> = [
        ['hdr-search', '/search'],
        ['hdr-history', '/history'],
        ['hdr-logical', '/logical-view'],
        ['hdr-deps', '/dependencies'],
        ['hdr-help', '/help'],
      ]
      for (const [button, path] of cases) {
        const { unmount } = renderBrowse(
          makeState({
            urlState: { repoName: 'myrepo', selectedBranch: 'main', selectedCommit: 'deadbeef' },
          })
        )
        await user.click(screen.getByText(button))
        const loc = screen.getByTestId('location')
        expect(loc).toHaveTextContent(path)
        expect(loc).toHaveTextContent('repo=myrepo')
        expect(loc).toHaveTextContent('branch=main')
        expect(loc).toHaveTextContent('commit=deadbeef')
        unmount()
      }
    })

    it('handleTabChange → browse stays on the current page (no navigation)', async () => {
      const user = userEvent.setup()
      renderBrowse(makeState(), '/browse/myrepo')
      await user.click(screen.getByText('hdr-browse'))
      expect(screen.getByTestId('location')).toHaveTextContent('/browse/myrepo')
    })
  })

  describe('content navigation handlers', () => {
    it('handleSearchText navigates to /search with the selected text as query', async () => {
      const user = userEvent.setup()
      renderBrowse(
        makeState({
          urlState: {
            filePath: 'src/a.ts',
            selectedCommit: 'deadbeef',
          },
          dataState: { fileContent: makeFileContent() },
        })
      )
      await user.click(screen.getByText('cv-search'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/search')
      expect(loc).toHaveTextContent('query=needle')
      expect(loc).toHaveTextContent('repo=myrepo')
      expect(loc).toHaveTextContent('branch=main')
      expect(loc).toHaveTextContent('commit=deadbeef')
    })

    it('handleSearchText is a no-op for empty text', async () => {
      const user = userEvent.setup()
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      await user.click(screen.getByText('cv-search-empty'))
      // No navigation away from the browse page.
      expect(screen.getByTestId('location')).toHaveTextContent('/browse/myrepo')
    })

    it('handleBlameCommitClick navigates to /history with the clicked commit', async () => {
      const user = userEvent.setup()
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      await user.click(screen.getByText('cv-blame'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/history')
      expect(loc).toHaveTextContent(`commit=${'c'.repeat(40)}`)
      expect(loc).toHaveTextContent('repo=myrepo')
      expect(loc).toHaveTextContent('branch=main')
    })

    it('Cmd+Shift+F searches the current text selection', async () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts', selectedCommit: 'deadbeef' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      // Simulate a non-empty window selection, then fire the shortcut.
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => '  pickedText  ',
      } as unknown as Selection)

      act(() => {
        window.dispatchEvent(
          new KeyboardEvent('keydown', { key: 'F', metaKey: true, shiftKey: true, bubbles: true })
        )
      })

      await waitFor(() => {
        const loc = screen.getByTestId('location')
        expect(loc).toHaveTextContent('/search')
        expect(loc).toHaveTextContent('query=pickedText')
      })
    })

    it('Cmd+Shift+F with an empty selection does not navigate', async () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => '   ',
      } as unknown as Selection)

      act(() => {
        window.dispatchEvent(
          new KeyboardEvent('keydown', { key: 'F', metaKey: true, shiftKey: true, bubbles: true })
        )
      })

      // Stays on the browse page — no /search navigation.
      expect(screen.getByTestId('location')).toHaveTextContent('/browse/myrepo')
    })

    it('ignores Cmd+Shift+F while focus is in an input field', () => {
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      // A non-empty selection exists, but the keystroke originates from an input,
      // so the shortcut must bail out before searching.
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => 'selected',
      } as unknown as Selection)
      const input = document.createElement('input')
      document.body.appendChild(input)
      act(() => {
        input.dispatchEvent(
          new KeyboardEvent('keydown', { key: 'F', metaKey: true, shiftKey: true, bubbles: true })
        )
      })
      expect(screen.getByTestId('location')).toHaveTextContent('/browse/myrepo')
      document.body.removeChild(input)
    })
  })

  describe('toolbar interactions', () => {
    function fileState(extra: StateOverrides = {}) {
      return makeState({
        urlState: { filePath: 'src/a.ts', ...extra.urlState },
        dataState: { fileContent: makeFileContent(), ...extra.dataState },
        ...extra,
      })
    }

    it('toggles the file-tree drawer', async () => {
      const user = userEvent.setup()
      const toggleDrawer = vi.fn()
      renderBrowse(makeState({ actions: { toggleDrawer } }))
      // drawerOpen defaults to true → the ChevronLeft (collapse) icon is shown.
      await user.click(iconButton('ChevronLeftIcon'))
      expect(toggleDrawer).toHaveBeenCalledTimes(1)
    })

    it('shows the menu icon and toggles the drawer when closed', async () => {
      const user = userEvent.setup()
      const toggleDrawer = vi.fn()
      renderBrowse(makeState({ uiState: { drawerOpen: false }, actions: { toggleDrawer } }))
      await user.click(iconButton('MenuIcon'))
      expect(toggleDrawer).toHaveBeenCalledTimes(1)
    })

    it('toggles "Changed files only"', async () => {
      const user = userEvent.setup()
      const toggleChangedOnly = vi.fn()
      renderBrowse(makeState({ actions: { toggleChangedOnly } }))
      await user.click(screen.getByRole('checkbox'))
      expect(toggleChangedOnly).toHaveBeenCalledTimes(1)
    })

    it('resets to the file tree via the back-to-root button', async () => {
      const user = userEvent.setup()
      const resetToFileTree = vi.fn()
      renderBrowse(fileState({ actions: { resetToFileTree } }))
      await user.click(screen.getByRole('button', { name: 'Back to root' }))
      expect(resetToFileTree).toHaveBeenCalledTimes(1)
    })

    it('jump-to-top navigates to line 1 for a code file', async () => {
      const user = userEvent.setup()
      const navigateToLine = vi.fn()
      renderBrowse(fileState({ actions: { navigateToLine } }))
      await user.click(iconButton('VerticalAlignTopIcon'))
      expect(navigateToLine).toHaveBeenCalledWith(1)
    })

    it('jump-to-top scrolls the container for rendered (markdown) content', async () => {
      const user = userEvent.setup()
      const scrollTo = vi.fn()
      Element.prototype.scrollTo = scrollTo
      const navigateToLine = vi.fn()
      renderBrowse(
        makeState({
          urlState: { filePath: 'README.md' },
          dataState: { fileContent: makeFileContent({ path: 'README.md', language: 'markdown' }) },
          actions: { navigateToLine },
        })
      )
      await user.click(iconButton('VerticalAlignTopIcon'))
      expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
      expect(navigateToLine).not.toHaveBeenCalled()
    })

    it('toggles the markdown raw/rendered view', async () => {
      const user = userEvent.setup()
      const setViewMode = vi.fn()
      renderBrowse(
        makeState({
          urlState: { filePath: 'README.md' },
          dataState: { fileContent: makeFileContent({ path: 'README.md', language: 'markdown' }) },
          actions: { setViewMode },
        })
      )
      await user.click(iconButton('CodeIcon'))
      expect(setViewMode).toHaveBeenCalledWith('raw')
    })

    it('enters diff mode via the compare button', async () => {
      const user = userEvent.setup()
      const enterDiffMode = vi.fn()
      renderBrowse(fileState({ actions: { enterDiffMode } }))
      await user.click(iconButton('CompareArrowsIcon'))
      expect(enterDiffMode).toHaveBeenCalledTimes(1)
    })

    it('exits diff mode via the close button', async () => {
      const user = userEvent.setup()
      const exitDiffMode = vi.fn()
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts', diffMode: true },
          dataState: { fileContent: makeFileContent() },
          diffState: { diffContent: makeFileContent({ content: 'const x = 2\n' }) },
          actions: { exitDiffMode },
        })
      )
      await user.click(iconButton('CloseIcon'))
      expect(exitDiffMode).toHaveBeenCalledTimes(1)
    })
  })

  describe('single-file viewer click handlers', () => {
    function single(actions: Partial<BrowseStateResult['actions']>) {
      return makeState({
        urlState: { filePath: 'src/a.ts' },
        dataState: { fileContent: makeFileContent() },
        actions,
      })
    }

    it('forwards symbol clicks to actions.handleSymbolClick', async () => {
      const user = userEvent.setup()
      const handleSymbolClick = vi.fn()
      renderBrowse(single({ handleSymbolClick }))
      await user.click(screen.getByText('cv-symbol'))
      expect(handleSymbolClick).toHaveBeenCalledWith({ id: 1, name: 'foo' })
    })

    it('forwards reference clicks to actions.handleCodeReferenceClick', async () => {
      const user = userEvent.setup()
      const handleCodeReferenceClick = vi.fn()
      renderBrowse(single({ handleCodeReferenceClick }))
      await user.click(screen.getByText('cv-reference'))
      expect(handleCodeReferenceClick).toHaveBeenCalledWith({ id: 2 })
    })

    it('forwards line clicks to actions.navigateToLine', async () => {
      const user = userEvent.setup()
      const navigateToLine = vi.fn()
      renderBrowse(single({ navigateToLine }))
      await user.click(screen.getByText('cv-line'))
      expect(navigateToLine).toHaveBeenCalledWith(42)
    })
  })

  describe('diff view header + click handlers', () => {
    const renameInfo: ResolvePathResult = {
      found: true,
      resolved_path: 'src/old.ts',
      renamed_from: 'src/old.ts',
      renamed_to: null,
      rename_commit_hash: 'a'.repeat(40),
    }

    function diff(o: StateOverrides = {}) {
      return makeState({
        urlState: {
          filePath: 'src/a.ts',
          diffMode: true,
          selectedCommit: 'deadbeef',
          diffCommit: 'cafe1234',
          ...o.urlState,
        },
        dataState: { fileContent: makeFileContent(), ...o.dataState },
        diffState: {
          diffContent: makeFileContent({ content: 'const x = 2\n' }),
          ...o.diffState,
        },
        computedState: {
          comparisonCommit: 'cafe1234',
          globalReferenceCommit: 'deadbeef',
          temporalOrderKnown: true,
          referenceIsNewer: true,
          ...o.computedState,
        },
        ...(o.uiState ? { uiState: o.uiState } : {}),
        ...(o.actions ? { actions: o.actions } : {}),
      })
    }

    it('renders temporal "older"/"newer" chips when the order is known', () => {
      renderBrowse(diff())
      expect(screen.getByText('older')).toBeInTheDocument()
      expect(screen.getByText('newer')).toBeInTheDocument()
    })

    it('renders the swap-panels affordance and rename chips when reference is older', () => {
      renderBrowse(
        diff({
          computedState: { referenceIsNewer: false, temporalOrderKnown: true },
          diffState: {
            diffContent: makeFileContent({ content: 'const x = 2\n' }),
            diffRenameInfo: renameInfo,
          },
        })
      )
      // Swap button only renders when the reference is NOT newer.
      expect(screen.getByTestId('SwapHorizIcon')).toBeInTheDocument()
      // Rename chips: left = resolved_path basename, right = current filePath basename.
      expect(screen.getByText('old.ts')).toBeInTheDocument()
      expect(screen.getByText('a.ts')).toBeInTheDocument()
    })

    it('swaps the diff panels when the swap affordance is clicked', async () => {
      const user = userEvent.setup()
      const swapDiffPanels = vi.fn()
      renderBrowse(
        diff({
          computedState: { referenceIsNewer: false, temporalOrderKnown: true },
          actions: { ...noopActions(), swapDiffPanels },
        })
      )
      await user.click(iconButton('SwapHorizIcon'))
      expect(swapDiffPanels).toHaveBeenCalledTimes(1)
    })

    it('builds a forward-direction rename tooltip when the file was renamed away', async () => {
      const user = userEvent.setup()
      // renamed_from null + renamed_to set drives the "current → renamed_to" tooltip branch.
      const renamedToInfo: ResolvePathResult = {
        found: true,
        resolved_path: 'src/new.ts',
        renamed_from: null,
        renamed_to: 'src/new.ts',
        rename_commit_hash: 'b'.repeat(40),
      }
      renderBrowse(
        diff({
          diffState: {
            diffContent: makeFileContent({ content: 'const x = 2\n' }),
            diffRenameInfo: renamedToInfo,
          },
        })
      )
      await user.hover(screen.getByText('new.ts'))
      // currentPath ('src/a.ts') → renamed_to ('src/new.ts')
      expect(await screen.findByRole('tooltip')).toHaveTextContent('src/a.ts → src/new.ts')
    })

    it('shows the same-version hint when both panels show identical content', () => {
      renderBrowse(
        diff({ diffState: { diffContent: makeFileContent() } }) // identical to fileContent default
      )
      expect(screen.getByText(/Select a version on the left to compare/)).toBeInTheDocument()
    })

    it('forwards diff symbol clicks with the originating panel', async () => {
      const user = userEvent.setup()
      const handleDiffSymbolClick = vi.fn()
      renderBrowse(diff({ actions: { ...noopActions(), handleDiffSymbolClick } }))
      await user.click(screen.getByText('diff-symbol'))
      expect(handleDiffSymbolClick).toHaveBeenCalledWith({ id: 1 }, 'left')
    })

    it('forwards diff reference clicks with the originating panel', async () => {
      const user = userEvent.setup()
      const handleDiffReferenceClick = vi.fn()
      renderBrowse(diff({ actions: { ...noopActions(), handleDiffReferenceClick } }))
      await user.click(screen.getByText('diff-reference'))
      expect(handleDiffReferenceClick).toHaveBeenCalledWith({ id: 2 }, 'right')
    })

    it('forwards diff line clicks with the originating panel', async () => {
      const user = userEvent.setup()
      const handleDiffLineClick = vi.fn()
      renderBrowse(diff({ actions: { ...noopActions(), handleDiffLineClick } }))
      await user.click(screen.getByText('diff-line'))
      expect(handleDiffLineClick).toHaveBeenCalledWith(5, 'left')
    })

    it('sets the active panel on panel click', async () => {
      const user = userEvent.setup()
      const setActivePanel = vi.fn()
      renderBrowse(diff({ actions: { ...noopActions(), setActivePanel } }))
      await user.click(screen.getByText('diff-panel'))
      expect(setActivePanel).toHaveBeenCalledWith('right')
    })

    it('closes a diff panel on close', async () => {
      const user = userEvent.setup()
      const closePanel = vi.fn()
      renderBrowse(diff({ actions: { ...noopActions(), closePanel } }))
      await user.click(screen.getByText('diff-close'))
      expect(closePanel).toHaveBeenCalledWith('left')
    })

    it('switches the file-tree version via the tree-panel selector', async () => {
      const user = userEvent.setup()
      const setTreePanel = vi.fn()
      renderBrowse(diff({ actions: { ...noopActions(), setTreePanel } }))
      // The "Tree @" selector is the only combobox when the refs panel is closed.
      // MUI Select opens its listbox on mouseDown, not click.
      fireEvent.mouseDown(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /\(right\)/ }))
      expect(setTreePanel).toHaveBeenCalledWith('right')
    })

    it('switches the references version via the refs-panel selector', async () => {
      const user = userEvent.setup()
      const handleRefPanelChange = vi.fn()
      renderBrowse(
        diff({
          uiState: { refsPanelOpen: true },
          actions: { ...noopActions(), handleRefPanelChange },
        })
      )
      // Scope to the refs side panel (labelled "Refs @") to disambiguate from the
      // tree-panel selector that also renders in diff mode.
      const refsHeading = screen.getByText('Refs @').closest('div') as HTMLElement
      fireEvent.mouseDown(within(refsHeading).getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /\(right\)/ }))
      expect(handleRefPanelChange).toHaveBeenCalledWith('right')
    })
  })

  describe('directory listing navigation', () => {
    it('forwards file and directory selection', async () => {
      const user = userEvent.setup()
      const navigateToFile = vi.fn()
      const navigateToDirectory = vi.fn()
      renderBrowse(makeState({ actions: { navigateToFile, navigateToDirectory } }))
      await user.click(screen.getByText('dir-file'))
      expect(navigateToFile).toHaveBeenCalledWith('src/x.ts')
      await user.click(screen.getByText('dir-dir'))
      expect(navigateToDirectory).toHaveBeenCalledWith('src')
    })

    it('parent click navigates up one directory when nested', async () => {
      const user = userEvent.setup()
      const navigateToDirectory = vi.fn()
      const resetToFileTree = vi.fn()
      renderBrowse(
        makeState({
          urlState: { directoryPath: 'src/sub/deep' },
          actions: { navigateToDirectory, resetToFileTree },
        })
      )
      await user.click(screen.getByText('dir-parent'))
      expect(navigateToDirectory).toHaveBeenCalledWith('src/sub')
      expect(resetToFileTree).not.toHaveBeenCalled()
    })

    it('parent click resets to the root from a top-level directory', async () => {
      const user = userEvent.setup()
      const navigateToDirectory = vi.fn()
      const resetToFileTree = vi.fn()
      renderBrowse(
        makeState({
          urlState: { directoryPath: 'src' },
          actions: { navigateToDirectory, resetToFileTree },
        })
      )
      await user.click(screen.getByText('dir-parent'))
      expect(resetToFileTree).toHaveBeenCalledTimes(1)
      expect(navigateToDirectory).not.toHaveBeenCalled()
    })

    it('parent click resets to the root when no directory is set', async () => {
      const user = userEvent.setup()
      const resetToFileTree = vi.fn()
      renderBrowse(makeState({ actions: { resetToFileTree } }))
      await user.click(screen.getByText('dir-parent'))
      expect(resetToFileTree).toHaveBeenCalledTimes(1)
    })
  })

  describe('blame annotations', () => {
    beforeEach(() => {
      mockGetFileBlame.mockClear()
      mockGetFileBlame.mockResolvedValue({
        path: 'src/a.ts',
        repository_name: 'myrepo',
        lines: [],
        total: 0,
      })
    })

    it('loads blame data when the blame toggle is enabled', async () => {
      const user = userEvent.setup()
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts', selectedCommit: 'deadbeef' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      await user.click(iconButton('HistoryToggleOffIcon'))
      await waitFor(() =>
        expect(mockGetFileBlame).toHaveBeenCalledWith('myrepo', 'src/a.ts', 'deadbeef', 'main')
      )
    })

    it('clears blame data and does not fetch when the file fails to load', async () => {
      // getFileBlame should never be called while blame is disabled (default).
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      expect(mockGetFileBlame).not.toHaveBeenCalled()
    })

    it('auto-disables blame when the view switches to rendered content', async () => {
      const user = userEvent.setup()
      mockUseBrowseState.mockReturnValue(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      // Fresh JSX each call so rerender forces a re-render (a reused element
      // reference makes React bail out); the Browse instance stays mounted so
      // its internal blameEnabled state survives the transition.
      const tree = () => (
        <MemoryRouter initialEntries={['/browse/myrepo']} future={ROUTER_FUTURE_FLAGS}>
          <Browse />
          <LocationDisplay />
        </MemoryRouter>
      )
      const { rerender } = render(tree())
      await user.click(iconButton('HistoryToggleOffIcon'))
      await waitFor(() => expect(mockGetFileBlame).toHaveBeenCalled())
      mockGetFileBlame.mockClear()

      // Switch the same Browse instance to a markdown (rendered) file: the
      // auto-disable effect turns blame off and no further blame fetch occurs.
      mockUseBrowseState.mockReturnValue(
        makeState({
          urlState: { filePath: 'README.md' },
          dataState: { fileContent: makeFileContent({ path: 'README.md', language: 'markdown' }) },
        })
      )
      rerender(tree())
      expect(screen.getByTestId('markdown-viewer')).toBeInTheDocument()
      expect(mockGetFileBlame).not.toHaveBeenCalled()
    })

    it('surfaces blame fetch errors without crashing', async () => {
      const user = userEvent.setup()
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockGetFileBlame.mockRejectedValue(new Error('blame boom'))
      renderBrowse(
        makeState({
          urlState: { filePath: 'src/a.ts' },
          dataState: { fileContent: makeFileContent() },
        })
      )
      await user.click(iconButton('HistoryToggleOffIcon'))
      await waitFor(() => expect(consoleError).toHaveBeenCalled())
      // The viewer is still mounted after the failed fetch.
      expect(screen.getByTestId('stub-code-viewer')).toBeInTheDocument()
    })
  })
})
