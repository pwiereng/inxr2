import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@/test/utils'
import Search from './Search'
import * as api from '@/lib/api'

/**
 * Helper to find an element whose textContent matches, even when the text
 * is split across child elements (e.g., <mark> highlighting).
 */
function getByTextContent(text: string | RegExp) {
  return screen.getByText((_content, element) => {
    if (!element) return false
    const tc = element.textContent || ''
    const matches = text instanceof RegExp ? text.test(tc) : tc === text
    // Only match the deepest element that contains the full text
    // (avoid matching parent wrappers)
    if (!matches) return false
    const childrenMatch = Array.from(element.children).some((child) => {
      const ctc = child.textContent || ''
      return text instanceof RegExp ? text.test(ctc) : ctc === text
    })
    return !childrenMatch
  })
}

// Mock the API
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return {
    ...actual,
    searchText: vi.fn(),
    searchSymbols: vi.fn(),
    searchDependencies: vi.fn(),
    getRepositories: vi.fn(),
    getRepositoryBranches: vi.fn(),
    getCommits: vi.fn(),
    getFileExtensions: vi.fn(),
  }
})

const mockSearchText = vi.mocked(api.searchText)
const mockSearchSymbols = vi.mocked(api.searchSymbols)
const mockSearchDependencies = vi.mocked(api.searchDependencies)
const mockGetRepositories = vi.mocked(api.getRepositories)
const mockGetRepositoryBranches = vi.mocked(api.getRepositoryBranches)
const mockGetCommits = vi.mocked(api.getCommits)
const mockGetFileExtensions = vi.mocked(api.getFileExtensions)

