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
    searchFiles: vi.fn(),
    searchSymbols: vi.fn(),
    searchDependencies: vi.fn(),
    getRepositories: vi.fn(),
    getRepositoryBranches: vi.fn(),
    getCommits: vi.fn(),
    getFileExtensions: vi.fn(),
  }
})

const mockSearchText = vi.mocked(api.searchText)
const mockSearchFiles = vi.mocked(api.searchFiles)
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

    mockSearchFiles.mockResolvedValue({
      files: [],
      total_count: 0,
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

    // Wait for the result chip to appear. Match the exact "Commit Message" chip
    // text (not the regex, which also matches the "Commit Messages" filter
    // dropdown and would resolve before the result row actually renders).
    await waitFor(() => {
      expect(screen.getByText('Commit Message')).toBeInTheDocument()
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

  describe('File mode', () => {
    it('should render file results and navigate with branch and commit on click', async () => {
      mockSearchFiles.mockResolvedValue({
        files: [
          {
            id: 1,
            path: 'src/lib/utils.py',
            name: 'utils.py',
            language: 'python',
            repository_id: 1,
            repository_name: 'test-repo',
            commit_id: 1,
            commit_hash: 'abc123def',
          },
        ],
        total_count: 1,
        limit: 50,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=utils&mode=file&repo=test-repo&branch=main')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('utils.py')).toBeInTheDocument()
        // language chip rendered
        expect(screen.getByText('python')).toBeInTheDocument()
        expect(getByTextContent('test-repo / src/lib/utils.py')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('utils.py'))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo/src/lib/utils.py')
        expect(window.location.search).toContain('branch=main')
        expect(window.location.search).toContain('commit=abc123def')
      })
    })

    it('should navigate without query string when file has no branch or commit', async () => {
      mockSearchFiles.mockResolvedValue({
        files: [
          {
            id: 2,
            path: 'README.md',
            name: 'README.md',
            language: null,
            repository_id: 1,
            repository_name: 'test-repo',
            commit_id: 1,
            commit_hash: '',
          },
        ],
        total_count: 1,
        limit: 50,
        offset: 0,
      })

      // file mode, no branch param, empty commit_hash → no query string
      window.history.pushState({}, '', '?query=README&mode=file')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
      })
      // No language chip when language is null
      expect(screen.queryByText('null')).not.toBeInTheDocument()

      // Click the side bar (aria-label "Go to file")
      fireEvent.click(screen.getAllByLabelText('Go to file')[0]!)

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo/README.md')
        expect(window.location.search).toBe('')
      })
    })

    it('should show empty state when file mode returns no files', async () => {
      mockSearchFiles.mockResolvedValue({
        files: [],
        total_count: 0,
        limit: 50,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=nothing&mode=file')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('No results found')).toBeInTheDocument()
      })
      // Text/symbol search must not be called in file mode
      expect(mockSearchText).not.toHaveBeenCalled()
      expect(mockSearchSymbols).not.toHaveBeenCalled()
      expect(mockSearchFiles).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'nothing', commit_hash: undefined })
      )
    })

    it('should show file-mode placeholder prompt when query is empty', async () => {
      window.history.pushState({}, '', '?mode=file')
      render(<Search />)

      await waitFor(() => {
        expect(
          screen.getByText('Enter a file name to search for files by path')
        ).toBeInTheDocument()
      })
    })
  })

  describe('Dependency results', () => {
    it('should render direct dependency with version_spec and resolved_version, then navigate', async () => {
      mockSearchDependencies.mockResolvedValue({
        results: [
          {
            id: 1,
            package_name: 'fastapi',
            language: 'python',
            version_spec: '>=0.100',
            resolved_version: '0.110.0',
            dependency_type: 'runtime',
            is_direct: true,
            file_id: 5,
            file_path: 'pyproject.toml',
            repository_id: 1,
            repository_name: 'test-repo',
            source_line: 12,
          },
        ],
        total: 1,
        query: 'fastapi',
        limit: 50,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=fastapi&types=dependency&branch=main')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('Dependency')).toBeInTheDocument()
        expect(screen.getByText('runtime')).toBeInTheDocument()
        expect(getByTextContent(/fastapi/)).toBeInTheDocument()
        expect(screen.getByText('>=0.100')).toBeInTheDocument()
        expect(screen.getByText('= 0.110.0')).toBeInTheDocument()
      })
      // is_direct=true → no "transitive" chip
      expect(screen.queryByText('transitive')).not.toBeInTheDocument()

      fireEvent.click(getByTextContent('test-repo / pyproject.toml'))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo/pyproject.toml')
        expect(window.location.search).toContain('repo=test-repo')
        expect(window.location.search).toContain('branch=main')
        expect(window.location.search).toContain('line=12')
      })
    })

    it('should render transitive dependency without version chips and not navigate when file_path is null', async () => {
      mockSearchDependencies.mockResolvedValue({
        results: [
          {
            id: 2,
            package_name: 'idna',
            language: 'python',
            version_spec: null,
            resolved_version: null,
            dependency_type: 'runtime',
            is_direct: false,
            file_id: 5,
            file_path: null,
            repository_id: 1,
            repository_name: 'test-repo',
            source_line: null,
          },
        ],
        total: 1,
        query: 'idna',
        limit: 50,
        offset: 0,
      })

      window.history.pushState({}, '', '/search?query=idna&types=dependency')
      render(<Search />)

      await waitFor(() => {
        // is_direct=false → "transitive" chip shown
        expect(screen.getByText('transitive')).toBeInTheDocument()
        expect(getByTextContent(/idna/)).toBeInTheDocument()
      })
      // version chips absent when both null
      expect(screen.queryByText(/^=/)).not.toBeInTheDocument()

      const startingPath = window.location.pathname
      const startingSearch = window.location.search
      // Click the location text — file_path is null so handler returns early (no nav)
      fireEvent.click(screen.getByLabelText('Go to result'))

      // URL unchanged — navigation was a no-op
      expect(window.location.pathname).toBe(startingPath)
      expect(window.location.search).toBe(startingSearch)
    })

    it('should carry branch and commit to browse when clicking a dependency with a selected repo', async () => {
      mockSearchDependencies.mockResolvedValue({
        results: [
          {
            id: 3,
            package_name: 'numpy',
            language: 'python',
            version_spec: '*',
            resolved_version: null,
            dependency_type: 'runtime',
            is_direct: true,
            file_id: 5,
            file_path: 'requirements.txt',
            repository_id: 1,
            repository_name: 'test-repo',
            source_line: 4,
          },
        ],
        total: 1,
        query: 'numpy',
        limit: 50,
        offset: 0,
      })

      window.history.pushState(
        {},
        '',
        '/search?query=numpy&types=dependency&repo=test-repo&branch=main&commit=abc123'
      )
      render(<Search />)

      await waitFor(() => {
        expect(getByTextContent('test-repo / requirements.txt')).toBeInTheDocument()
      })

      fireEvent.click(getByTextContent('test-repo / requirements.txt'))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo/requirements.txt')
        expect(window.location.search).toContain('repo=test-repo')
        expect(window.location.search).toContain('branch=main')
        expect(window.location.search).toContain('commit=abc123')
        expect(window.location.search).toContain('line=4')
      })
    })

    it('should call searchDependencies with branch and pass repository_id when repo selected', async () => {
      window.history.pushState({}, '', '?query=req&types=dependency&repo=test-repo&branch=main')
      render(<Search />)

      await waitFor(() => {
        expect(mockSearchDependencies).toHaveBeenCalledWith(
          expect.objectContaining({
            q: 'req',
            repository_id: 1,
            branch: 'main',
          })
        )
      })
    })
  })

  it('should search unfiltered when commit+repo params are set but repo name does not match', async () => {
    // repos are loaded (length > 0) but the repo param does not match any name,
    // so the deferral guard falls through and the search runs without a repo.
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

    window.history.pushState({}, '', '?query=x&repo=ghost-repo&commit=abc123&types=comment')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'x',
          // unmatched repo name → repo undefined and commit dropped
          repo: undefined,
        })
      )
    })
  })

  it('should navigate when clicking the inner result content text (not just the side bar)', async () => {
    mockSearchText.mockResolvedValue({
      results: [
        {
          id: 1,
          source_type: 'comment',
          content: '# clickable content',
          content_type: null,
          repository_id: 1,
          repository_name: 'test-repo',
          file_path: 'src/x.py',
          source_line: 9,
          source_end_line: null,
          language: 'python',
          commit_hash: 'abc123',
          branch: 'main',
          headline: null,
          rank: 1.0,
        },
      ],
      total: 1,
      query: 'clickable',
      mode: 'keyword',
      limit: 50,
      offset: 0,
    })

    window.history.pushState({}, '', '/search?query=clickable&types=comment')
    render(<Search />)

    await waitFor(() => {
      expect(getByTextContent(/# clickable content/)).toBeInTheDocument()
    })

    // Click the location ButtonBase (the inner clickable element)
    fireEvent.click(getByTextContent(/test-repo \/ src\/x\.py:9/))

    await waitFor(() => {
      expect(window.location.pathname).toBe('/browse/test-repo/src/x.py')
      expect(window.location.search).toContain('branch=main')
      expect(window.location.search).toContain('commit=abc123')
      expect(window.location.search).toContain('line=9')
    })
  })

  describe('Symbol click edge cases', () => {
    it('should not navigate when symbol repository_id has no matching repo', async () => {
      mockSearchSymbols.mockResolvedValue({
        items: [
          {
            id: 1,
            name: 'orphan',
            qualified_name: 'mod.orphan',
            kind: 'function',
            file_id: 10,
            file_path: 'src/orphan.py',
            repository_id: 999, // no repo with this id
            commit_id: 1,
            start_line: 3,
            start_column: 0,
            end_line: 8,
            end_column: 0,
            signature: 'def orphan()',
            docstring: null,
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      })

      window.history.pushState({}, '', '/search?query=orphan&types=symbol')
      render(<Search />)

      await waitFor(() => {
        expect(getByTextContent('def orphan()')).toBeInTheDocument()
      })

      const startingPath = window.location.pathname
      fireEvent.click(screen.getByLabelText('Go to result'))

      // No repo match → no navigation
      expect(window.location.pathname).toBe(startingPath)
    })

    it('should carry branch and commit when clicking a symbol with a selected repo', async () => {
      mockSearchSymbols.mockResolvedValue({
        items: [
          {
            id: 1,
            name: 'handler',
            qualified_name: 'mod.handler',
            kind: 'function',
            file_id: 10,
            file_path: 'src/h.py',
            repository_id: 1,
            commit_id: 1,
            start_line: 20,
            start_column: 0,
            end_line: 30,
            end_column: 0,
            signature: 'def handler()',
            docstring: null,
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      })

      window.history.pushState(
        {},
        '',
        '/search?query=handler&types=symbol&repo=test-repo&branch=main&commit=abc123'
      )
      render(<Search />)

      await waitFor(() => {
        expect(getByTextContent('def handler()')).toBeInTheDocument()
      })

      fireEvent.click(getByTextContent(/test-repo \/ src\/h\.py:20/))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo/src/h.py')
        expect(window.location.search).toContain('branch=main')
        expect(window.location.search).toContain('commit=abc123')
        expect(window.location.search).toContain('line=20')
      })
    })

    it('should fall back to name when symbol has no signature or qualified_name', async () => {
      mockSearchSymbols.mockResolvedValue({
        items: [
          {
            id: 1,
            name: 'bare_name',
            qualified_name: '',
            kind: 'variable',
            file_id: 10,
            file_path: 'src/x.py',
            repository_id: 1,
            commit_id: 1,
            start_line: 7,
            start_column: 0,
            end_line: 7,
            end_column: 0,
            signature: null,
            docstring: null,
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=bare_name&types=symbol&branch=main')
      render(<Search />)

      await waitFor(() => {
        expect(getByTextContent('bare_name')).toBeInTheDocument()
      })

      fireEvent.click(getByTextContent(/test-repo \/ src\/x\.py:7/))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo/src/x.py')
        expect(window.location.search).toContain('branch=main')
        expect(window.location.search).toContain('line=7')
      })
    })
  })

  describe('Text result click variants', () => {
    it('should fall back to repo root when file-content result has no file_path', async () => {
      mockSearchText.mockResolvedValue({
        results: [
          {
            id: 1,
            source_type: 'file_content',
            content: 'orphan content',
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
        query: 'orphan',
        mode: 'keyword',
        limit: 20,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=orphan&types=file_content')
      render(<Search />)

      await waitFor(() => {
        expect(getByTextContent(/orphan content/)).toBeInTheDocument()
      })

      fireEvent.click(screen.getByLabelText('Go to result'))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo')
        expect(window.location.search).toContain('repo=test-repo')
        expect(window.location.search).toContain('branch=main')
        expect(window.location.search).toContain('commit=abc123')
      })
    })

    it('should add view=raw when navigating to a markdown file result', async () => {
      mockSearchText.mockResolvedValue({
        results: [
          {
            id: 1,
            source_type: 'file_content',
            content: '# Heading',
            content_type: null,
            repository_id: 1,
            repository_name: 'test-repo',
            file_path: 'docs/README.md',
            source_line: 5,
            source_end_line: null,
            language: 'markdown',
            commit_hash: 'abc123',
            branch: 'main',
            headline: null,
            rank: 1.0,
          },
        ],
        total: 1,
        query: 'Heading',
        mode: 'keyword',
        limit: 20,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=Heading&types=file_content')
      render(<Search />)

      await waitFor(() => {
        expect(getByTextContent(/# Heading/)).toBeInTheDocument()
      })

      fireEvent.click(getByTextContent(/test-repo \/ docs\/README\.md:5/))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo/docs/README.md')
        expect(window.location.search).toContain('view=raw')
        expect(window.location.search).toContain('line=5')
      })
    })

    it('should render a result without branch and omit branch from navigation URL', async () => {
      mockSearchText.mockResolvedValue({
        results: [
          {
            id: 1,
            source_type: 'comment',
            content: '# no branch here',
            content_type: null,
            repository_id: 1,
            repository_name: 'test-repo',
            file_path: 'src/x.py',
            source_line: null,
            source_end_line: null,
            language: 'python',
            commit_hash: 'abc123',
            branch: null,
            headline: null,
            rank: 1.0,
          },
        ],
        total: 1,
        query: 'branch',
        mode: 'keyword',
        limit: 20,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=branch&types=comment')
      render(<Search />)

      await waitFor(() => {
        expect(getByTextContent(/# no branch here/)).toBeInTheDocument()
      })
      // No source_line → location text has no ":line" suffix
      fireEvent.click(getByTextContent('test-repo / src/x.py'))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo/src/x.py')
        expect(window.location.search).toContain('commit=abc123')
        expect(window.location.search).not.toContain('branch=')
        expect(window.location.search).not.toContain('line=')
      })
    })

    it('should render headline HTML instead of plain content when headline is present', async () => {
      mockSearchText.mockResolvedValue({
        results: [
          {
            id: 1,
            source_type: 'comment',
            content: 'plain content',
            content_type: null,
            repository_id: 1,
            repository_name: 'test-repo',
            file_path: 'src/x.py',
            source_line: 2,
            source_end_line: null,
            language: 'python',
            commit_hash: 'abc123',
            branch: 'main',
            headline: 'highlighted <mark>match</mark>',
            rank: 1.0,
          },
        ],
        total: 1,
        query: 'match',
        mode: 'keyword',
        limit: 20,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=match&types=comment')
      render(<Search />)

      await waitFor(() => {
        // Headline is injected via dangerouslySetInnerHTML; the <b> splits the
        // text, so match on the combined textContent of the span.
        expect(getByTextContent('highlighted match')).toBeInTheDocument()
      })
      // The mark tag from the headline HTML is rendered (not escaped as text)
      expect(getByTextContent('highlighted match').querySelector('mark')).not.toBeNull()
      // The raw content should not be rendered when a headline exists
      expect(screen.queryByText('plain content')).not.toBeInTheDocument()
    })
  })

  describe('CodeHeader handlers and filter buttons', () => {
    it('should clear types and ext filters when clicking "Show All"', async () => {
      window.history.pushState({}, '', '?query=test&types=comment&ext=.py')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('Show All')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByText('Show All'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('types')).toBeNull()
        expect(params.get('ext')).toBeNull()
        expect(params.get('query')).toBe('test')
      })
    })

    it('should set types to empty when clicking the "Select None" button', async () => {
      window.history.pushState({}, '', '?query=test')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('Select None')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByText('Select None'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('types')).toBe('')
      })
    })

    it('should toggle case sensitivity off then back on via URL param', async () => {
      window.history.pushState({}, '', '?query=test')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('Aa')).toBeInTheDocument()
      })
      // Default is case-sensitive → toggling sets case_sensitive=false
      fireEvent.click(screen.getByText('Aa'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('case_sensitive')).toBe('false')
      })

      // Toggle again → param removed (back to default true)
      fireEvent.click(screen.getByText('Aa'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('case_sensitive')).toBeNull()
      })
    })

    it('should toggle a source type off, adding a types param without that type', async () => {
      window.history.pushState({}, '', '?query=test')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByLabelText('Comments')).toBeInTheDocument()
      })
      // Uncheck Comments — all-but-comment should be written to URL
      fireEvent.click(screen.getByLabelText('Comments'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        const types = params.get('types')
        expect(types).not.toBeNull()
        expect(types!.split(',')).not.toContain('comment')
        expect(types!.split(',')).toContain('symbol')
      })
    })

    it('should re-check the last source type and remove the types param (back to all)', async () => {
      // Only symbol selected; checking another type that completes the full set
      // would remove the param. Start with all-but-symbol, then check symbol.
      const allButSymbol = 'reference,comment,docstring,commit_message,file_content,dependency'
      window.history.pushState({}, '', `?query=test&types=${allButSymbol}`)
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByLabelText('Definitions')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByLabelText('Definitions'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        // All types selected → param removed
        expect(params.get('types')).toBeNull()
      })
    })

    it('should clear types when switching mode to file', async () => {
      window.history.pushState({}, '', '?query=test&types=comment')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('No results found')).toBeInTheDocument()
      })

      // Open the Mode select and choose File
      const modeLabels = screen.getAllByText('Mode')
      const formControl = modeLabels[0]!.closest('.MuiFormControl-root')!
      const trigger = formControl.querySelector('.MuiSelect-select') as HTMLElement
      fireEvent.mouseDown(trigger)
      fireEvent.click(await screen.findByText('File'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('mode')).toBe('file')
        expect(params.get('types')).toBeNull()
      })
    })

    it('should navigate to a specific repo search when repo is changed in header', async () => {
      window.history.pushState({}, '', '?query=test')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByDisplayValue('All Repositories')).toBeInTheDocument()
      })

      // Open the repo Autocomplete and pick test-repo
      fireEvent.click(screen.getByTitle('Open'))
      fireEvent.click(await screen.findByText('test-repo'))

      await waitFor(() => {
        expect(window.location.pathname).toBe('/search')
        expect(window.location.search).toBe('?repo=test-repo')
      })
    })

    it('should remove repo/branch/commit but keep query when "All Repositories" is selected', async () => {
      window.history.pushState(
        {},
        '',
        '/search?repo=test-repo&branch=main&commit=abc123&query=test'
      )
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByDisplayValue('test-repo')).toBeInTheDocument()
      })

      // Open the repo Autocomplete and pick "All Repositories"
      fireEvent.click(screen.getByTitle('Open'))
      fireEvent.click(await screen.findByText('All Repositories'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('repo')).toBeNull()
        expect(params.get('branch')).toBeNull()
        expect(params.get('commit')).toBeNull()
        expect(params.get('query')).toBe('test')
      })
    })

    it('should navigate to browse when switching to the Browse tab with a repo selected', async () => {
      window.history.pushState({}, '', '?repo=test-repo&branch=main&query=test')
      render(<Search />)

      const browseTab = await screen.findByRole('tab', { name: /Browse/i })
      fireEvent.click(browseTab)

      await waitFor(() => {
        expect(window.location.pathname).toBe('/browse/test-repo')
        expect(window.location.search).toContain('repo=test-repo')
        expect(window.location.search).toContain('branch=main')
      })
    })

    it('should navigate to home when switching to Browse tab with no repo selected', async () => {
      window.history.pushState({}, '', '?query=test')
      render(<Search />)

      const browseTab = await screen.findByRole('tab', { name: /Browse/i })
      fireEvent.click(browseTab)

      await waitFor(() => {
        expect(window.location.pathname).toBe('/')
      })
    })

    it('should navigate to history with repo/branch/commit when switching to History tab', async () => {
      window.history.pushState({}, '', '?repo=test-repo&branch=main&commit=abc123&query=test')
      render(<Search />)

      const historyTab = await screen.findByRole('tab', { name: /History/i })
      fireEvent.click(historyTab)

      await waitFor(() => {
        expect(window.location.pathname).toBe('/history')
        expect(window.location.search).toContain('repo=test-repo')
        expect(window.location.search).toContain('branch=main')
        expect(window.location.search).toContain('commit=abc123')
      })
    })

    it('should navigate to logical-view carrying repo/branch when switching to that tab', async () => {
      window.history.pushState({}, '', '?repo=test-repo&branch=main&query=test')
      render(<Search />)

      const tab = await screen.findByRole('tab', { name: /Logical View/i })
      fireEvent.click(tab)

      await waitFor(() => {
        expect(window.location.pathname).toBe('/logical-view')
        expect(window.location.search).toContain('repo=test-repo')
        expect(window.location.search).toContain('branch=main')
      })
    })

    it('should navigate to dependencies carrying repo when switching to that tab', async () => {
      window.history.pushState({}, '', '?repo=test-repo&query=test')
      render(<Search />)

      const tab = await screen.findByRole('tab', { name: /Dependencies/i })
      fireEvent.click(tab)

      await waitFor(() => {
        expect(window.location.pathname).toBe('/dependencies')
        expect(window.location.search).toContain('repo=test-repo')
      })
    })

    it('should navigate to help carrying repo when switching to the Help tab', async () => {
      window.history.pushState({}, '', '?repo=test-repo&query=test')
      render(<Search />)

      const tab = await screen.findByRole('tab', { name: /Help/i })
      fireEvent.click(tab)

      await waitFor(() => {
        expect(window.location.pathname).toBe('/help')
        expect(window.location.search).toContain('repo=test-repo')
      })
    })

    it('should switch mode to phrase without clearing source types', async () => {
      window.history.pushState({}, '', '?query=test&types=comment')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('No results found')).toBeInTheDocument()
      })

      const modeLabels = screen.getAllByText('Mode')
      const formControl = modeLabels[0]!.closest('.MuiFormControl-root')!
      const trigger = formControl.querySelector('.MuiSelect-select') as HTMLElement
      fireEvent.mouseDown(trigger)
      fireEvent.click(await screen.findByText('Phrase'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('mode')).toBe('phrase')
        // Non-file mode → types are preserved
        expect(params.get('types')).toBe('comment')
      })
    })

    it('should keep query when selecting "All Repositories" with no query present', async () => {
      window.history.pushState({}, '', '/search?repo=test-repo&branch=main')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByDisplayValue('test-repo')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByTitle('Open'))
      fireEvent.click(await screen.findByText('All Repositories'))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('repo')).toBeNull()
        expect(params.get('branch')).toBeNull()
        // No query was set → none added
        expect(params.get('query')).toBeNull()
      })
    })
  })

  describe('Pagination and deep linking', () => {
    it('should render pagination and Page X of Y when there are more results than a page', async () => {
      mockSearchText.mockResolvedValue({
        results: Array.from({ length: 3 }, (_, i) => ({
          id: i + 1,
          source_type: 'comment' as const,
          content: `comment ${i}`,
          content_type: null,
          repository_id: 1,
          repository_name: 'test-repo',
          file_path: `src/f${i}.py`,
          source_line: i + 1,
          source_end_line: null,
          language: 'python',
          commit_hash: 'abc123',
          branch: 'main',
          headline: null,
          rank: 1.0,
        })),
        total: 120,
        query: 'comment',
        mode: 'keyword',
        limit: 50,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=comment&types=comment')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText(/Found 120 results/)).toBeInTheDocument()
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
      })

      // Navigate to page 2 via pagination control
      fireEvent.click(screen.getByRole('button', { name: /Go to page 2/i }))

      await waitFor(() => {
        const params = new URLSearchParams(window.location.search)
        expect(params.get('page')).toBe('2')
      })
    })

    it('should run a discovery fetch when deep-linking to page > 1 without cached totals', async () => {
      mockSearchText.mockResolvedValue({
        results: Array.from({ length: 3 }, (_, i) => ({
          id: i + 1,
          source_type: 'comment' as const,
          content: `c${i}`,
          content_type: null,
          repository_id: 1,
          repository_name: 'test-repo',
          file_path: `src/f${i}.py`,
          source_line: i + 1,
          source_end_line: null,
          language: 'python',
          commit_hash: 'abc123',
          branch: 'main',
          headline: null,
          rank: 1.0,
        })),
        total: 200,
        query: 'c',
        mode: 'keyword',
        limit: 50,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=c&types=comment&page=2')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText(/Found 200 results/)).toBeInTheDocument()
      })
      // Discovery call (limit:1, offset:0) plus the slice fetch → at least 2 calls
      const limitOneCalls = mockSearchText.mock.calls.filter(([args]) => args.limit === 1)
      expect(limitOneCalls.length).toBeGreaterThanOrEqual(1)
    })

    it('should run discovery fetches for symbol and dependency sources when deep-linking past page 1', async () => {
      mockSearchSymbols.mockResolvedValue({
        items: Array.from({ length: 3 }, (_, i) => ({
          id: i + 1,
          name: `sym${i}`,
          qualified_name: `mod.sym${i}`,
          kind: 'function',
          file_id: 10,
          file_path: `src/s${i}.py`,
          repository_id: 1,
          commit_id: 1,
          start_line: i + 1,
          start_column: 0,
          end_line: i + 2,
          end_column: 0,
          signature: `def sym${i}()`,
          docstring: null,
        })),
        total: 80,
        limit: 50,
        offset: 0,
      })
      mockSearchDependencies.mockResolvedValue({
        results: Array.from({ length: 3 }, (_, i) => ({
          id: i + 1,
          package_name: `dep${i}`,
          language: 'python',
          version_spec: null,
          resolved_version: null,
          dependency_type: 'runtime',
          is_direct: true,
          file_id: 5,
          file_path: 'requirements.txt',
          repository_id: 1,
          repository_name: 'test-repo',
          source_line: i + 1,
        })),
        total: 80,
        query: 'q',
        limit: 50,
        offset: 0,
      })

      // Deep-link to page 2 with symbol + dependency selected → discovery path runs
      window.history.pushState({}, '', '?query=q&types=symbol,dependency&page=2')
      render(<Search />)

      await waitFor(() => {
        // 80 symbols + 80 deps = 160 combined
        expect(screen.getByText(/Found 160 results/)).toBeInTheDocument()
      })

      // Discovery calls use limit:1
      const symDiscovery = mockSearchSymbols.mock.calls.filter(([a]) => a.limit === 1)
      const depDiscovery = mockSearchDependencies.mock.calls.filter(([a]) => a.limit === 1)
      expect(symDiscovery.length).toBeGreaterThanOrEqual(1)
      expect(depDiscovery.length).toBeGreaterThanOrEqual(1)
    })

    it('should singularize the result count when exactly one result', async () => {
      mockSearchText.mockResolvedValue({
        results: [
          {
            id: 1,
            source_type: 'comment',
            content: 'single',
            content_type: null,
            repository_id: 1,
            repository_name: 'test-repo',
            file_path: 'src/x.py',
            source_line: 1,
            source_end_line: null,
            language: 'python',
            commit_hash: 'abc123',
            branch: 'main',
            headline: null,
            rank: 1.0,
          },
        ],
        total: 1,
        query: 'single',
        mode: 'keyword',
        limit: 50,
        offset: 0,
      })

      window.history.pushState({}, '', '?query=single&types=comment')
      render(<Search />)

      await waitFor(() => {
        expect(screen.getByText('Found 1 result')).toBeInTheDocument()
      })
      // No pagination when only one page
      expect(screen.queryByText(/Page 1 of/)).not.toBeInTheDocument()
    })
  })

  describe('Regex and case-sensitivity wiring', () => {
    it('should pass mode=regex to searchSymbols and searchText in regex mode', async () => {
      window.history.pushState({}, '', '?query=get_.*&mode=regex&types=symbol,comment')
      render(<Search />)

      await waitFor(() => {
        expect(mockSearchSymbols).toHaveBeenCalledWith(
          expect.objectContaining({ q: 'get_.*', mode: 'regex' })
        )
        expect(mockSearchText).toHaveBeenCalledWith(
          expect.objectContaining({ q: 'get_.*', mode: 'regex' })
        )
      })
    })

    it('should pass case_sensitive=false to the search APIs when toggled off', async () => {
      window.history.pushState({}, '', '?query=test&case_sensitive=false&types=symbol,comment')
      render(<Search />)

      await waitFor(() => {
        expect(mockSearchText).toHaveBeenCalledWith(
          expect.objectContaining({ case_sensitive: false })
        )
        expect(mockSearchSymbols).toHaveBeenCalledWith(
          expect.objectContaining({ case_sensitive: false })
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
