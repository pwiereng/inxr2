import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/utils'
import { ReferencesPanel } from './ReferencesPanel'
import * as api from '@/lib/api'

// Mock the API module
vi.mock('@/lib/api', () => ({
  getSymbolReferences: vi.fn(),
  getSymbolsByName: vi.fn(),
}))

const mockGetSymbolReferences = vi.mocked(api.getSymbolReferences)
const mockGetSymbolsByName = vi.mocked(api.getSymbolsByName)

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

    it('should not fetch references if no definitions found', async () => {
      mockGetSymbolsByName.mockResolvedValue({
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
      })

      render(
        <ReferencesPanel symbol={null} searchByName={{ name: 'NonExistent', repositoryId: 1 }} />
      )

      await waitFor(() => {
        expect(mockGetSymbolsByName).toHaveBeenCalled()
      })

      // Should NOT call getSymbolReferences when no definitions found
      expect(mockGetSymbolReferences).not.toHaveBeenCalled()
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
        expect(link).toHaveAttribute(
          'href',
          '/search?query=TestClass&source_types=symbol,reference'
        )
      })
    })

    it('should render link when using searchByName', async () => {
      mockGetSymbolsByName.mockResolvedValue({
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
      })

      render(
        <ReferencesPanel symbol={null} searchByName={{ name: 'myFunction', repositoryId: 1 }} />
      )

      await waitFor(() => {
        const link = screen.getByText(/Search globally for/).closest('a')
        expect(link).toBeInTheDocument()
        expect(link).toHaveAttribute(
          'href',
          '/search?query=myFunction&source_types=symbol,reference'
        )
      })
    })

    it('should not render link when no symbol or searchByName', () => {
      render(<ReferencesPanel symbol={null} />)

      expect(screen.queryByText(/Search globally for/)).not.toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('should show prompt when no symbol or searchByName provided', () => {
      render(<ReferencesPanel symbol={null} />)

      expect(screen.getByText('Select a symbol to see its references')).toBeInTheDocument()
    })
  })
})
