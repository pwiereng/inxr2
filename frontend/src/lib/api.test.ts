import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  getRepositoryByName,
  getRepositoryTreeByName,
  getFileContentByPath,
  getFileSymbolsByPath,
  getFileReferencesByPath,
  searchText,
  ApiError,
  getRepositories,
  getRepository,
  getRepositoryFiles,
  getRepositoryTree,
  getRepositoryStats,
  getAllRepositoryStats,
  getSymbolTree,
  searchSymbols,
  getSymbol,
  getSymbolsByName,
  getSymbolReferences,
  getFileContent,
  getFileSymbols,
  getFileReferences,
  getFileContentByPathAtCommit,
  getFileRawContent,
  getFileBlame,
  getCommits,
  getRepositoryBranches,
  getFileHistory,
  searchFiles,
  getFileExtensions,
  searchDependencies,
  getRepositoryDependencies,
  resolveFilePath,
  getActivityLog,
} from './api'

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('API functions - by-name/by-path endpoints', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('getRepositoryByName', () => {
    it('should fetch repository by name with encoded URL', async () => {
      const mockRepo = {
        id: 1,
        name: 'my-repo',
        url: 'https://github.com/test/repo.git',
        description: 'Test repo',
        default_branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockRepo,
      })

      const result = await getRepositoryByName('my-repo')

      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/by-name/my-repo')
      expect(result).toEqual(mockRepo)
    })

    it('should encode special characters in repository name', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 1, name: 'repo with spaces' }),
      })

      await getRepositoryByName('repo with spaces')

      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/by-name/repo%20with%20spaces')
    })

    it('should throw error when repository not found', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Repository not found' }),
      })

      await expect(getRepositoryByName('nonexistent')).rejects.toThrow('Repository not found')
    })
  })

  describe('getRepositoryTreeByName', () => {
    it('should fetch tree by repository name', async () => {
      const mockTree = {
        repository_id: 1,
        repository_name: 'my-repo',
        root: [{ name: 'src', path: 'src', type: 'directory', children: [] }],
        total_files: 5,
        total_directories: 2,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockTree,
      })

      const result = await getRepositoryTreeByName('my-repo')

      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/by-name/my-repo/tree')
      expect(result).toEqual(mockTree)
    })

    it('should include changedOnly param when true', async () => {
      const mockTree = {
        repository_id: 1,
        repository_name: 'my-repo',
        root: [],
        total_files: 1,
        total_directories: 0,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockTree,
      })

      await getRepositoryTreeByName('my-repo', 'abc123', 'main', true)

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/repositories/by-name/my-repo/tree?commit=abc123&branch=main&changed_only=true'
      )
    })

    it('should not include changedOnly param when false', async () => {
      const mockTree = {
        repository_id: 1,
        repository_name: 'my-repo',
        root: [],
        total_files: 1,
        total_directories: 0,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockTree,
      })

      await getRepositoryTreeByName('my-repo', 'abc123', undefined, false)

      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/by-name/my-repo/tree?commit=abc123')
    })
  })

  describe('getFileContentByPath', () => {
    it('should fetch file content by repo and path', async () => {
      const mockContent = {
        id: 1,
        path: 'src/main.py',
        language: 'python',
        content: 'print("hello")',
        line_count: 1,
        size_bytes: 15,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockContent,
      })

      const result = await getFileContentByPath('my-repo', 'src/main.py')

      expect(mockFetch).toHaveBeenCalledWith('/api/files/by-path?repo=my-repo&path=src%2Fmain.py')
      expect(result).toEqual(mockContent)
    })

    it('should throw error when file not found', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'File not found' }),
      })

      await expect(getFileContentByPath('repo', 'nonexistent.py')).rejects.toThrow('File not found')
    })
  })

  describe('getFileSymbolsByPath', () => {
    it('should fetch file symbols by repo and path', async () => {
      const mockSymbols = {
        file_id: 1,
        file_path: 'src/utils.py',
        symbols: [
          {
            id: 1,
            name: 'helper',
            kind: 'function',
            start_line: 1,
            start_column: 0,
            end_line: 5,
            end_column: 0,
          },
        ],
        total: 1,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSymbols,
      })

      const result = await getFileSymbolsByPath('my-repo', 'src/utils.py')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/files/by-path/symbols?repo=my-repo&path=src%2Futils.py'
      )
      expect(result).toEqual(mockSymbols)
    })
  })

  describe('getFileReferencesByPath', () => {
    it('should fetch file references by repo and path', async () => {
      const mockRefs = {
        file_id: 1,
        file_path: 'src/main.py',
        references: [
          {
            id: 1,
            reference_text: 'import os',
            reference_type: 'import',
            source_line: 1,
            source_column: 0,
            target_symbol_id: null,
          },
        ],
        total: 1,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockRefs,
      })

      const result = await getFileReferencesByPath('my-repo', 'src/main.py')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/files/by-path/references?repo=my-repo&path=src%2Fmain.py'
      )
      expect(result).toEqual(mockRefs)
    })
  })

  describe('searchText', () => {
    it('should search text with basic query', async () => {
      const mockResponse = {
        results: [
          {
            id: 1,
            repository_id: 1,
            repository_name: 'test-repo',
            file_path: 'src/main.py',
            source_line: 10,
            source_end_line: 10,
            source_type: 'comment',
            content: '# This is a test comment',
            content_type: null,
            language: 'python',
            commit_hash: 'abc123',
            branch: 'main',
            rank: 1.0,
            headline: '# This is a <mark>test</mark> comment',
          },
        ],
        total: 1,
        query: 'test',
        mode: 'keyword',
        limit: 20,
        offset: 0,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await searchText({ q: 'test' })

      expect(mockFetch).toHaveBeenCalledWith('/api/search/text?q=test')
      expect(result).toEqual(mockResponse)
    })

    it('should include all search parameters in URL', async () => {
      const mockResponse = {
        results: [],
        total: 0,
        query: 'test',
        mode: 'phrase',
        limit: 50,
        offset: 20,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      await searchText({
        q: 'test',
        mode: 'phrase',
        repo: 1,
        branch: 'develop',
        commit: 'abc123',
        source_types: ['comment', 'docstring'],
        languages: ['python', 'typescript'],
        limit: 50,
        offset: 20,
      })

      const expectedUrl =
        '/api/search/text?q=test&mode=phrase&repository_id=1&branch=develop&commit_hash=abc123&source_types=comment&source_types=docstring&languages=python&languages=typescript&limit=50&offset=20'
      expect(mockFetch).toHaveBeenCalledWith(expectedUrl)
    })

    it('should include extensions, case_sensitive and scope params', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          results: [],
          total: 0,
          query: 'x',
          mode: 'keyword',
          limit: 0,
          offset: 0,
        }),
      })

      await searchText({
        q: 'x',
        extensions: ['.py', '.ts'],
        case_sensitive: true,
        scope: 'all_branches',
      })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/search/text?q=x&extensions=.py&extensions=.ts&case_sensitive=true&scope=all_branches'
      )
    })

    it('should handle search errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Invalid search query' }),
      })

      await expect(searchText({ q: 'invalid[' })).rejects.toThrow('Invalid search query')
    })

    it('should format FastAPI 422 validation error array as human-readable message', async () => {
      // FastAPI returns detail as an array of validation error objects when input is invalid
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({
          detail: [
            {
              type: 'enum',
              loc: ['query', 'mode'],
              msg: "Input should be 'keyword', 'phrase' or 'regex'",
              input: 'text',
            },
          ],
        }),
      })

      await expect(searchText({ q: 'foo', mode: 'text' as 'keyword' })).rejects.toThrow(
        "Input should be 'keyword', 'phrase' or 'regex'"
      )
    })

    it('should join multiple FastAPI validation errors with semicolons', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({
          detail: [
            { msg: 'Field required', type: 'missing', loc: ['query', 'q'], input: {} },
            {
              msg: "Input should be 'keyword', 'phrase' or 'regex'",
              type: 'enum',
              loc: ['query', 'mode'],
              input: 'bad',
            },
          ],
        }),
      })

      await expect(searchText({ q: 'foo' })).rejects.toThrow(
        "Field required; Input should be 'keyword', 'phrase' or 'regex'"
      )
    })
  })
})

