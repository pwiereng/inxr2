import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import LogicalView from './LogicalView'
import type { TabValue } from '@/components/CodeHeader'
import type {
  Repository,
  Symbol as ApiSymbol,
  SymbolTreeFile,
  SymbolTreeSymbol,
  SymbolTreeResponse,
} from '@/lib/api'

// LogicalView reaches the API through these four functions. Mock the module so
// each test drives the loading / error / empty / populated branches directly.
vi.mock('@/lib/api', () => ({
  getSymbolTree: vi.fn(),
  searchSymbols: vi.fn(),
  getRepositoryByName: vi.fn(),
  getCommits: vi.fn(),
}))

// Stub CodeHeader with one button per callback so the header-driven navigation
// handlers (handleTabChange/Repo/Branch/Commit) are actually exercised.
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

// Stub the context menu with one button per callback so the menu-driven
// handlers (copy name / search symbol / go to definition) are exercised. It
// only renders when a context-menu state is present, mirroring the real one.
vi.mock('@/components/SymbolContextMenu', () => ({
  SymbolContextMenu: (props: {
    contextMenu: unknown | null
    onCopyName: () => void
    onSearchSymbol: () => void
    onGoToDefinition: () => void
    onClose: () => void
  }) =>
    props.contextMenu ? (
      <div data-testid="ctx-menu">
        <button onClick={props.onCopyName}>ctx-copy</button>
        <button onClick={props.onSearchSymbol}>ctx-search</button>
        <button onClick={props.onGoToDefinition}>ctx-goto</button>
        <button onClick={props.onClose}>ctx-close</button>
      </div>
    ) : null,
}))
// Stub the selection toolbar to expose its copy/search callbacks as buttons.
vi.mock('@/components/SelectionToolbar', () => ({
  SelectionToolbar: (props: { onCopy: () => void; onSearch: () => void }) => (
    <div data-testid="sel-toolbar">
      <button onClick={props.onCopy}>sel-copy</button>
      <button onClick={props.onSearch}>sel-search</button>
    </div>
  ),
}))
// Drive the toolbar with a selected-text payload so onSearch/onCopy have content.
vi.mock('@/hooks/useSelectionToolbar', () => ({
  useSelectionToolbar: () => ({
    toolbar: { selectedText: 'picked', x: 0, y: 0 },
    containerRef: { current: null },
    handleClose: vi.fn(),
  }),
}))

import { getSymbolTree, searchSymbols, getRepositoryByName, getCommits } from '@/lib/api'
const mockGetSymbolTree = vi.mocked(getSymbolTree)
const mockSearchSymbols = vi.mocked(searchSymbols)
const mockGetRepositoryByName = vi.mocked(getRepositoryByName)
const mockGetCommits = vi.mocked(getCommits)

function LocationDisplay() {
  const loc = useLocation()
  return <div data-testid="location">{loc.pathname + loc.search}</div>
}

function renderView(entry = '/logical-view?repo=myrepo&branch=main&commit=deadbeef') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <LogicalView />
      <LocationDisplay />
    </MemoryRouter>
  )
}

function makeFile(overrides: Partial<SymbolTreeFile> = {}): SymbolTreeFile {
  return {
    file_id: 1,
    path: 'src/app.py',
    language: 'python',
    symbol_count: 2,
    kind_counts: {},
    all_kind_counts: { function: 2 },
    ...overrides,
  }
}

function makeTreeSymbol(overrides: Partial<SymbolTreeSymbol> = {}): SymbolTreeSymbol {
  return {
    id: 100,
    name: 'doThing',
    kind: 'function',
    start_line: 5,
    end_line: 9,
    file_path: 'src/app.py',
    has_children: false,
    signature: null,
    inheritance: [],
    ...overrides,
  }
}

function makeApiSymbol(overrides: Partial<ApiSymbol> = {}): ApiSymbol {
  return {
    id: 200,
    name: 'MyClass',
    qualified_name: 'MyClass',
    kind: 'class',
    file_id: 1,
    file_path: 'src/app.py',
    repository_id: 1,
    commit_id: 1,
    start_line: 1,
    start_column: 0,
    end_line: 20,
    end_column: 0,
    signature: null,
    docstring: null,
    ...overrides,
  }
}

// A tier-1 (files) symbol-tree response.
function tier1(
  files: SymbolTreeFile[],
  kinds: string[] = ['class', 'function']
): SymbolTreeResponse {
  return {
    repository_id: 1,
    files,
    symbols: null,
    available_kinds: kinds,
    total_kind_counts: { function: 2, class: 1 },
  }
}

// A tier-2/3 (symbols) symbol-tree response.
function tierSymbols(symbols: SymbolTreeSymbol[]): SymbolTreeResponse {
  return {
    repository_id: 1,
    files: null,
    symbols,
    available_kinds: null,
    total_kind_counts: null,
  }
}

