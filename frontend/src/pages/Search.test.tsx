import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@/test/utils'
import Search from './Search'
import * as api from '@/lib/api'

// Mock the API
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return {
    ...actual,
    searchText: vi.fn(),
    searchSymbols: vi.fn(),
    getRepositories: vi.fn(),
    getRepositoryBranches: vi.fn(),
    getCommits: vi.fn(),
  }
})

const mockSearchText = vi.mocked(api.searchText)
const mockSearchSymbols = vi.mocked(api.searchSymbols)
const mockGetRepositories = vi.mocked(api.getRepositories)
const mockGetRepositoryBranches = vi.mocked(api.getRepositoryBranches)
const mockGetCommits = vi.mocked(api.getCommits)

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
  })

  it('should render search page with empty state', async () => {
    render(<Search />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Enter search query...')).toBeInTheDocument()
    })

    expect(
      screen.getByText(
        /Enter a search query to find symbols, comments, docstrings, commit messages, and files/i
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
          commit_hash: 'abc123def456',
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

    window.history.pushState({}, '', '?query=get_file_symbols_by_path&source_types=commit_message')
    render(<Search />)

    // Wait for results to appear
    await waitFor(() => {
      expect(screen.getByText(/Commit Message/i)).toBeInTheDocument()
    })

    // Click the result
    fireEvent.click(screen.getByText(/fix: update get_file_symbols_by_path/i))

    // Should navigate to history, not browse
    await waitFor(() => {
      expect(window.location.pathname).toBe('/history')
      expect(window.location.search).toContain('commit=abc123def456')
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
          commit_hash: 'abc123def456',
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
      expect(screen.getByText(/# helper function/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText(/# helper function/i))

    await waitFor(() => {
      expect(window.location.pathname).toBe('/browse/test-repo/src/utils.py')
      expect(window.location.search).toContain('line=10')
    })
  })

  it('should render Symbols checkbox in source types', async () => {
    render(<Search />)

    await waitFor(() => {
      expect(screen.getByLabelText('Symbols')).toBeInTheDocument()
    })
  })

  it('should call searchSymbols when Symbols source type is selected', async () => {
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

    window.history.pushState(
      {},
      '',
      '?query=get_file_symbols_by_path&source_types=symbol'
    )
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchSymbols).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'get_file_symbols_by_path',
        })
      )
    })

    // Should NOT call searchText when only symbol is selected
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

    window.history.pushState({}, '', '?query=MyClass&source_types=symbol')
    render(<Search />)

    await waitFor(() => {
      expect(screen.getByText('Symbol')).toBeInTheDocument()
      expect(screen.getByText('class')).toBeInTheDocument()
      expect(screen.getByText('class MyClass(Base)')).toBeInTheDocument()
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

    window.history.pushState({}, '', '?query=my_function&source_types=symbol')
    render(<Search />)

    await waitFor(() => {
      expect(screen.getByText('def my_function(x: int) -> str')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('def my_function(x: int) -> str'))

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

    window.history.pushState({}, '', '?query=test&source_types=symbol,comment')
    render(<Search />)

    await waitFor(() => {
      expect(mockSearchSymbols).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'test' })
      )
      expect(mockSearchText).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          source_types: ['comment'],
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