describe('Search', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default mock responses
    mockGetRepositories.mockResolvedValue([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: 'Test repository',
        default_branch: 'main',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ])

    mockGetRepositoryBranches.mockResolvedValue({
      branches: [
        {
          name: 'main',
          commit_count: 10,
          last_indexed_commit: 'abc123',
          oldest_indexed_commit: 'abc123',
          last_indexed_at: '2024-01-01T00:00:00Z',
        },
      ],
    })

    mockGetCommits.mockResolvedValue({
      commits: [
        {
          hash: 'abc123',
          short_hash: 'abc123',
          message: 'Test commit',
          author_name: 'Test',
          author_email: 'test@test.com',
          commit_date: '2024-01-01T00:00:00Z',
          is_indexed: true,
          tags: [],
          is_branch_specific: false,
          is_merge_base: false,
        },
      ],
      total: 1,
    })

    mockGetFileExtensions.mockResolvedValue({
      extensions: ['.py', '.ts', '.tsx', '.js'],
    })

    mockSearchText.mockResolvedValue({
      results: [],
      total: 0,
      query: '',
      mode: 'keyword',
      limit: 20,
      offset: 0,
    })

    mockSearchSymbols.mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    })

    mockSearchDependencies.mockResolvedValue({
      results: [],
      total: 0,
      query: '',
      limit: 20,
      offset: 0,
    })
  })

  it('should render search page with empty state', async () => {
    render(<Search />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Enter search query...')).toBeInTheDocument()
    })

    expect(
      screen.getByText(
        /Enter a search query to find symbols, comments, docstrings, commit messages, dependencies, and files/i
      )
    ).toBeInTheDocument()
  })

  it('should render CodeHeader with Search tab active', async () => {
    render(<Search />)

    await waitFor(() => {
      // Should have tabs
      expect(screen.getByRole('tab', { name: /Browse/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /Search/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /History/i })).toBeInTheDocument()
    })
  })

  it('should call getRepositories on mount', async () => {
    render(<Search />)

    await waitFor(() => {
      expect(mockGetRepositories).toHaveBeenCalled()
    })
  })

  it('should display API error message', async () => {
    // Suppress expected console.error from the component's error handler
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      mockSearchText.mockRejectedValue(new Error('API error'))

      // Render with query param to trigger search
      window.history.pushState({}, '', '?query=test')
      render(<Search />)

      await waitFor(
        () => {
          expect(screen.getByText(/API error/i)).toBeInTheDocument()
        },
        { timeout: 1000 }
      )
    } finally {
      consoleSpy.mockRestore()
    }
  })

  it('should navigate to history when clicking a commit_message result', async () => {
    mockSearchText.mockResolvedValue({
      results: [
        {
          id: 1,
          source_type: 'commit_message',
          content: 'fix: update get_file_symbols_by_path',
          content_type: null,
          repository_id: 1,
          repository_name: 'test-repo',
          file_path: null,
          source_line: null,
          source_end_line: null,
          language: null,
          commit_hash: 'abc123',
          branch: 'main',
          headline: null,
          rank: 1.0,
        },
      ],
      total: 1,
      query: 'get_file_symbols_by_path',
      mode: 'keyword',
      limit: 20,
      offset: 0,
    })

    window.history.pushState({}, '', '?query=get_file_symbols_by_path')
    render(<Search />)

    // Wait for results to appear
    await waitFor(() => {
      expect(screen.getByText(/Commit Message/i)).toBeInTheDocument()
    })

    // Click the location link (repo name) to navigate — content text is now non-clickable
    // Find the result list item by locating the "Commit Message" chip
    const chipEl = screen.getByText('Commit Message')
    const listItem = chipEl.closest('li')!
    // The clickable location link is the ButtonBase showing repo name
    const locationLink = within(listItem).getByText('test-repo')
    fireEvent.click(locationLink)

    // Should navigate to history, not browse
    await waitFor(() => {
      expect(window.location.pathname).toBe('/history')
      expect(window.location.search).toContain('commit=abc123')
      expect(window.location.search).toContain('repo=test-repo')
    })
  })

  it('should navigate to browse when clicking a file-based result', async () => {
    mockSearchText.mockResolvedValue({
      results: [
        {
          id: 2,
          source_type: 'comment',
          content: '# helper function',
          content_type: null,
          repository_id: 1,
          repository_name: 'test-repo',
          file_path: 'src/utils.py',
          source_line: 10,
          source_end_line: null,
          language: 'python',
          commit_hash: 'abc123',
          branch: 'main',
          headline: null,
          rank: 1.0,
        },
      ],
      total: 1,
      query: 'helper',
      mode: 'keyword',
      limit: 20,
      offset: 0,
    })

    window.history.pushState({}, '', '?query=helper')
    render(<Search />)

    await waitFor(() => {
      expect(getByTextContent(/# helper function/i)).toBeInTheDocument()
    })

    // Click the location link (file path), not the content text
    fireEvent.click(getByTextContent(/test-repo \/ src\/utils\.py:10/))

    await waitFor(() => {
      expect(window.location.pathname).toBe('/browse/test-repo/src/utils.py')
      expect(window.location.search).toContain('line=10')
    })
  })

  it('should not include commit=unknown when clicking file-derived result with null commit_hash', async () => {
    mockSearchText.mockResolvedValue({
      results: [
        {
          id: 3,
          source_type: 'comment',
          content: '# Initialize console',
          content_type: null,
          repository_id: 1,
          repository_name: 'test-repo',
          file_path: 'src/cli.py',
          source_line: 22,
          source_end_line: null,
          language: 'python',
          commit_hash: null,
          branch: 'main',
          headline: null,
          rank: 1.0,
        },
      ],
      total: 1,
      query: 'console',
      mode: 'keyword',
      limit: 20,
      offset: 0,
    })

    window.history.pushState({}, '', '?query=console&source_types=comment')
    render(<Search />)

    await waitFor(() => {
      expect(getByTextContent(/# Initialize console/i)).toBeInTheDocument()
    })

    // Click the location link (file path), not the content text
    fireEvent.click(getByTextContent(/test-repo \/ src\/cli\.py:22/))

    await waitFor(() => {
      expect(window.location.pathname).toBe('/browse/test-repo/src/cli.py')
      expect(window.location.search).toContain('branch=main')
      expect(window.location.search).toContain('line=22')
      expect(window.location.search).not.toContain('commit=')
    })
  })

  it('should have all source type checkboxes checked by default (all included)', async () => {
    render(<Search />)

    await waitFor(() => {
      const symbolsCheckbox = screen.getByLabelText('Definitions') as HTMLInputElement
      const referencesCheckbox = screen.getByLabelText('References') as HTMLInputElement
      const commentsCheckbox = screen.getByLabelText('Comments') as HTMLInputElement
      const docstringsCheckbox = screen.getByLabelText('Docstrings') as HTMLInputElement
      const commitMsgsCheckbox = screen.getByLabelText('Commit Messages') as HTMLInputElement
      const fileContentCheckbox = screen.getByLabelText('File Content') as HTMLInputElement

      expect(symbolsCheckbox.checked).toBe(true)
      expect(referencesCheckbox.checked).toBe(true)
      expect(commentsCheckbox.checked).toBe(true)
      expect(docstringsCheckbox.checked).toBe(true)
      expect(commitMsgsCheckbox.checked).toBe(true)
      expect(fileContentCheckbox.checked).toBe(true)
    })
  })

  it('should call both searchSymbols and searchText by default', async () => {
    window.history.pushState({}, '', '?query=test')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchSymbols).toHaveBeenCalledWith(expect.objectContaining({ q: 'test' }))
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          // With reference selected by default, source_types is sent explicitly
          source_types: ['comment', 'docstring', 'commit_message', 'file_content', 'reference'],
        })
      )
    })
  })

  it('should exclude unchecked source types from results', async () => {
    // URL includes only non-symbol types (symbol is not in types list = excluded)
    window.history.pushState(
      {},
      '',
      '?query=test&types=reference,comment,docstring,commit_message,file_content'
    )
    render(<Search />)

    await waitFor(() => {
      // searchText should be called (other text types still active)
      expect(mockSearchText).toHaveBeenCalled()
      // searchSymbols should NOT be called since symbol is not included
      expect(mockSearchSymbols).not.toHaveBeenCalled()
    })
  })

  it('should render Definitions checkbox in source types', async () => {
    render(<Search />)

    await waitFor(() => {
      expect(screen.getByLabelText('Definitions')).toBeInTheDocument()
    })
  })

  it('should call searchSymbols when only Definitions source type is selected', async () => {
    mockSearchSymbols.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'get_file_symbols_by_path',
          qualified_name: 'inxr2.api.get_file_symbols_by_path',
          kind: 'function',
          file_id: 10,
          file_path: 'src/api/routes.py',
          repository_id: 1,
          commit_id: 1,
          start_line: 42,
          start_column: 0,
          end_line: 55,
          end_column: 0,
          signature: 'def get_file_symbols_by_path(repo: str, path: str)',
          docstring: null,
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    })

    // Only symbol type included
    window.history.pushState({}, '', '?query=get_file_symbols_by_path&types=symbol')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchSymbols).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'get_file_symbols_by_path',
        })
      )
    })

    // Should NOT call searchText when only symbol is included
    expect(mockSearchText).not.toHaveBeenCalled()
  })

  it('should render symbol results with Symbol badge and kind', async () => {
    mockSearchSymbols.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'MyClass',
          qualified_name: 'module.MyClass',
          kind: 'class',
          file_id: 10,
          file_path: 'src/models.py',
          repository_id: 1,
          commit_id: 1,
          start_line: 5,
          start_column: 0,
          end_line: 20,
          end_column: 0,
          signature: 'class MyClass(Base)',
          docstring: null,
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    })

    // Only symbol type included
    window.history.pushState({}, '', '?query=MyClass&types=symbol')
    render(<Search />)

    await waitFor(() => {
      expect(screen.getByText('Symbol')).toBeInTheDocument()
      expect(screen.getByText('class')).toBeInTheDocument()
      expect(getByTextContent('class MyClass(Base)')).toBeInTheDocument()
    })
  })

  it('should navigate to browse when clicking a symbol result', async () => {
    mockSearchSymbols.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'my_function',
          qualified_name: 'module.my_function',
          kind: 'function',
          file_id: 10,
          file_path: 'src/utils.py',
          repository_id: 1,
          commit_id: 1,
          start_line: 15,
          start_column: 0,
          end_line: 25,
          end_column: 0,
          signature: 'def my_function(x: int) -> str',
          docstring: null,
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    })

    // Only symbol type included
    window.history.pushState({}, '', '?query=my_function&types=symbol')
    render(<Search />)

    await waitFor(() => {
      expect(getByTextContent('def my_function(x: int) -> str')).toBeInTheDocument()
    })

    // Click the location link (file path), not the signature text
    fireEvent.click(getByTextContent(/test-repo \/ src\/utils\.py:15/))

    await waitFor(() => {
      expect(window.location.pathname).toBe('/browse/test-repo/src/utils.py')
      expect(window.location.search).toContain('line=15')
    })
  })

  it('should call both searchSymbols and searchText when both are selected', async () => {
    mockSearchSymbols.mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    })

    // symbol and comment included
    window.history.pushState({}, '', '?query=test&types=symbol,comment')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchSymbols).toHaveBeenCalledWith(expect.objectContaining({ q: 'test' }))
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          source_types: ['comment'],
        })
      )
    })
  })

  it('should pass scope=latest when no repo is selected', async () => {
    window.history.pushState({}, '', '?query=test')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchSymbols).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          scope: 'latest',
          repository_id: undefined,
        })
      )
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          scope: 'latest',
          repo: undefined,
        })
      )
    })
  })

  it('should NOT pass scope when repo is selected', async () => {
    window.history.pushState({}, '', '?repo=test-repo&query=test')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          repo: 1,
          scope: undefined,
        })
      )
    })
  })

  it('should not search until repos are loaded when repo param is set (race condition fix)', async () => {
    // Simulate slow repo loading by making getRepositories return a promise
    // that we control
    let resolveRepos!: (repos: api.Repository[]) => void
    mockGetRepositories.mockReturnValue(
      new Promise((resolve) => {
        resolveRepos = resolve
      })
    )

    window.history.pushState({}, '', '?repo=test-repo&query=test')
    render(<Search />)

    // Search should NOT have been called yet — repos haven't loaded
    expect(mockSearchText).not.toHaveBeenCalled()
    expect(mockSearchSymbols).not.toHaveBeenCalled()

    // Now resolve repos
    resolveRepos([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: 'Test repository',
        default_branch: 'main',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ])

    // After repos load, search should fire with the correct repo ID
    await waitFor(() => {
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          repo: 1,
        })
      )
    })
  })

  describe('Extension filter', () => {
    /**
     * Helper to find and open the MUI "Extensions" multi-select dropdown.
     * MUI InputLabel renders the label text twice (label element + notched outline),
     * so we find the label, navigate to the FormControl, then find the select trigger.
     */
    async function openExtensionDropdown() {
      await waitFor(() => {
        const labels = screen.getAllByText('Extensions')
        expect(labels.length).toBeGreaterThan(0)
      })
      // Find the MUI Select trigger (div with role="combobox" or class MuiSelect-select)
      const labels = screen.getAllByText('Extensions')
      const formControl = labels[0]!.closest('.MuiFormControl-root')!
      const trigger = formControl.querySelector('.MuiSelect-select') as HTMLElement
      fireEvent.mouseDown(trigger)
    }

    it('should render Extensions dropdown', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '.ts', '.tsx', '.js'],
      })

      window.history.pushState({}, '', '/search')
      render(<Search />)

      await waitFor(() => {
        const labels = screen.getAllByText('Extensions')
        expect(labels.length).toBeGreaterThan(0)
      })
    })

    it('should set ext to empty when clicking "Select none"', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '.ts', '.tsx'],
      })

      window.history.pushState({}, '', '?query=test')
      render(<Search />)

      await openExtensionDropdown()

      // Wait for extension options to render (ensures state update from async effect is done)
      await waitFor(() => {
        expect(screen.getByText('.py')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByText('Select none'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        const ext = params.get('ext')
        expect(ext).toBe('')
      })
    })

    it('should clear ext param when clicking "Show all extensions"', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '.ts', '.tsx'],
      })

      window.history.pushState({}, '', '?query=test&ext=.py')
      render(<Search />)

      await openExtensionDropdown()

      // Wait for extension options to render
      await waitFor(() => {
        expect(screen.getByText('Show all extensions')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByText('Show all extensions'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('ext')).toBeNull()
      })
    })

    it('should render (none) sentinel as "(no extension)" in dropdown menu', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '(none)', '.ts'],
      })

      window.history.pushState({}, '', '/search')
      render(<Search />)

      await openExtensionDropdown()

      // Wait for extension options to render, then verify (none) displays as "(no extension)"
      await waitFor(() => {
        expect(screen.getByText('(no extension)')).toBeInTheDocument()
      })
    })

    it('should render (none) sentinel as "(no extension)" in chip display when included', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '(none)', '.ts'],
      })

      window.history.pushState({}, '', '?query=test&ext=(none)')
      render(<Search />)

      // The chip in the select's renderValue should display "(no extension)"
      await waitFor(() => {
        const chips = screen.getAllByText('(no extension)')
        expect(chips.length).toBeGreaterThanOrEqual(1)
      })
    })

    it('should include (none) in ext URL param when selecting from empty state', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '(none)', '.ts'],
      })

      // Start with no extensions selected
      window.history.pushState({}, '', '?query=test&ext=')
      render(<Search />)

      await openExtensionDropdown()

      // Wait for extension options to render
      await waitFor(() => {
        expect(screen.getByText('(no extension)')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByText('(no extension)'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        const ext = params.get('ext')
        expect(ext).toContain('(none)')
      })
    })

    it('should uncheck extension when clicking it from default (all selected) state', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '.ts', '.tsx'],
      })

      window.history.pushState({}, '', '?query=test')
      render(<Search />)

      await openExtensionDropdown()

      // Wait for extension options to render, then click .py to uncheck it
      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
      })
      const listbox = screen.getByRole('listbox')
      await waitFor(() => {
        expect(within(listbox).getByText('.py')).toBeInTheDocument()
      })
      fireEvent.click(within(listbox).getByText('.py'))

      // .py unchecked → only .ts and .tsx remain
      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('ext')).toBe('.ts,.tsx')
      })
    })

    it('should skip search when ext param is empty (no extensions selected)', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '.ts'],
      })

      // Empty ext param = no extensions selected
      window.history.pushState({}, '', '?query=test&ext=')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('No results found')).toBeInTheDocument()
      })

      expect(mockSearchText).not.toHaveBeenCalled()
      expect(mockSearchSymbols).not.toHaveBeenCalled()
    })

    it('should restore extension filter state from URL on mount', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '.ts', '.tsx'],
      })

      // Mount with ext already in URL (simulates page reload)
      window.history.pushState({}, '', '?query=test&ext=.py,.tsx')
      render(<Search />)

      // The chips should show the included extensions in the select's renderValue
      await waitFor(() => {
        const pyChips = screen.getAllByText('.py')
        expect(pyChips.length).toBeGreaterThanOrEqual(1)
        const tsxChips = screen.getAllByText('.tsx')
        expect(tsxChips.length).toBeGreaterThanOrEqual(1)
      })
    })

    it('should pass included extensions to searchText API call', async () => {
      mockGetFileExtensions.mockResolvedValue({
        extensions: ['.py', '.ts', '.tsx'],
      })

      // Include only .py — only .py should be passed as extensions
      window.history.pushState({}, '', '?query=test&ext=.py')
      render(<Search />)

      await waitFor(() => {
        expect(mockSearchText).toHaveBeenCalledWith(
          expect.objectContaining({
            q: 'test',
            extensions: ['.py'],
          })
        )
      })
    })
  })

  it('should never fire search without commit filter when commit and repo params are both set', async () => {
    // Regression test for: search fires once without commit filter when
    // reposLoading=false but selectedRepoId hasn't resolved yet (race condition).
    let resolveRepos!: (repos: api.Repository[]) => void
    mockGetRepositories.mockReturnValue(
      new Promise((resolve) => {
        resolveRepos = resolve
      })
    )

    window.history.pushState({}, '', '?repo=test-repo&branch=main&commit=abc123def456&query=mcp')
    render(<Search />)

    // Search must NOT fire before repos have loaded
    expect(mockSearchText).not.toHaveBeenCalled()
    expect(mockSearchSymbols).not.toHaveBeenCalled()

    // Resolve repos — simulates the state update that sets repositories
    resolveRepos([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: 'Test repository',
        default_branch: 'main',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ])

    // After repos load, search must fire WITH the commit filter
    await waitFor(() => {
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'mcp',
          repo: 1,
          commit: 'abc123def456',
        })
      )
    })

    // Verify no call was ever made without the commit filter
    const callsWithoutCommit = mockSearchText.mock.calls.filter(([args]) => !args.commit)
    expect(callsWithoutCommit).toHaveLength(0)
  })

  it('should pass commit param to searchText and searchSymbols', async () => {
    mockGetRepositories.mockResolvedValue([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: 'Test repository',
        default_branch: 'main',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ])

    window.history.pushState({}, '', '?query=test&repo=test-repo&branch=main&commit=abc123def456')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          commit: 'abc123def456',
        })
      )
      expect(mockSearchSymbols).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          commit: 'abc123def456',
        })
      )
    })
  })

  it('should filter by repository when repo param is in URL', async () => {
    mockGetRepositories.mockResolvedValue([
      {
        id: 1,
        name: 'test-repo',
        url: 'https://github.com/test/repo',
        description: 'Test repository',
        default_branch: 'main',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
      {
        id: 2,
        name: 'other-repo',
        url: 'https://github.com/test/other',
        description: 'Other repository',
        default_branch: 'main',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ])

    mockSearchText.mockResolvedValue({
      results: [
        {
          id: 1,
          source_type: 'comment',
          content: 'test content',
          content_type: null,
          repository_id: 1,
          repository_name: 'test-repo',
          file_path: 'test.py',
          source_line: 10,
          source_end_line: null,
          language: 'python',
          commit_hash: 'abc123',
          branch: 'main',
          headline: null,
          rank: 1.0,
        },
      ],
      total: 1,
      query: 'test',
      mode: 'keyword',
      limit: 20,
      offset: 0,
    })

    // Render with repo and query params in URL
    window.history.pushState({}, '', '?repo=test-repo&query=test')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          repo: 1, // Should use the ID from the repo with name 'test-repo'
        })
      )
    })
  })
})