function makeRepo(overrides: Partial<Repository> = {}): Repository {
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

describe('LogicalView', () => {
  beforeEach(() => {
    mockGetSymbolTree.mockReset()
    mockSearchSymbols.mockReset()
    mockGetRepositoryByName.mockReset()
    mockGetCommits.mockReset()
    // The branch/commit-resolution effect only runs when they are absent from
    // the URL; default these to a no-op rejection so handler tests that navigate
    // to a bare ?repo=… don't have the resolver rewrite the URL underneath them.
    mockGetRepositoryByName.mockRejectedValue(new Error('not needed'))
    mockGetCommits.mockResolvedValue({ commits: [], total: 0 })
    mockSearchSymbols.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 })
    // jsdom lacks scrollIntoView; the URL-driven auto-expand effect calls it.
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('render branches', () => {
    it('prompts to select a repository when no repo param is present', () => {
      renderView('/logical-view')
      expect(
        screen.getByText('Select a repository to browse its symbol hierarchy')
      ).toBeInTheDocument()
      expect(mockGetSymbolTree).not.toHaveBeenCalled()
    })

    it('shows a loading spinner while the symbol tree is being fetched', () => {
      mockGetSymbolTree.mockReturnValue(new Promise(() => {}))
      renderView()
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    it('renders the error message when getSymbolTree rejects', async () => {
      mockGetSymbolTree.mockRejectedValue(new Error('tree boom'))
      renderView()
      await waitFor(() => expect(screen.getByText('tree boom')).toBeInTheDocument())
    })

    it('renders the empty state when the repository has no files', async () => {
      mockGetSymbolTree.mockResolvedValue(tier1([]))
      renderView()
      await waitFor(() =>
        expect(screen.getByText('No symbols found in this repository')).toBeInTheDocument()
      )
    })

    it('renders the file tree and a summary when populated', async () => {
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile({ path: 'src/app.py' })]))
      renderView()
      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      expect(screen.getByText('src/')).toBeInTheDocument()
      // Summary bar reports the filtered file count.
      expect(screen.getByText('files')).toBeInTheDocument()
    })

    it('passes repo/branch/commit through to getSymbolTree', async () => {
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      renderView('/logical-view?repo=myrepo&branch=dev&commit=cafe')
      await waitFor(() =>
        expect(mockGetSymbolTree).toHaveBeenCalledWith('myrepo', {
          branch: 'dev',
          commit: 'cafe',
        })
      )
    })
  })

  describe('branch/commit resolution effect', () => {
    it('resolves the default branch and latest commit into the URL when missing', async () => {
      mockGetRepositoryByName.mockResolvedValue(makeRepo({ default_branch: 'main' }))
      mockGetCommits.mockResolvedValue({
        commits: [
          {
            hash: 'f'.repeat(40),
            short_hash: 'fffffff',
            message: 'latest',
            author_name: 'A',
            author_email: 'a@example.com',
            commit_date: '2026-01-01T00:00:00Z',
            is_indexed: true,
            tags: [],
            is_branch_specific: false,
            is_merge_base: false,
          },
        ],
        total: 1,
      })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      renderView('/logical-view?repo=myrepo')

      await waitFor(() => {
        const loc = screen.getByTestId('location')
        expect(loc).toHaveTextContent('branch=main')
        expect(loc).toHaveTextContent(`commit=${'f'.repeat(40)}`)
      })
      expect(mockGetRepositoryByName).toHaveBeenCalledWith('myrepo')
    })
  })

  describe('header navigation handlers', () => {
    beforeEach(() => {
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
    })

    it('handleRepoChange resets to the new repo and drops branch/commit', async () => {
      const user = userEvent.setup({ delay: null })
      renderView('/logical-view?repo=old&branch=main&commit=deadbeef')
      await user.click(screen.getByText('hdr-repo'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/logical-view?repo=newrepo')
      expect(loc).not.toHaveTextContent('branch')
      expect(loc).not.toHaveTextContent('commit')
    })

    it('handleBranchChange sets the branch and drops the commit', async () => {
      const user = userEvent.setup({ delay: null })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')
      await user.click(screen.getByText('hdr-branch'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('branch=newbranch')
      expect(loc).toHaveTextContent('repo=myrepo')
      expect(loc).not.toHaveTextContent('commit')
    })

    it('handleCommitChange sets the commit and keeps repo/branch', async () => {
      const user = userEvent.setup({ delay: null })
      renderView('/logical-view?repo=myrepo&branch=main')
      await user.click(screen.getByText('hdr-commit'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('commit=abc123')
      expect(loc).toHaveTextContent('repo=myrepo')
      expect(loc).toHaveTextContent('branch=main')
    })

    it('handleTabChange navigates to each tab, preserving repo/branch/commit', async () => {
      const user = userEvent.setup({ delay: null })
      const cases: Array<[string, string]> = [
        ['hdr-browse', '/browse/myrepo'],
        ['hdr-search', '/search'],
        ['hdr-history', '/history'],
        ['hdr-deps', '/dependencies'],
        ['hdr-help', '/help'],
      ]
      for (const [button, path] of cases) {
        const { unmount } = renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')
        await user.click(screen.getByText(button))
        const loc = screen.getByTestId('location')
        expect(loc).toHaveTextContent(path)
        // handleTabChange threads all three params into the destination query;
        // assert each survives so a regression dropping `?${params}` is caught.
        expect(loc).toHaveTextContent('repo=myrepo')
        expect(loc).toHaveTextContent('branch=main')
        expect(loc).toHaveTextContent('commit=deadbeef')
        unmount()
      }
    })

    it('handleTabChange → logical-view stays on the logical-view page', async () => {
      const user = userEvent.setup({ delay: null })
      renderView('/logical-view?repo=myrepo&branch=main')
      await user.click(screen.getByText('hdr-logical'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/logical-view?repo=myrepo')
      expect(loc).toHaveTextContent('branch=main')
    })

    it('handleTabChange → browse with no repo falls back to the home route', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockReset()
      renderView('/logical-view')
      await user.click(screen.getByText('hdr-browse'))
      // Exact match, not toHaveTextContent('/') — the starting '/logical-view'
      // already contains '/', so a substring check could not catch a regression
      // that left us on the original page (CONTRIBUTING Page-Test Convention #4).
      const loc = screen.getByTestId('location')
      expect(loc.textContent).toBe('/')
      expect(loc).not.toHaveTextContent('logical-view')
    })
  })

  describe('symbol navigation', () => {
    it('handleSymbolClick navigates to the browse view with the encoded path and line', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([
            makeTreeSymbol({ id: 100, name: 'doThing', start_line: 5, file_path: 'src/app.py' }),
          ])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')

      // Expand the file to reveal its symbols.
      await user.click(await screen.findByText('app.py'))
      const goButton = await screen.findByRole('button', { name: 'Go to line 5' })
      await user.click(goButton)

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/browse/myrepo/src/app.py')
      expect(loc).toHaveTextContent('branch=main')
      expect(loc).toHaveTextContent('commit=deadbeef')
      expect(loc).toHaveTextContent('line=5')
    })

    it('handleInheritanceClick navigates to the inheritance target on a plain click', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([
            makeTreeSymbol({
              id: 100,
              name: 'Derived',
              kind: 'class',
              has_children: false,
              inheritance: [
                {
                  reference_text: 'Base',
                  target_symbol_id: 99,
                  target_file_id: 2,
                  target_file_path: 'src/base.py',
                  target_line: 10,
                },
              ],
            }),
          ])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')

      await user.click(await screen.findByText('app.py'))
      // A plain (non-Cmd/Ctrl) click on the "extends" chip navigates to Browse.
      await user.click(await screen.findByText('extends Base'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/browse/myrepo/src/base.py')
      expect(loc).toHaveTextContent('branch=main')
      expect(loc).toHaveTextContent('commit=deadbeef')
      expect(loc).toHaveTextContent('line=10')
    })
  })

  describe('filtering', () => {
    it('filters the file list by the include-files text', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(
        tier1([
          makeFile({ file_id: 1, path: 'src/app.py' }),
          makeFile({ file_id: 2, path: 'src/util.py' }),
        ])
      )
      renderView()

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      expect(screen.getByText('util.py')).toBeInTheDocument()

      await user.type(screen.getByPlaceholderText('Include files...'), 'util')

      await waitFor(() => expect(screen.queryByText('app.py')).not.toBeInTheDocument())
      expect(screen.getByText('util.py')).toBeInTheDocument()
    })
  })

  describe('filter-bar interactions', () => {
    it('clicking a kind chip enters kind mode and reflects it in the URL', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()], ['class', 'function']))
      mockSearchSymbols.mockResolvedValue({
        items: [makeApiSymbol({ id: 201, name: 'AClass', kind: 'class' })],
        total: 1,
        limit: 100,
        offset: 0,
      })
      renderView()

      const chip = await screen.findByRole('button', { name: 'function' })
      await user.click(chip)

      await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('kind=function'))
      expect(mockSearchSymbols).toHaveBeenCalledWith(
        expect.objectContaining({ kind: 'function', repository_id: 1 })
      )
    })

    it('selecting a language chip filters the file list and updates the URL', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(
        tier1([
          makeFile({ file_id: 1, path: 'src/app.py', language: 'python' }),
          makeFile({ file_id: 2, path: 'src/main.ts', language: 'typescript' }),
        ])
      )
      renderView()

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      await user.click(screen.getByRole('button', { name: 'typescript' }))

      await waitFor(() => expect(screen.queryByText('app.py')).not.toBeInTheDocument())
      expect(screen.getByText('main.ts')).toBeInTheDocument()
      expect(screen.getByTestId('location')).toHaveTextContent('language=typescript')
    })

    it('the find-symbol field issues a debounced search and applies the match filter', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(
        tier1([
          makeFile({ file_id: 1, path: 'src/app.py' }),
          makeFile({ file_id: 2, path: 'src/other.py' }),
        ])
      )
      // The search only matches a symbol in file 1, so the match-file-id filter
      // should keep app.py and drop other.py.
      mockSearchSymbols.mockResolvedValue({
        items: [makeApiSymbol({ id: 300, file_id: 1 })],
        total: 1,
        limit: 200,
        offset: 0,
      })
      renderView()

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      expect(screen.getByText('other.py')).toBeInTheDocument()
      await user.type(screen.getByPlaceholderText('Find symbol...'), 'doThing')

      await waitFor(() =>
        expect(mockSearchSymbols).toHaveBeenCalledWith(
          expect.objectContaining({ q: 'doThing', repository_id: 1 })
        )
      )
      // The matched file survives; the non-matching file is filtered out.
      await waitFor(() => expect(screen.queryByText('other.py')).not.toBeInTheDocument())
      expect(screen.getByText('app.py')).toBeInTheDocument()
    })
  })

  describe('kind mode', () => {
    it('loads and renders kind symbols when a kind is active in the URL', async () => {
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      mockSearchSymbols.mockResolvedValue({
        items: [makeApiSymbol({ id: 200, name: 'MyClass', kind: 'class' })],
        total: 1,
        limit: 100,
        offset: 0,
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=class')

      await waitFor(() => expect(screen.getByText('MyClass')).toBeInTheDocument())
      expect(mockSearchSymbols).toHaveBeenCalledWith(
        expect.objectContaining({ kind: 'class', repository_id: 1 })
      )
    })

    it('renders the kind-mode empty state when no symbols match', async () => {
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      mockSearchSymbols.mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=function')

      await waitFor(() => expect(screen.getByText('No function symbols found')).toBeInTheDocument())
    })

    it('switchToOutline leaves kind mode and pins the file in the URL', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      mockSearchSymbols.mockResolvedValue({
        items: [
          makeApiSymbol({ id: 400, name: 'handler', kind: 'function', file_path: 'src/app.py' }),
        ],
        total: 1,
        limit: 100,
        offset: 0,
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=function')

      // The kind-symbol row exposes its file path as a "view in outline" link.
      await user.click(await screen.findByText('app.py'))

      const loc = screen.getByTestId('location')
      await waitFor(() => expect(loc).toHaveTextContent('file=src%2Fapp.py'))
      expect(loc).not.toHaveTextContent('kind=')
    })
  })

  describe('URL-driven auto-expand', () => {
    it('expands the file named by the ?file= param and reveals its symbols', async () => {
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([makeTreeSymbol({ id: 100, name: 'doThing', start_line: 5 })])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&file=src/app.py')

      // The symbol becomes visible without any user interaction.
      expect(await screen.findByText('doThing()')).toBeInTheDocument()
      expect(mockGetSymbolTree).toHaveBeenCalledWith(
        'myrepo',
        expect.objectContaining({ file_id: 1 })
      )
    })

    it('auto-expands a container symbol from the URL, fetching its tier-3 children', async () => {
      // file_id → tier 2 with a has_children class; parent_symbol_id → tier 3 child.
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.parent_symbol_id === 100) {
          return tierSymbols([
            makeTreeSymbol({ id: 101, name: 'childMethod', kind: 'method', start_line: 7 }),
          ])
        }
        if (params?.file_id) {
          return tierSymbols([
            makeTreeSymbol({ id: 100, name: 'MyClass', kind: 'class', has_children: true }),
          ])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&file=src/app.py')

      // The auto-expand effect fetches children for the has_children symbol and
      // expands them, so the nested method is visible with no interaction.
      expect(await screen.findByText('childMethod()')).toBeInTheDocument()
      expect(mockGetSymbolTree).toHaveBeenCalledWith(
        'myrepo',
        expect.objectContaining({ parent_symbol_id: 100 })
      )
    })

    it('does nothing when the ?file= param names a file not in the tree', async () => {
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([makeTreeSymbol({ id: 100, name: 'doThing', start_line: 5 })])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&file=src/missing.py')

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      // The unknown file path matches no node, so no tier-2 fetch happens and the
      // file stays collapsed (only the tier-1 call was made).
      expect(mockGetSymbolTree).toHaveBeenCalledTimes(1)
      expect(screen.queryByText('doThing()')).not.toBeInTheDocument()
    })
  })

  describe('file expand / collapse (toggleFile)', () => {
    it('expands a file on click, fetches its symbols, then collapses on a second click', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([makeTreeSymbol({ id: 100, name: 'doThing', start_line: 5 })])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')

      const fileRow = await screen.findByText('app.py')
      await user.click(fileRow)
      expect(await screen.findByText('doThing()')).toBeInTheDocument()
      // Expanding pins the file in the URL.
      await waitFor(() =>
        expect(screen.getByTestId('location')).toHaveTextContent('file=src%2Fapp.py')
      )

      // Second click collapses (early-return path in toggleFile). MUI Collapse
      // keeps children mounted during the close animation, so assert the
      // collapse branch ran via the MuiCollapse-hidden wrapper class — and that
      // no extra tier-2 fetch was issued (the collapse path returns early).
      const callsBefore = mockGetSymbolTree.mock.calls.length
      await user.click(fileRow)
      await waitFor(() => expect(document.querySelector('.MuiCollapse-hidden')).toBeInTheDocument())
      expect(mockGetSymbolTree.mock.calls.length).toBe(callsBefore)
    })

    it('auto-expands child symbols when expanding a file with container symbols', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.parent_symbol_id === 100) {
          return tierSymbols([
            makeTreeSymbol({ id: 101, name: 'childMethod', kind: 'method', start_line: 7 }),
          ])
        }
        if (params?.file_id) {
          return tierSymbols([
            makeTreeSymbol({ id: 100, name: 'MyClass', kind: 'class', has_children: true }),
          ])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')

      await user.click(await screen.findByText('app.py'))
      // The has_children class triggers a tier-3 fetch and auto-expansion.
      expect(await screen.findByText('childMethod()')).toBeInTheDocument()
      expect(mockGetSymbolTree).toHaveBeenCalledWith(
        'myrepo',
        expect.objectContaining({ parent_symbol_id: 100 })
      )
    })
  })

  describe('symbol expand / collapse (toggleSymbol)', () => {
    it('expands a child container symbol, fetches its children, then collapses it', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.parent_symbol_id === 200) {
          return tierSymbols([
            makeTreeSymbol({ id: 201, name: 'innerFn', kind: 'function', start_line: 12 }),
          ])
        }
        if (params?.parent_symbol_id === 100) {
          // Auto-expanded outer class has one child class with its own children.
          return tierSymbols([
            makeTreeSymbol({ id: 200, name: 'Inner', kind: 'class', has_children: true }),
          ])
        }
        if (params?.file_id) {
          return tierSymbols([
            makeTreeSymbol({ id: 100, name: 'Outer', kind: 'class', has_children: true }),
          ])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')

      await user.click(await screen.findByText('app.py'))
      // Outer auto-expands; Inner (its child) is visible but collapsed.
      const innerRow = await screen.findByText('Inner')
      // Expand Inner — fetches its children (innerFn).
      await user.click(innerRow)
      expect(await screen.findByText('innerFn()')).toBeInTheDocument()
      expect(mockGetSymbolTree).toHaveBeenCalledWith(
        'myrepo',
        expect.objectContaining({ parent_symbol_id: 200 })
      )

      // Collapse Inner — early-return collapse path in toggleSymbol. Assert no
      // new fetch fired (collapse returns before any getSymbolTree call).
      const callsBefore = mockGetSymbolTree.mock.calls.length
      await user.click(innerRow)
      await waitFor(() => expect(document.querySelector('.MuiCollapse-hidden')).toBeInTheDocument())
      expect(mockGetSymbolTree.mock.calls.length).toBe(callsBefore)
    })
  })

  describe('inheritance Cmd/Ctrl+click', () => {
    it('Cmd+click on an extends chip locates the target file in the tree (no navigation)', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id === 2) {
          return tierSymbols([makeTreeSymbol({ id: 300, name: 'baseFn', start_line: 3 })])
        }
        if (params?.file_id === 1) {
          return tierSymbols([
            makeTreeSymbol({
              id: 100,
              name: 'Derived',
              kind: 'class',
              has_children: false,
              inheritance: [
                {
                  reference_text: 'Base',
                  target_symbol_id: 99,
                  target_file_id: 2,
                  target_file_path: 'src/base.py',
                  target_line: 10,
                },
              ],
            }),
          ])
        }
        return tier1([
          makeFile({ file_id: 1, path: 'src/app.py' }),
          makeFile({ file_id: 2, path: 'src/base.py' }),
        ])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')

      await user.click(await screen.findByText('app.py'))
      const chip = await screen.findByText('extends Base')
      // Cmd+click expands the target file in-tree instead of navigating to Browse.
      await user.keyboard('{Meta>}')
      await user.click(chip)
      await user.keyboard('{/Meta}')

      // The target file's symbols load in-place; URL stays on logical-view.
      expect(await screen.findByText('baseFn()')).toBeInTheDocument()
      expect(screen.getByTestId('location')).toHaveTextContent('/logical-view')
      expect(screen.getByTestId('location')).not.toHaveTextContent('/browse/')
    })
  })

  describe('filter-bar: exclude, reset, kind-count toggle, language deselect', () => {
    beforeEach(() => {
      mockGetSymbolTree.mockResolvedValue(
        tier1(
          [
            makeFile({ file_id: 1, path: 'src/app.py', language: 'python' }),
            makeFile({ file_id: 2, path: 'src/util.py', language: 'python' }),
          ],
          ['class', 'function']
        )
      )
    })

    it('excludes files matching the exclude-files text', async () => {
      const user = userEvent.setup({ delay: null })
      renderView()

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      await user.type(screen.getByPlaceholderText('Exclude files...'), 'util')

      await waitFor(() => expect(screen.queryByText('util.py')).not.toBeInTheDocument())
      expect(screen.getByText('app.py')).toBeInTheDocument()
    })

    it('toggles the kind-count visibility button in outline mode', async () => {
      const user = userEvent.setup({ delay: null })
      renderView()

      // The kind-count toggle only renders when activeKind === null (outline mode).
      const toggle = await screen.findByRole('button', { name: 'Show kind counts' })
      await user.click(toggle)
      // After toggling on, the tooltip flips to the hide label.
      expect(await screen.findByRole('button', { name: 'Hide kind counts' })).toBeInTheDocument()
    })

    it('the reset button clears filters and strips file/kind/language from the URL', async () => {
      const user = userEvent.setup({ delay: null })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&file=src/app.py')

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      await user.type(screen.getByPlaceholderText('Include files...'), 'app')
      await user.click(screen.getByRole('button', { name: 'Reset view' }))

      const loc = screen.getByTestId('location')
      await waitFor(() => expect(loc).not.toHaveTextContent('file='))
      expect(loc).not.toHaveTextContent('kind=')
      expect(loc).not.toHaveTextContent('language=')
      expect(loc).toHaveTextContent('repo=myrepo')
    })

    it('re-clicking the active language chip deselects it and clears the language param', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(
        tier1([
          makeFile({ file_id: 1, path: 'src/app.py', language: 'python' }),
          makeFile({ file_id: 2, path: 'src/main.ts', language: 'typescript' }),
        ])
      )
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&language=typescript')

      // Pre-selected via URL; the chip toggles off on click.
      const chip = await screen.findByRole('button', { name: 'typescript' })
      await user.click(chip)
      await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent('language='))
      expect(screen.getByText('app.py')).toBeInTheDocument()
    })

    it('clicking the active "Outline" chip while in kind mode returns to outline', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()], ['class', 'function']))
      mockSearchSymbols.mockResolvedValue({
        items: [makeApiSymbol({ id: 201, name: 'AClass', kind: 'class' })],
        total: 1,
        limit: 100,
        offset: 0,
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=function')

      const outlineChip = await screen.findByRole('button', { name: 'Outline' })
      await user.click(outlineChip)
      await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent('kind='))
    })

    it('re-clicking the active kind chip toggles back to outline mode', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()], ['class', 'function']))
      mockSearchSymbols.mockResolvedValue({
        items: [makeApiSymbol({ id: 201, name: 'AClass', kind: 'class' })],
        total: 1,
        limit: 100,
        offset: 0,
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=function')

      const chip = await screen.findByRole('button', { name: 'function' })
      await user.click(chip)
      await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent('kind='))
    })

    it('clears the find-symbol field via its clear button', async () => {
      const user = userEvent.setup({ delay: null })
      renderView()

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      const findField = screen.getByPlaceholderText('Find symbol...')
      await user.type(findField, 'doThing')
      expect(findField).toHaveValue('doThing')
      // The clear button (a ClearIcon IconButton) only renders once the field
      // has text. Scope to this field's TextField root so we click its own
      // clear button — exercising the onClick={() => setSymbolSearch('')} branch.
      const fieldRoot = findField.closest('.MuiTextField-root') as HTMLElement
      const clearButton = within(fieldRoot).getByRole('button')
      await user.click(clearButton)
      expect(findField).toHaveValue('')
    })
  })

  describe('kind mode: grouped symbols, load-more, branch/commit threading', () => {
    it('groups kind symbols under their parent class header', async () => {
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()], ['method', 'function']))
      mockSearchSymbols.mockResolvedValue({
        items: [
          makeApiSymbol({
            id: 500,
            name: 'doIt',
            qualified_name: 'MyClass.doIt',
            kind: 'method',
            file_path: 'src/app.py',
          }),
        ],
        total: 1,
        limit: 100,
        offset: 0,
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=method')

      // The class header (from qualified_name) and the method are both rendered.
      expect(await screen.findByText('MyClass')).toBeInTheDocument()
      expect(screen.getByText('doIt()')).toBeInTheDocument()
      // searchSymbols received branch + commit threaded from the URL.
      expect(mockSearchSymbols).toHaveBeenCalledWith(
        expect.objectContaining({ kind: 'method', branch: 'main', commit: 'deadbeef' })
      )
    })

    it('shows a Load more chip and fetches the next page when a full page returns', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()], ['function']))
      // First page: exactly KIND_PAGE_SIZE (100) items → hasMore is true.
      const page1 = Array.from({ length: 100 }, (_, i) =>
        makeApiSymbol({ id: 1000 + i, name: `fn${i}`, kind: 'function', qualified_name: `fn${i}` })
      )
      const page2 = [
        makeApiSymbol({ id: 2000, name: 'lastFn', kind: 'function', qualified_name: 'lastFn' }),
      ]
      mockSearchSymbols
        .mockResolvedValueOnce({ items: page1, total: 101, limit: 100, offset: 0 })
        .mockResolvedValueOnce({ items: page2, total: 101, limit: 100, offset: 100 })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=function')

      const loadMore = await screen.findByText('Load more')
      await user.click(loadMore)

      expect(await screen.findByText('lastFn()')).toBeInTheDocument()
      expect(mockSearchSymbols).toHaveBeenCalledWith(expect.objectContaining({ offset: 100 }))
    })

    it('expands a container symbol in kind mode and fetches its children', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.parent_symbol_id === 600) {
          return tierSymbols([
            makeTreeSymbol({ id: 601, name: 'method1', kind: 'method', start_line: 4 }),
          ])
        }
        return tier1([makeFile()], ['class'])
      })
      mockSearchSymbols.mockResolvedValue({
        items: [
          makeApiSymbol({
            id: 600,
            name: 'BigClass',
            qualified_name: 'BigClass',
            kind: 'class',
            file_path: 'src/app.py',
          }),
        ],
        total: 1,
        limit: 100,
        offset: 0,
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=class')

      // The grouped header and the expandable container row both say BigClass;
      // click the expand chevron row (ListItemButton) to toggle children.
      const rows = await screen.findAllByText('BigClass')
      await user.click(rows[rows.length - 1]!)
      expect(await screen.findByText('method1()')).toBeInTheDocument()
      expect(mockGetSymbolTree).toHaveBeenCalledWith(
        'myrepo',
        expect.objectContaining({ parent_symbol_id: 600 })
      )

      // Collapse again — early-return path in toggleKindSymbol. Assert no new
      // fetch fired (collapse returns before any getSymbolTree call).
      const callsBefore = mockGetSymbolTree.mock.calls.length
      await user.click(rows[rows.length - 1]!)
      await waitFor(() => expect(document.querySelector('.MuiCollapse-hidden')).toBeInTheDocument())
      expect(mockGetSymbolTree.mock.calls.length).toBe(callsBefore)
    })

    it('threads the selected language into the kind-mode search', async () => {
      mockGetSymbolTree.mockResolvedValue(
        tier1(
          [
            makeFile({ file_id: 1, path: 'src/app.py', language: 'python' }),
            makeFile({ file_id: 2, path: 'src/main.ts', language: 'typescript' }),
          ],
          ['function']
        )
      )
      mockSearchSymbols.mockResolvedValue({
        items: [makeApiSymbol({ id: 700, name: 'tsFn', kind: 'function' })],
        total: 1,
        limit: 100,
        offset: 0,
      })
      renderView(
        '/logical-view?repo=myrepo&branch=main&commit=deadbeef&kind=function&language=typescript'
      )

      await waitFor(() =>
        expect(mockSearchSymbols).toHaveBeenCalledWith(
          expect.objectContaining({ kind: 'function', language: 'typescript' })
        )
      )
    })
  })

  describe('branch/commit resolution effect — additional branches', () => {
    it('resolves only the commit when the branch is already present', async () => {
      mockGetRepositoryByName.mockResolvedValue(makeRepo({ default_branch: 'main' }))
      mockGetCommits.mockResolvedValue({
        commits: [
          {
            hash: 'a'.repeat(40),
            short_hash: 'aaaaaaa',
            message: 'latest',
            author_name: 'A',
            author_email: 'a@example.com',
            commit_date: '2026-01-01T00:00:00Z',
            is_indexed: true,
            tags: [],
            is_branch_specific: false,
            is_merge_base: false,
          },
        ],
        total: 1,
      })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      // branch present, commit absent → effectiveBranch uses URL branch (dev).
      renderView('/logical-view?repo=myrepo&branch=dev')

      await waitFor(() => {
        const loc = screen.getByTestId('location')
        expect(loc).toHaveTextContent('branch=dev')
        expect(loc).toHaveTextContent(`commit=${'a'.repeat(40)}`)
      })
      expect(mockGetCommits).toHaveBeenCalledWith('myrepo', 'dev', 1)
    })

    it('leaves the URL without a commit when no commits are returned', async () => {
      mockGetRepositoryByName.mockResolvedValue(makeRepo({ default_branch: 'main' }))
      mockGetCommits.mockResolvedValue({ commits: [], total: 0 })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      renderView('/logical-view?repo=myrepo')

      await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('branch=main'))
      // No commit could be resolved, so the param is never added.
      expect(screen.getByTestId('location')).not.toHaveTextContent('commit=')
    })

    it('silently does nothing when repository resolution fails', async () => {
      mockGetRepositoryByName.mockRejectedValue(new Error('no such repo'))
      mockGetSymbolTree.mockReturnValue(new Promise(() => {}))
      renderView('/logical-view?repo=myrepo')

      // The catch swallows the error; the URL keeps only the original repo param.
      await waitFor(() => expect(mockGetRepositoryByName).toHaveBeenCalled())
      expect(screen.getByTestId('location')).not.toHaveTextContent('branch=')
    })
  })

  describe('error + symbol-click edge branches', () => {
    it('falls back to a generic message when getSymbolTree rejects without an Error', async () => {
      mockGetSymbolTree.mockRejectedValue('plain string failure')
      renderView()
      await waitFor(() =>
        expect(screen.getByText('Failed to load symbol tree')).toBeInTheDocument()
      )
    })

    it('omits branch and commit from the browse URL when neither is set', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([makeTreeSymbol({ id: 100, name: 'doThing', start_line: 5 })])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      // Provide branch so files load, but no commit; then click a symbol.
      renderView('/logical-view?repo=myrepo&branch=main')

      await user.click(await screen.findByText('app.py'))
      await user.click(await screen.findByRole('button', { name: 'Go to line 5' }))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/browse/myrepo/src/app.py')
      expect(loc).toHaveTextContent('branch=main')
      expect(loc).toHaveTextContent('line=5')
      expect(loc).not.toHaveTextContent('commit=')
    })
  })

  describe('symbol search threading + tier-1 partial responses', () => {
    it('omits branch/commit from the symbol search when neither is in the URL', async () => {
      // No branch in the URL → files won't load, so seed the repositoryId via a
      // kind URL is not possible; instead drive search with branch present only.
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile({ file_id: 1, path: 'src/app.py' })]))
      mockSearchSymbols.mockResolvedValue({
        items: [makeApiSymbol({ id: 300, file_id: 1 })],
        total: 1,
        limit: 200,
        offset: 0,
      })
      // branch present (so files load) but commit absent.
      renderView('/logical-view?repo=myrepo&branch=main')

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      await user.type(screen.getByPlaceholderText('Find symbol...'), 'doThing')

      await waitFor(() =>
        expect(mockSearchSymbols).toHaveBeenCalledWith(
          expect.objectContaining({ q: 'doThing', branch: 'main' })
        )
      )
      const call = mockSearchSymbols.mock.calls.find(([a]) => a.q === 'doThing')
      expect(call?.[0].commit).toBeUndefined()
    })

    it('handles a tier-1 response that omits available_kinds and total_kind_counts', async () => {
      // result.files present but available_kinds / total_kind_counts null → the
      // corresponding setters are skipped (falsy branches).
      mockGetSymbolTree.mockResolvedValue({
        repository_id: 1,
        files: [makeFile({ file_id: 1, path: 'src/app.py' })],
        symbols: null,
        available_kinds: null,
        total_kind_counts: null,
      })
      renderView()

      await waitFor(() => expect(screen.getByText('app.py')).toBeInTheDocument())
      // No kind chips render when available_kinds is null.
      expect(screen.queryByRole('button', { name: 'function' })).not.toBeInTheDocument()
    })

    it('handles a tier-1 response with a null files array', async () => {
      // result.files null → setFiles is skipped, leaving the empty state.
      mockGetSymbolTree.mockResolvedValue({
        repository_id: 1,
        files: null,
        symbols: null,
        available_kinds: ['class'],
        total_kind_counts: { class: 1 },
      })
      renderView()

      await waitFor(() =>
        expect(screen.getByText('No symbols found in this repository')).toBeInTheDocument()
      )
    })
  })

  describe('inheritance plain-click edge branches', () => {
    it('omits branch/commit/line from the browse URL when none are available', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([
            makeTreeSymbol({
              id: 100,
              name: 'Derived',
              kind: 'class',
              has_children: false,
              inheritance: [
                {
                  reference_text: 'Base',
                  target_symbol_id: 99,
                  target_file_id: 2,
                  target_file_path: 'src/base.py',
                  target_line: null,
                },
              ],
            }),
          ])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      // branch present so files load, but no commit; target_line is null.
      renderView('/logical-view?repo=myrepo&branch=main')

      await user.click(await screen.findByText('app.py'))
      await user.click(await screen.findByText('extends Base'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/browse/myrepo/src/base.py')
      expect(loc).toHaveTextContent('branch=main')
      expect(loc).not.toHaveTextContent('commit=')
      expect(loc).not.toHaveTextContent('line=')
    })

    it('Cmd+click does nothing when the inheritance target has no file id', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([
            makeTreeSymbol({
              id: 100,
              name: 'Derived',
              kind: 'class',
              has_children: false,
              inheritance: [
                {
                  reference_text: 'Base',
                  target_symbol_id: 99,
                  target_file_id: null,
                  target_file_path: 'src/base.py',
                  target_line: 10,
                },
              ],
            }),
          ])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')

      await user.click(await screen.findByText('app.py'))
      const chip = await screen.findByText('extends Base')
      const callsBefore = mockGetSymbolTree.mock.calls.length
      await user.keyboard('{Meta>}')
      await user.click(chip)
      await user.keyboard('{/Meta}')

      // targetFileId == null → the handler returns early: no fetch, no nav.
      expect(mockGetSymbolTree.mock.calls.length).toBe(callsBefore)
      expect(screen.getByTestId('location')).not.toHaveTextContent('/browse/')
    })
  })

  describe('context-menu + selection-toolbar handlers', () => {
    // Right-click a symbol row to populate the context-menu state, then drive
    // each menu callback through the stubbed menu's buttons.
    async function openMenu(user: ReturnType<typeof userEvent.setup>) {
      mockGetSymbolTree.mockImplementation(async (_repo, params) => {
        if (params?.file_id) {
          return tierSymbols([
            makeTreeSymbol({ id: 100, name: 'doThing', start_line: 5, file_path: 'src/app.py' }),
          ])
        }
        return tier1([makeFile({ file_id: 1, path: 'src/app.py' })])
      })
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')
      await user.click(await screen.findByText('app.py'))
      const symbolRow = await screen.findByText('doThing()')
      await user.pointer({ keys: '[MouseRight]', target: symbolRow })
      await screen.findByTestId('ctx-menu')
    }

    it('go-to-definition from the context menu navigates to Browse', async () => {
      const user = userEvent.setup({ delay: null })
      await openMenu(user)
      await user.click(screen.getByText('ctx-goto'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/browse/myrepo/src/app.py')
      expect(loc).toHaveTextContent('line=5')
    })

    it('search-symbol from the context menu navigates to /search with the name', async () => {
      const user = userEvent.setup({ delay: null })
      await openMenu(user)
      await user.click(screen.getByText('ctx-search'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/search')
      expect(loc).toHaveTextContent('repo=myrepo')
      expect(loc).toHaveTextContent('query=doThing')
      expect(loc).toHaveTextContent('branch=main')
      expect(loc).toHaveTextContent('commit=deadbeef')
    })

    it('copy-name from the context menu writes the symbol name to the clipboard', async () => {
      const user = userEvent.setup({ delay: null })
      const writeText = vi.fn()
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText },
        configurable: true,
      })
      await openMenu(user)
      await user.click(screen.getByText('ctx-copy'))
      expect(writeText).toHaveBeenCalledWith('doThing')
    })

    it('selection-toolbar search navigates to /search with the selected text', async () => {
      const user = userEvent.setup({ delay: null })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')
      await screen.findByText('app.py')
      await user.click(screen.getByText('sel-search'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/search')
      expect(loc).toHaveTextContent('query=picked')
      expect(loc).toHaveTextContent('repo=myrepo')
    })

    it('selection-toolbar copy writes the selected text to the clipboard', async () => {
      const user = userEvent.setup({ delay: null })
      const writeText = vi.fn()
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText },
        configurable: true,
      })
      mockGetSymbolTree.mockResolvedValue(tier1([makeFile()]))
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')
      await screen.findByText('app.py')
      await user.click(screen.getByText('sel-copy'))
      expect(writeText).toHaveBeenCalledWith('picked')
    })
  })
})
