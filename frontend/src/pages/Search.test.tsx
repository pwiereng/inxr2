import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/utils'
import Search from './Search'
import * as api from '@/lib/api'

// Mock the API
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return {
    ...actual,
    searchText: vi.fn(),
    getRepositories: vi.fn(),
    getRepositoryBranches: vi.fn(),
    getCommits: vi.fn(),
  }
})

const mockSearchText = vi.mocked(api.searchText)
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
  })

  it('should render search page with empty state', async () => {
    render(<Search />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Enter search query...')).toBeInTheDocument()
    })

    expect(
      screen.getByText(
        /Enter a search query to find text in comments, docstrings, commit messages, and files/i
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