describe('API functions - repositories', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const okJson = (data: unknown) => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => data })
  }

  describe('getRepositories', () => {
    it('fetches the repositories list', async () => {
      const repos = [{ id: 1, name: 'a' }]
      okJson(repos)
      const result = await getRepositories()
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories')
      expect(result).toEqual(repos)
    })
  })

  describe('getRepository', () => {
    it('fetches a repository by id', async () => {
      okJson({ id: 7, name: 'seven' })
      const result = await getRepository(7)
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/7')
      expect(result).toEqual({ id: 7, name: 'seven' })
    })
  })

  describe('getRepositoryFiles', () => {
    it('fetches the file list for a repository', async () => {
      const files = [{ id: 1, path: 'a.py' }]
      okJson(files)
      const result = await getRepositoryFiles(3)
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/3/files')
      expect(result).toEqual(files)
    })

    it('throws ApiError with status on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Repository not found' }),
      })
      await expect(getRepositoryFiles(99)).rejects.toThrow('Repository not found')
    })
  })

  describe('getRepositoryTree', () => {
    it('fetches tree without commit', async () => {
      okJson({ repository_id: 1, root: [] })
      await getRepositoryTree(1)
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/1/tree')
    })

    it('appends commit query param when provided', async () => {
      okJson({ repository_id: 1, root: [] })
      await getRepositoryTree(1, 'abc123')
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/1/tree?commit=abc123')
    })
  })

  describe('getRepositoryStats', () => {
    it('fetches stats for a single repository', async () => {
      okJson({ repository_id: 1, name: 'a' })
      await getRepositoryStats(1)
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/1/stats')
    })
  })

  describe('getAllRepositoryStats', () => {
    it('fetches aggregate stats', async () => {
      okJson([])
      await getAllRepositoryStats()
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/stats')
    })
  })

  describe('getRepositoryBranches', () => {
    it('fetches branches with encoded repo name', async () => {
      okJson({ branches: [] })
      await getRepositoryBranches('my repo')
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/by-name/my%20repo/branches')
    })
  })

  describe('getRepositoryDependencies', () => {
    it('fetches dependencies without params', async () => {
      okJson({ items: [] })
      await getRepositoryDependencies('repo')
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/by-name/repo/dependencies')
    })

    it('builds query string from all params', async () => {
      okJson({ items: [] })
      await getRepositoryDependencies('repo', {
        commit: 'abc',
        branch: 'main',
        language: 'python',
        dependency_type: 'runtime',
        is_direct: false,
      })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/repositories/by-name/repo/dependencies?commit=abc&branch=main&language=python&dependency_type=runtime&is_direct=false'
      )
    })
  })

  describe('getSymbolTree', () => {
    it('fetches symbol tree without params', async () => {
      okJson({ repository_id: 1, files: [], symbols: null })
      await getSymbolTree('repo')
      expect(mockFetch).toHaveBeenCalledWith('/api/repositories/by-name/repo/symbol-tree')
    })

    it('builds query string including numeric and array params', async () => {
      okJson({ repository_id: 1, files: [], symbols: null })
      await getSymbolTree('repo', {
        branch: 'main',
        commit: 'abc',
        file_id: 0,
        parent_symbol_id: 5,
        language: 'python',
        kind: 'class',
        kinds: ['class', 'function'],
      })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/repositories/by-name/repo/symbol-tree?branch=main&commit=abc&file_id=0&parent_symbol_id=5&language=python&kind=class&kinds=class%2Cfunction'
      )
    })
  })
})

