import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

// Keep the heavy context-menu / selection-toolbar machinery out of these tests.
vi.mock('@/components/SymbolContextMenu', () => ({
  SymbolContextMenu: () => null,
}))
vi.mock('@/components/SelectionToolbar', () => ({
  SelectionToolbar: () => null,
}))
vi.mock('@/hooks/useSelectionToolbar', () => ({
  useSelectionToolbar: () => ({
    toolbar: null,
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
      const user = userEvent.setup()
      renderView('/logical-view?repo=old&branch=main&commit=deadbeef')
      await user.click(screen.getByText('hdr-repo'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/logical-view?repo=newrepo')
      expect(loc).not.toHaveTextContent('branch')
      expect(loc).not.toHaveTextContent('commit')
    })

    it('handleBranchChange sets the branch and drops the commit', async () => {
      const user = userEvent.setup()
      renderView('/logical-view?repo=myrepo&branch=main&commit=deadbeef')
      await user.click(screen.getByText('hdr-branch'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('branch=newbranch')
      expect(loc).toHaveTextContent('repo=myrepo')
      expect(loc).not.toHaveTextContent('commit')
    })

    it('handleCommitChange sets the commit and keeps repo/branch', async () => {
      const user = userEvent.setup()
      renderView('/logical-view?repo=myrepo&branch=main')
      await user.click(screen.getByText('hdr-commit'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('commit=abc123')
      expect(loc).toHaveTextContent('repo=myrepo')
      expect(loc).toHaveTextContent('branch=main')
    })

    it('handleTabChange navigates to each tab, preserving repo/branch/commit', async () => {
      const user = userEvent.setup()
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
      const user = userEvent.setup()
      renderView('/logical-view?repo=myrepo&branch=main')
      await user.click(screen.getByText('hdr-logical'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/logical-view?repo=myrepo')
      expect(loc).toHaveTextContent('branch=main')
    })

    it('handleTabChange → browse with no repo falls back to the home route', async () => {
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
  })
})
