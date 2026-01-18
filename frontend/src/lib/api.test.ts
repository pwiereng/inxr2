import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  getRepositoryByName,
  getRepositoryTreeByName,
  getFileContentByPath,
  getFileSymbolsByPath,
  getFileReferencesByPath,
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

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/repositories/by-name/my-repo'
      )
      expect(result).toEqual(mockRepo)
    })

    it('should encode special characters in repository name', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 1, name: 'repo with spaces' }),
      })

      await getRepositoryByName('repo with spaces')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/repositories/by-name/repo%20with%20spaces'
      )
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

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/repositories/by-name/my-repo/tree'
      )
      expect(result).toEqual(mockTree)
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

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/files/by-path?repo=my-repo&path=src%2Fmain.py'
      )
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
        'http://localhost:8000/api/files/by-path/symbols?repo=my-repo&path=src%2Futils.py'
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
        'http://localhost:8000/api/files/by-path/references?repo=my-repo&path=src%2Fmain.py'
      )
      expect(result).toEqual(mockRefs)
    })
  })
})
