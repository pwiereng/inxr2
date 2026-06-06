import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
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
  }) => (
    // testid is "stub-code-viewer" to avoid colliding with the resizable Panel
    // whose id="code-viewer" surfaces as a data-testid in the DOM.
    <div data-testid="stub-code-viewer">
      <button onClick={() => props.onSearchText?.('needle')}>cv-search</button>
      <button onClick={() => props.onBlameCommitClick?.('c'.repeat(40))}>cv-blame</button>
    </div>
  ),
}))
vi.mock('@/components/DiffCodeViewer', () => ({
  DiffCodeViewer: (props: { onSearchText?: (t: string) => void }) => (
    <div data-testid="diff-code-viewer">
      <button onClick={() => props.onSearchText?.('needle')}>diff-search</button>
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
  DirectoryListing: () => <div data-testid="directory-listing" />,
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
type BrowseStateResult = ReturnType<typeof useBrowseState>
const mockUseBrowseState = vi.mocked(useBrowseState)

function LocationDisplay() {
  const loc = useLocation()
  return <div data-testid="location">{loc.pathname + loc.search}</div>
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
    <MemoryRouter initialEntries={[entry]}>
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

    it('shows the rename notice when the file resolves to a different path', () => {
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
        })
      )
      expect(screen.getByText(/this file was at src\/renamed\.ts/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Go to file' })).toBeInTheDocument()
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
  })
})
