import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  getRepositoryByName,
  getRepositoryTreeByName,
  getFileContentByPath,
  getFileSymbolsByPath,
  getFileReferencesByPath,
  searchText,
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
