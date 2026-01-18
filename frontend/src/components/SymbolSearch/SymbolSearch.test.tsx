import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SymbolSearch } from './SymbolSearch'

// Mock the API module
vi.mock('@/lib/api', () => ({
  searchSymbols: vi.fn().mockResolvedValue({ items: [] }),
}))

describe('SymbolSearch', () => {
  describe('uncontrolled mode', () => {
    it('should render with placeholder', () => {
      render(<SymbolSearch placeholder="Search..." />)

      expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument()
    })

    it('should allow typing in the search field', () => {
      render(<SymbolSearch />)

      const input = screen.getByRole('combobox')
      fireEvent.change(input, { target: { value: 'test' } })

      expect(input).toHaveValue('test')
    })
  })

  describe('controlled mode', () => {
    it('should display the provided value', () => {
      render(<SymbolSearch value="MyClass" onValueChange={() => {}} />)

      const input = screen.getByRole('combobox')
      expect(input).toHaveValue('MyClass')
    })

    it('should call onValueChange when input changes', () => {
      const onValueChange = vi.fn()
      render(<SymbolSearch value="" onValueChange={onValueChange} />)

      const input = screen.getByRole('combobox')
      fireEvent.change(input, { target: { value: 'newValue' } })

      expect(onValueChange).toHaveBeenCalledWith('newValue')
    })

    it('should update displayed value when prop changes', () => {
      const { rerender } = render(<SymbolSearch value="initial" onValueChange={() => {}} />)

      expect(screen.getByRole('combobox')).toHaveValue('initial')

      rerender(<SymbolSearch value="updated" onValueChange={() => {}} />)

      expect(screen.getByRole('combobox')).toHaveValue('updated')
    })

    it('should work when value is set externally (simulating symbol click)', async () => {
      // This simulates the Browse page setting the search value when a symbol is clicked
      const onValueChange = vi.fn()
      const { rerender } = render(<SymbolSearch value="" onValueChange={onValueChange} />)

      const input = screen.getByRole('combobox')
      expect(input).toHaveValue('')

      // Simulate external update (like clicking a symbol in code viewer)
      rerender(<SymbolSearch value="RepositoryMapper" onValueChange={onValueChange} />)

      await waitFor(() => {
        expect(input).toHaveValue('RepositoryMapper')
      })
    })
  })

  describe('symbol selection', () => {
    it('should call onSymbolSelect when a symbol is selected', async () => {
      const { searchSymbols } = await import('@/lib/api')
      const mockSymbol = {
        id: 1,
        name: 'TestSymbol',
        qualified_name: 'module.TestSymbol',
        kind: 'class',
        file_id: 1,
        file_path: 'src/test.py',
        repository_id: 1,
        commit_id: 1,
        start_line: 10,
        start_column: 0,
        end_line: 20,
        end_column: 0,
        signature: null,
        docstring: null,
      }

      vi.mocked(searchSymbols).mockResolvedValueOnce({
        items: [mockSymbol],
        total: 1,
        limit: 20,
        offset: 0,
      })

      const onSymbolSelect = vi.fn()
      render(<SymbolSearch onSymbolSelect={onSymbolSelect} />)

      const input = screen.getByRole('combobox')
      fireEvent.change(input, { target: { value: 'Test' } })

      // Wait for debounced search and results
      await waitFor(
        () => {
          expect(screen.getByText('TestSymbol')).toBeInTheDocument()
        },
        { timeout: 500 }
      )

      // Click on the option
      fireEvent.click(screen.getByText('TestSymbol'))

      expect(onSymbolSelect).toHaveBeenCalledWith(mockSymbol)
    })
  })
})