describe('API functions - symbols', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const okJson = (data: unknown) => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => data })
  }

  describe('searchSymbols', () => {
    it('fetches with no params', async () => {
      okJson({ items: [], total: 0, limit: 0, offset: 0 })
      await searchSymbols({})
      expect(mockFetch).toHaveBeenCalledWith('/api/symbols')
    })

    it('builds query string from all params including repeated extensions', async () => {
      okJson({ items: [], total: 0, limit: 0, offset: 0 })
      await searchSymbols({
        q: 'foo',
        kind: 'function',
        repository_id: 1,
        branch: 'main',
        commit: 'abc',
        language: 'python',
        extensions: ['.py', '.pyi'],
        mode: 'exact',
        case_sensitive: false,
        scope: 'all_branches',
        top_level_only: true,
        limit: 10,
        offset: 20,
      })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/symbols?q=foo&kind=function&repository_id=1&branch=main&commit=abc&language=python&extensions=.py&extensions=.pyi&mode=exact&case_sensitive=false&scope=all_branches&top_level_only=true&limit=10&offset=20'
      )
    })
  })

  describe('getSymbol', () => {
    it('fetches a symbol by id', async () => {
      okJson({ id: 5, name: 'foo' })
      await getSymbol(5)
      expect(mockFetch).toHaveBeenCalledWith('/api/symbols/5')
    })
  })

  describe('getSymbolsByName', () => {
    it('fetches by name without optional params', async () => {
      okJson({ items: [], total: 0 })
      await getSymbolsByName('Foo Bar')
      expect(mockFetch).toHaveBeenCalledWith('/api/symbols/by-name/Foo%20Bar')
    })

    it('includes repository_id and commit when provided', async () => {
      okJson({ items: [], total: 0 })
      await getSymbolsByName('Foo', 2, 'abc')
      expect(mockFetch).toHaveBeenCalledWith('/api/symbols/by-name/Foo?repository_id=2&commit=abc')
    })
  })

  describe('getSymbolReferences', () => {
    it('uses default limit of 100', async () => {
      okJson({ items: [], total: 0, symbol_name: 'foo' })
      await getSymbolReferences(5)
      expect(mockFetch).toHaveBeenCalledWith('/api/symbols/5/references?limit=100')
    })

    it('includes commit and branch params', async () => {
      okJson({ items: [], total: 0, symbol_name: 'foo' })
      await getSymbolReferences(5, 50, 'abc', 'main')
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/symbols/5/references?limit=50&commit=abc&branch=main'
      )
    })
  })
})

