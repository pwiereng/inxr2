import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/utils'
import { ReferencesPanel } from './ReferencesPanel'
import * as api from '@/lib/api'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getSymbolReferences: vi.fn(),
  getSymbolsByName: vi.fn(),
  searchText: vi.fn(),
}))

const mockGetSymbolReferences = vi.mocked(api.getSymbolReferences)
const mockGetSymbolsByName = vi.mocked(api.getSymbolsByName)
const mockSearchText = vi.mocked(api.searchText)

describe('ReferencesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mockSymbol: api.Symbol = {
    id: 1,
    name: 'TestClass',
    qualified_name: 'module.TestClass',
    kind: 'class',
    file_id: 1,
    file_path: 'src/test.py',
    repository_id: 1,
    commit_id: 1,
    start_line: 10,
    start_column: 0,
    end_line: 50,
    end_column: 0,
    signature: null,
    docstring: null,
  }

  const mockReferences: api.Reference[] = [
    {
      id: 1,
      source_file_id: 2,
      source_file_path: 'src/other.py',
      source_line: 5,
      source_column: 0,
      target_symbol_id: 1,
      reference_type: 'import',
      reference_text: 'TestClass',
    },
    {
      id: 2,
      source_file_id: 3,
      source_file_path: 'src/main.py',
      source_line: 20,
      source_column: 0,
      target_symbol_id: 1,
      reference_type: 'call',
      reference_text: 'TestClass',
    },
  ]

  describe('with symbol prop', () => {
    it('should fetch and display references for the symbol', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: mockReferences,
        total: 2,
        symbol_name: 'TestClass',
      })

      render(<ReferencesPanel symbol={mockSymbol} isDirectDefinition={true} />)

      await waitFor(() => {
        expect(mockGetSymbolReferences).toHaveBeenCalledWith(1, 100, undefined, undefined)
      })

      // Should show references count
      await waitFor(() => {
        expect(screen.getByText('2 references')).toBeInTheDocument()
      })

      // Should show reference entries
      expect(screen.getByText('src/other.py')).toBeInTheDocument()
      expect(screen.getByText('src/main.py')).toBeInTheDocument()
    })

    it('should pass selectedCommit to API calls', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(
        <ReferencesPanel symbol={mockSymbol} isDirectDefinition={true} selectedCommit="abc123" />
      )

      await waitFor(() => {
        expect(mockGetSymbolReferences).toHaveBeenCalledWith(1, 100, 'abc123', undefined)
      })
    })

    it('should pass selectedBranch to API calls', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(
        <ReferencesPanel symbol={mockSymbol} isDirectDefinition={true} selectedBranch="main" />
      )

      await waitFor(() => {
        expect(mockGetSymbolReferences).toHaveBeenCalledWith(1, 100, undefined, 'main')
      })
    })

    it('should pass both selectedCommit and selectedBranch to API calls', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(
        <ReferencesPanel
          symbol={mockSymbol}
          isDirectDefinition={true}
          selectedCommit="abc123"
          selectedBranch="feature"
        />
      )

      await waitFor(() => {
        expect(mockGetSymbolReferences).toHaveBeenCalledWith(1, 100, 'abc123', 'feature')
      })
    })
  })

  describe('with searchByName prop (diff mode panel switch)', () => {
    it('should fetch definitions AND references when searching by name', async () => {
      // This tests the fix for the bug where switching refs panel in diff mode
      // would only show definitions, not references
      mockGetSymbolsByName.mockResolvedValue({
        items: [mockSymbol],
        total: 1,
        limit: 20,
        offset: 0,
      })
      mockGetSymbolReferences.mockResolvedValue({
        items: mockReferences,
        total: 2,
        symbol_name: 'TestClass',
      })

      render(
        <ReferencesPanel symbol={null} searchByName={{ name: 'TestClass', repositoryId: 1 }} />
      )

      // Should fetch definitions by name
      await waitFor(() => {
        expect(mockGetSymbolsByName).toHaveBeenCalledWith('TestClass', 1, undefined)
      })

      // Should also fetch references for the first definition found
      await waitFor(() => {
        expect(mockGetSymbolReferences).toHaveBeenCalledWith(1, 100, undefined, undefined)
      })

      // Should display references
      await waitFor(() => {
        expect(screen.getByText('src/other.py')).toBeInTheDocument()
        expect(screen.getByText('src/main.py')).toBeInTheDocument()
      })
    })

    it('should pass selectedCommit when searching by name', async () => {
      mockGetSymbolsByName.mockResolvedValue({
        items: [mockSymbol],
        total: 1,
        limit: 20,
        offset: 0,
      })
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(
        <ReferencesPanel
          symbol={null}
          searchByName={{ name: 'TestClass', repositoryId: 1 }}
          selectedCommit="def456"
        />
      )

      await waitFor(() => {
        expect(mockGetSymbolsByName).toHaveBeenCalledWith('TestClass', 1, 'def456')
      })

      await waitFor(() => {
        expect(mockGetSymbolReferences).toHaveBeenCalledWith(1, 100, 'def456', undefined)
      })
    })

    it('should pass selectedBranch when searching by name', async () => {
      mockGetSymbolsByName.mockResolvedValue({
        items: [mockSymbol],
        total: 1,
        limit: 20,
        offset: 0,
      })
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(
        <ReferencesPanel
          symbol={null}
          searchByName={{ name: 'TestClass', repositoryId: 1 }}
          selectedBranch="feature"
        />
      )

      await waitFor(() => {
        expect(mockGetSymbolReferences).toHaveBeenCalledWith(1, 100, undefined, 'feature')
      })
    })

    it('should fall back to text search when no definitions found', async () => {
      mockGetSymbolsByName.mockResolvedValue({
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
      })
      mockSearchText.mockResolvedValue({
        results: [
          {
            id: 1,
            repository_id: 1,
            repository_name: 'test',
            file_path: 'src/app.py',
            source_line: 10,
            source_end_line: 10,
            source_type: 'reference',
            content: 'include_router',
            content_type: 'call',
            language: 'python',
            commit_hash: null,
            branch: null,
            rank: 1.0,
            headline: null,
          },
        ],
        total: 1,
        query: 'include_router',
        mode: 'keyword',
        limit: 100,
        offset: 0,
      })

      render(
        <ReferencesPanel symbol={null} searchByName={{ name: 'include_router', repositoryId: 1 }} />
      )

      await waitFor(() => {
        expect(mockGetSymbolsByName).toHaveBeenCalled()
      })

      // Should NOT call getSymbolReferences — no definitions to get refs for
      expect(mockGetSymbolReferences).not.toHaveBeenCalled()

      // Should fall back to searchText with source_types=['reference']
      await waitFor(() => {
        expect(mockSearchText).toHaveBeenCalledWith({
          q: 'include_router',
          mode: 'keyword',
          repo: 1,
          branch: undefined,
          commit: undefined,
          source_types: ['reference'],
          limit: 100,
        })
      })

      // Should display the reference from text search
      await waitFor(() => {
        expect(screen.getByText('src/app.py')).toBeInTheDocument()
      })
    })

    it('should pass selectedCommit and selectedBranch to text search fallback', async () => {
      mockGetSymbolsByName.mockResolvedValue({
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
      })
      mockSearchText.mockResolvedValue({
        results: [],
        total: 0,
        query: 'someName',
        mode: 'keyword',
        limit: 100,
        offset: 0,
      })

      render(
        <ReferencesPanel
          symbol={null}
          searchByName={{ name: 'someName', repositoryId: 1 }}
          selectedCommit="abc123"
          selectedBranch="feature"
        />
      )

      await waitFor(() => {
        expect(mockSearchText).toHaveBeenCalledWith({
          q: 'someName',
          mode: 'keyword',
          repo: 1,
          branch: 'feature',
          commit: 'abc123',
          source_types: ['reference'],
          limit: 100,
        })
      })
    })
  })

  describe('definition file path display', () => {
    it('should show filename only when there is a single definition', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(<ReferencesPanel symbol={mockSymbol} isDirectDefinition={true} />)

      await waitFor(() => {
        // Single definition: should show just the filename, not the full path
        expect(screen.getByText('test.py')).toBeInTheDocument()
        expect(screen.queryByText('src/test.py')).not.toBeInTheDocument()
      })
    })

    it('should show full path when there are multiple definitions', async () => {
      const secondSymbol: api.Symbol = {
        ...mockSymbol,
        id: 2,
        file_id: 2,
        file_path: 'lib/test.py',
        start_line: 5,
      }

      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })
      mockGetSymbolsByName.mockResolvedValue({
        items: [mockSymbol, secondSymbol],
        total: 2,
        limit: 20,
        offset: 0,
      })

      render(<ReferencesPanel symbol={mockSymbol} isDirectDefinition={false} />)

      await waitFor(() => {
        // Multiple definitions: should show full paths to disambiguate
        expect(screen.getByText('src/test.py')).toBeInTheDocument()
        expect(screen.getByText('lib/test.py')).toBeInTheDocument()
      })
    })
  })

  describe('search globally link', () => {
    it('should render link with correct URL when symbol is provided', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(<ReferencesPanel symbol={mockSymbol} isDirectDefinition={true} />)

      await waitFor(() => {
        const link = screen.getByText(/Search globally for/).closest('a')
        expect(link).toBeInTheDocument()
        expect(link).toHaveAttribute('href', '/search?query=TestClass&types=symbol,reference')
      })
    })

    it('should render link when using searchByName', async () => {
      mockGetSymbolsByName.mockResolvedValue({
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
      })
      mockSearchText.mockResolvedValue({
        results: [],
        total: 0,
        query: 'myFunction',
        mode: 'keyword',
        limit: 100,
        offset: 0,
      })

      render(
        <ReferencesPanel symbol={null} searchByName={{ name: 'myFunction', repositoryId: 1 }} />
      )

      await waitFor(() => {
        const link = screen.getByText(/Search globally for/).closest('a')
        expect(link).toBeInTheDocument()
        expect(link).toHaveAttribute('href', '/search?query=myFunction&types=symbol,reference')
      })
    })

    it('should not render link when no symbol or searchByName', () => {
      render(<ReferencesPanel symbol={null} />)

      expect(screen.queryByText(/Search globally for/)).not.toBeInTheDocument()
    })
  })

  describe('View in Logical View link', () => {
    it('should show link when repoName and symbol.file_path are provided', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(<ReferencesPanel symbol={mockSymbol} isDirectDefinition={true} repoName="test-repo" />)

      await waitFor(() => {
        const link = screen.getByText('View in Logical View').closest('a')
        expect(link).toBeInTheDocument()
        expect(link).toHaveAttribute('href', '/logical-view?repo=test-repo&file=src%2Ftest.py')
      })
    })

    it('should include branch and commit in URL when provided', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(
        <ReferencesPanel
          symbol={mockSymbol}
          isDirectDefinition={true}
          repoName="test-repo"
          selectedBranch="feature"
          selectedCommit="abc123"
        />
      )

      await waitFor(() => {
        const link = screen.getByText('View in Logical View').closest('a')
        expect(link).toBeInTheDocument()
        expect(link).toHaveAttribute(
          'href',
          '/logical-view?repo=test-repo&branch=feature&commit=abc123&file=src%2Ftest.py'
        )
      })
    })

    it('should not show link when repoName is not provided', async () => {
      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })

      render(<ReferencesPanel symbol={mockSymbol} isDirectDefinition={true} />)

      await waitFor(() => {
        expect(screen.queryByText('View in Logical View')).not.toBeInTheDocument()
      })
    })

    it('should use allDefinitions file_path when symbol has no file_path', async () => {
      const symbolNoPath: api.Symbol = {
        ...mockSymbol,
        file_path: null,
      }
      const definitionWithPath: api.Symbol = {
        ...mockSymbol,
        id: 5,
        file_path: 'src/resolved.py',
      }

      mockGetSymbolReferences.mockResolvedValue({
        items: [],
        total: 0,
        symbol_name: 'TestClass',
      })
      mockGetSymbolsByName.mockResolvedValue({
        items: [definitionWithPath],
        total: 1,
        limit: 20,
        offset: 0,
      })

      render(
        <ReferencesPanel symbol={symbolNoPath} isDirectDefinition={false} repoName="test-repo" />
      )

      await waitFor(() => {
        const link = screen.getByText('View in Logical View').closest('a')
        expect(link).toBeInTheDocument()
        expect(link).toHaveAttribute('href', '/logical-view?repo=test-repo&file=src%2Fresolved.py')
      })
    })
  })

  describe('empty state', () => {
    it('should show prompt when no symbol or searchByName provided', () => {
      render(<ReferencesPanel symbol={null} />)

      expect(screen.getByText('Select a symbol to see its references')).toBeInTheDocument()
    })
  })
})
