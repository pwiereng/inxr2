import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import { CodeViewer } from './CodeViewer'
import type { FileSymbol, FileReference, BlameLine } from '@/lib/api'

describe('CodeViewer', () => {
  describe('basic rendering', () => {
    it('should render code content with line numbers', () => {
      const content = `line 1
line 2
line 3`
      render(<CodeViewer content={content} language="text" />)

      // Check that line numbers are rendered
      expect(screen.getByText('1')).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('should render correct number of rows', () => {
      const content = `line 1
line 2
line 3`
      render(<CodeViewer content={content} language="text" />)

      // Check for data-line attributes
      expect(document.querySelector('[data-line="1"]')).toBeInTheDocument()
      expect(document.querySelector('[data-line="2"]')).toBeInTheDocument()
      expect(document.querySelector('[data-line="3"]')).toBeInTheDocument()
    })
  })

  describe('symbol definitions', () => {
    it('should make symbol definition clickable', () => {
      const onSymbolClick = vi.fn()
      const symbols: FileSymbol[] = [
        {
          id: 1,
          name: 'myFunction',
          qualified_name: null,
          kind: 'function',
          start_line: 1,
          start_column: 4,
          end_line: 3,
          end_column: 0,
          signature: null,
        },
      ]

      render(
        <CodeViewer
          content="def myFunction():"
          language="python"
          symbols={symbols}
          onSymbolClick={onSymbolClick}
        />
      )

      // Click on the symbol - use getAllByText since Prism may create multiple spans
      const elements = screen.getAllByText(/myFunction/)
      expect(elements.length).toBeGreaterThan(0)
      fireEvent.click(elements[0]!)

      expect(onSymbolClick).toHaveBeenCalledWith(symbols[0])
    })

    it('should find symbol name even when start_column points to keyword', () => {
      // This tests the bug fix where start_column=0 pointed to "class" keyword
      // but we need to find "RepositoryMapper" which starts later in the line
      const onSymbolClick = vi.fn()
      const symbols: FileSymbol[] = [
        {
          id: 1,
          name: 'RepositoryMapper',
          qualified_name: null,
          kind: 'class',
          start_line: 1,
          start_column: 0, // Points to 'class' keyword, not the class name
          end_line: 10,
          end_column: 0,
          signature: null,
        },
      ]

      render(
        <CodeViewer
          content="class RepositoryMapper:"
          language="python"
          symbols={symbols}
          onSymbolClick={onSymbolClick}
        />
      )

      // The class name should still be clickable
      const elements = screen.getAllByText(/RepositoryMapper/)
      expect(elements.length).toBeGreaterThan(0)
      fireEvent.click(elements[0]!)

      expect(onSymbolClick).toHaveBeenCalledWith(symbols[0])
    })

    it('should not match symbol name that is part of a larger word', () => {
      // "name" should not match inside "myname" or "name123"
      const onSymbolClick = vi.fn()
      const symbols: FileSymbol[] = [
        {
          id: 1,
          name: 'name',
          qualified_name: null,
          kind: 'variable',
          start_line: 1,
          start_column: 0,
          end_line: 1,
          end_column: 4,
          signature: null,
        },
      ]

      // Line contains "myname" but not standalone "name"
      render(
        <CodeViewer
          content="myname = 123"
          language="python"
          symbols={symbols}
          onSymbolClick={onSymbolClick}
        />
      )

      // Click on the text - should not find a clickable symbol
      const elements = screen.queryAllByText(/name/)
      // Even if we find text containing "name", clicking should not trigger handler
      // because "name" is part of "myname", not a standalone word
      if (elements.length > 0) {
        fireEvent.click(elements[0]!)
      }
      expect(onSymbolClick).not.toHaveBeenCalled()
    })

    it('should match symbol name after a dot separator', () => {
      // "name" in "self.name" should be clickable (dot is not a word char)
      const onSymbolClick = vi.fn()
      const symbols: FileSymbol[] = [
        {
          id: 1,
          name: 'name',
          qualified_name: null,
          kind: 'attribute',
          start_line: 1,
          start_column: 0,
          end_line: 1,
          end_column: 9,
          signature: null,
        },
      ]

      render(
        <CodeViewer
          content="self.name = value"
          language="python"
          symbols={symbols}
          onSymbolClick={onSymbolClick}
        />
      )

      // "name" after the dot should be clickable
      const elements = screen.getAllByText(/name/)
      expect(elements.length).toBeGreaterThan(0)
      fireEvent.click(elements[0]!)

      expect(onSymbolClick).toHaveBeenCalledWith(symbols[0])
    })

    it('should match correct occurrence when symbol appears multiple times', () => {
      // In "name = self.name", we should match based on word boundaries
      const onSymbolClick = vi.fn()
      const symbols: FileSymbol[] = [
        {
          id: 1,
          name: 'name',
          qualified_name: null,
          kind: 'variable',
          start_line: 1,
          start_column: 0, // Points to start of line where "name" variable is
          end_line: 1,
          end_column: 4,
          signature: null,
        },
      ]

      render(
        <CodeViewer
          content="name = self.name"
          language="text"
          symbols={symbols}
          onSymbolClick={onSymbolClick}
        />
      )

      // Should find and make the first "name" clickable
      const elements = screen.getAllByText('name')
      expect(elements.length).toBeGreaterThanOrEqual(1)
      fireEvent.click(elements[0]!)

      expect(onSymbolClick).toHaveBeenCalledWith(symbols[0])
    })

    it('should make class variable with type annotation clickable', () => {
      // Test case: Python class variable like "    indexing_status: str = 'pending'"
      // The symbol starts at column 4 (after indentation)
      const onSymbolClick = vi.fn()
      const symbols: FileSymbol[] = [
        {
          id: 1,
          name: 'indexing_status',
          qualified_name: 'IndexStatus.indexing_status',
          kind: 'class_variable',
          start_line: 1,
          start_column: 4, // After 4 spaces of indentation
          end_line: 1,
          end_column: 38,
          signature: null,
        },
      ]

      // Test with Python language to verify Prism doesn't break clicking
      render(
        <CodeViewer
          content="    indexing_status: str = 'pending'"
          language="python"
          symbols={symbols}
          onSymbolClick={onSymbolClick}
        />
      )

      // The class variable name should be clickable
      const elements = screen.getAllByText(/indexing_status/)
      expect(elements.length).toBeGreaterThan(0)
      fireEvent.click(elements[0]!)

      expect(onSymbolClick).toHaveBeenCalledWith(symbols[0])
    })
  })

  describe('references', () => {
    it('should make reference with target_symbol_id clickable', () => {
      const onReferenceClick = vi.fn()
      const references: FileReference[] = [
        {
          id: 1,
          reference_text: 'helper',
          reference_type: 'call',
          source_line: 1,
          source_column: 0,
          target_symbol_id: 100,
        },
      ]

      render(
        <CodeViewer
          content="helper()"
          language="python"
          references={references}
          onReferenceClick={onReferenceClick}
        />
      )

      const elements = screen.getAllByText(/helper/)
      expect(elements.length).toBeGreaterThan(0)
      fireEvent.click(elements[0]!)

      expect(onReferenceClick).toHaveBeenCalledWith(references[0])
    })

    it('should make reference without target_symbol_id clickable', () => {
      const onReferenceClick = vi.fn()
      const references: FileReference[] = [
        {
          id: 1,
          reference_text: 'unresolved',
          reference_type: 'call',
          source_line: 1,
          source_column: 0,
          target_symbol_id: null, // Unresolved reference
        },
      ]

      render(
        <CodeViewer
          content="unresolved()"
          language="python"
          references={references}
          onReferenceClick={onReferenceClick}
        />
      )

      // Click on the text - unresolved refs should still be clickable
      const elements = screen.getAllByText(/unresolved/)
      expect(elements.length).toBeGreaterThan(0)
      fireEvent.click(elements[0]!)

      expect(onReferenceClick).toHaveBeenCalledWith(references[0])
    })

    it('should make multiple references on same line all clickable', () => {
      // This tests the bug fix for multiple references per line
      const onReferenceClick = vi.fn()
      const references: FileReference[] = [
        {
          id: 1,
          reference_text: 'foo',
          reference_type: 'call',
          source_line: 1,
          source_column: 0,
          target_symbol_id: 100,
        },
        {
          id: 2,
          reference_text: 'bar',
          reference_type: 'call',
          source_line: 1,
          source_column: 7,
          target_symbol_id: 101,
        },
        {
          id: 3,
          reference_text: 'baz',
          reference_type: 'call',
          source_line: 1,
          source_column: 14,
          target_symbol_id: 102,
        },
      ]

      // Simple line without syntax that would be broken up by Prism
      const lineContent = 'foo(), bar(), baz()'

      render(
        <CodeViewer
          content={lineContent}
          language="text" // Use text to avoid Prism splitting
          references={references}
          onReferenceClick={onReferenceClick}
        />
      )

      // All three references should be clickable
      fireEvent.click(screen.getByText('foo'))
      expect(onReferenceClick).toHaveBeenLastCalledWith(references[0])

      fireEvent.click(screen.getByText('bar'))
      expect(onReferenceClick).toHaveBeenLastCalledWith(references[1])

      fireEvent.click(screen.getByText('baz'))
      expect(onReferenceClick).toHaveBeenLastCalledWith(references[2])

      expect(onReferenceClick).toHaveBeenCalledTimes(3)
    })
  })

  describe('line click', () => {
    it('should call onLineClick when line number is clicked', () => {
      const onLineClick = vi.fn()
      const content = `line 1
line 2
line 3`

      render(<CodeViewer content={content} language="text" onLineClick={onLineClick} />)

      // Click on line number 2
      fireEvent.click(screen.getByText('2'))

      expect(onLineClick).toHaveBeenCalledWith(2)
    })
  })

  describe('highlight', () => {
    it('should have data-line attribute for highlighted line', () => {
      // Mock scrollIntoView since jsdom doesn't support it
      Element.prototype.scrollIntoView = vi.fn()

      const content = `line 1
line 2
line 3`
      render(<CodeViewer content={content} language="text" highlightLine={2} />)

      const line2Row = document.querySelector('[data-line="2"]')
      expect(line2Row).toBeInTheDocument()
    })
  })

  describe('blame annotations', () => {
    const makeBlameData = (overrides: Partial<BlameLine> = {}): BlameLine[] => [
      {
        line_number: 1,
        commit_hash: 'abc123def456abc123def456abc123def456abc1',
        short_hash: 'abc123d',
        author_name: 'Test Author',
        commit_date: '2026-01-15',
        message: 'test commit',
        is_indexed: true,
        ...overrides,
      },
    ]

    it('should call onBlameCommitClick when clicking an indexed blame hash', () => {
      const onBlameCommitClick = vi.fn()
      const blameData = makeBlameData({ is_indexed: true })

      render(
        <CodeViewer
          content="line 1"
          language="text"
          blameData={blameData}
          onBlameCommitClick={onBlameCommitClick}
        />
      )

      fireEvent.click(screen.getByText('abc123d'))
      expect(onBlameCommitClick).toHaveBeenCalledWith('abc123def456abc123def456abc123def456abc1')
    })

    it('should call onBlameCommitClick when clicking an un-indexed blame hash', () => {
      const onBlameCommitClick = vi.fn()
      const blameData = makeBlameData({ is_indexed: false })

      render(
        <CodeViewer
          content="line 1"
          language="text"
          blameData={blameData}
          onBlameCommitClick={onBlameCommitClick}
        />
      )

      // Un-indexed commits should still be clickable
      fireEvent.click(screen.getByText('abc123d'))
      expect(onBlameCommitClick).toHaveBeenCalledWith('abc123def456abc123def456abc123def456abc1')
    })
  })

  describe('context menu', () => {
    it('should show menu on right-click when text is selected and onSearchText provided', () => {
      const onSearchText = vi.fn()
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => 'selectedCode',
      } as Selection)

      render(
        <CodeViewer content="some selectedCode here" language="text" onSearchText={onSearchText} />
      )

      // Right-click on the code area
      const codeRow = document.querySelector('[data-line="1"]')!
      fireEvent.contextMenu(codeRow)

      // Menu item should appear with the search text
      expect(screen.getByRole('menuitem')).toHaveTextContent("Search for 'selectedCode'")
    })

    it('should call onSearchText with selected text when menu item is clicked', () => {
      const onSearchText = vi.fn()
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => 'myVar',
      } as Selection)

      render(<CodeViewer content="const myVar = 1" language="text" onSearchText={onSearchText} />)

      // Right-click
      const codeRow = document.querySelector('[data-line="1"]')!
      fireEvent.contextMenu(codeRow)

      // Click the search menu item
      fireEvent.click(screen.getByText(/Search for/))

      expect(onSearchText).toHaveBeenCalledWith('myVar')
    })

    it('should NOT show menu when no text is selected', () => {
      const onSearchText = vi.fn()
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => '',
      } as Selection)

      render(<CodeViewer content="some code here" language="text" onSearchText={onSearchText} />)

      const codeRow = document.querySelector('[data-line="1"]')!
      fireEvent.contextMenu(codeRow)

      expect(screen.queryByText(/Search for/)).not.toBeInTheDocument()
    })

    it('should NOT show menu when onSearchText is not provided', () => {
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => 'selectedCode',
      } as Selection)

      render(<CodeViewer content="some selectedCode here" language="text" />)

      const codeRow = document.querySelector('[data-line="1"]')!
      fireEvent.contextMenu(codeRow)

      expect(screen.queryByText(/Search for/)).not.toBeInTheDocument()
    })
  })
})