describe('API functions - files (by id and by path)', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const okJson = (data: unknown) => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => data })
  }

  describe('getFileContent', () => {
    it('fetches file content by id', async () => {
      okJson({ id: 1, content: 'x' })
      await getFileContent(1)
      expect(mockFetch).toHaveBeenCalledWith('/api/files/1/content')
    })
  })

  describe('getFileSymbols', () => {
    it('fetches file symbols by id', async () => {
      okJson({ file_id: 1, symbols: [] })
      await getFileSymbols(1)
      expect(mockFetch).toHaveBeenCalledWith('/api/files/1/symbols')
    })
  })

  describe('getFileReferences', () => {
    it('fetches file references by id', async () => {
      okJson({ file_id: 1, references: [] })
      await getFileReferences(1)
      expect(mockFetch).toHaveBeenCalledWith('/api/files/1/references')
    })
  })

  describe('getFileContentByPathAtCommit', () => {
    it('builds query with commit and branch', async () => {
      okJson({ id: 1, content: 'x' })
      await getFileContentByPathAtCommit('repo', 'src/main.py', 'abc', 'main')
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/files/by-path?repo=repo&path=src%2Fmain.py&commit=abc&branch=main'
      )
    })

    it('omits optional params when not provided', async () => {
      okJson({ id: 1, content: 'x' })
      await getFileContentByPathAtCommit('repo', 'a.py')
      expect(mockFetch).toHaveBeenCalledWith('/api/files/by-path?repo=repo&path=a.py')
    })
  })

  describe('getFileRawContent', () => {
    it('builds raw content query', async () => {
      okJson({ path: 'img.png', data: '...' })
      await getFileRawContent('repo', 'img.png', 'abc')
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/files/by-path/raw?repo=repo&path=img.png&commit=abc'
      )
    })
  })

  describe('getFileBlame', () => {
    it('builds blame query with branch', async () => {
      okJson({ path: 'a.py', lines: [] })
      await getFileBlame('repo', 'a.py', undefined, 'main')
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/files/by-path/blame?repo=repo&path=a.py&branch=main'
      )
    })
  })

  describe('getFileHistory', () => {
    it('builds history query with branch', async () => {
      okJson({ path: 'a.py', versions: [] })
      await getFileHistory('repo', 'a.py', 'main')
      expect(mockFetch).toHaveBeenCalledWith('/api/files/history?repo=repo&path=a.py&branch=main')
    })
  })
})

describe('API functions - search, commits, activity', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const okJson = (data: unknown) => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => data })
  }

  describe('getCommits', () => {
    it('uses default limit of 50', async () => {
      okJson({ commits: [], total: 0 })
      await getCommits('repo')
      expect(mockFetch).toHaveBeenCalledWith('/api/commits?repo=repo&limit=50')
    })

    it('includes branch when provided', async () => {
      okJson({ commits: [], total: 0 })
      await getCommits('repo', 'main', 10)
      expect(mockFetch).toHaveBeenCalledWith('/api/commits?repo=repo&branch=main&limit=10')
    })
  })

  describe('searchFiles', () => {
    it('searches with just a query', async () => {
      okJson({ files: [], total_count: 0, limit: 0, offset: 0 })
      await searchFiles({ q: 'main' })
      expect(mockFetch).toHaveBeenCalledWith('/api/search/files?q=main')
    })

    it('builds query with all params and repeated extensions', async () => {
      okJson({ files: [], total_count: 0, limit: 0, offset: 0 })
      await searchFiles({
        q: 'main',
        repository: 'repo',
        branch: 'dev',
        commit_hash: 'abc',
        language: 'python',
        extensions: ['.py', '.ts'],
        scope: 'all_history',
        limit: 5,
        offset: 10,
      })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/search/files?q=main&repository=repo&branch=dev&commit_hash=abc&language=python&extensions=.py&extensions=.ts&scope=all_history&limit=5&offset=10'
      )
    })
  })

  describe('getFileExtensions', () => {
    it('fetches without params', async () => {
      okJson({ extensions: [] })
      await getFileExtensions()
      expect(mockFetch).toHaveBeenCalledWith('/api/search/extensions')
    })

    it('builds query from params', async () => {
      okJson({ extensions: [] })
      await getFileExtensions({ repository_id: 1, branch: 'main', scope: 'latest' })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/search/extensions?repository_id=1&branch=main&scope=latest'
      )
    })
  })

  describe('searchDependencies', () => {
    it('searches with just a query', async () => {
      okJson({ results: [], total: 0, query: 'flask', limit: 0, offset: 0 })
      await searchDependencies({ q: 'flask' })
      expect(mockFetch).toHaveBeenCalledWith('/api/search/dependencies?q=flask')
    })

    it('builds query with all params', async () => {
      okJson({ results: [], total: 0, query: 'flask', limit: 0, offset: 0 })
      await searchDependencies({
        q: 'flask',
        repository_id: 1,
        language: 'python',
        dependency_type: 'runtime',
        is_direct: true,
        branch: 'main',
        limit: 5,
        offset: 10,
      })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/search/dependencies?q=flask&repository_id=1&language=python&dependency_type=runtime&is_direct=true&branch=main&limit=5&offset=10'
      )
    })
  })

  describe('resolveFilePath', () => {
    it('builds resolve-path query with required commit', async () => {
      okJson({ found: true, resolved_path: 'a.py' })
      await resolveFilePath('repo', 'a.py', 'abc')
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/renames/resolve-path?repo=repo&path=a.py&commit=abc'
      )
    })

    it('includes branch when provided', async () => {
      okJson({ found: true, resolved_path: 'a.py' })
      await resolveFilePath('repo', 'a.py', 'abc', 'main')
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/renames/resolve-path?repo=repo&path=a.py&commit=abc&branch=main'
      )
    })
  })

  describe('getActivityLog', () => {
    it('fetches without params', async () => {
      okJson({ entries: [], returned_count: 0 })
      await getActivityLog()
      expect(mockFetch).toHaveBeenCalledWith('/api/activity')
    })

    it('builds query from params including zero offset', async () => {
      okJson({ entries: [], returned_count: 0 })
      await getActivityLog({ source: 'mcp', repository: 'repo', limit: 10, offset: 0 })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/activity?source=mcp&repository=repo&limit=10&offset=0'
      )
    })
  })
})

describe('ApiError and fetchApi error handling', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('throws ApiError carrying the HTTP status', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'boom' }),
    })
    await expect(getRepositories()).rejects.toMatchObject({
      name: 'ApiError',
      message: 'boom',
      status: 500,
    })
  })

  it('falls back to HTTP status message when detail is not a string', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({ detail: { unexpected: 'shape' } }),
    })
    await expect(getRepositories()).rejects.toThrow('HTTP 503')
  })

  it('falls back to Unknown error when body cannot be parsed', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('not json')
      },
    })
    await expect(getRepositories()).rejects.toThrow('Unknown error')
  })

  it('ApiError is an instance of Error with a status field', () => {
    const err = new ApiError('nope', 404)
    expect(err).toBeInstanceOf(Error)
    expect(err.status).toBe(404)
    expect(err.name).toBe('ApiError')
  })
})
