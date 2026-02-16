import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import { FileTreeFilter } from './FileTreeFilter'
import type { TreeNode } from '@/lib/api'

const sampleTree: TreeNode[] = [
  {
    name: 'src',
    path: 'src',
    type: 'directory',
    file_id: null,
    language: null,
    children: [
      {
        name: 'components',
        path: 'src/components',
        type: 'directory',
        file_id: null,
        language: null,
        children: [
          {
            name: 'Button.tsx',
            path: 'src/components/Button.tsx',
            type: 'file',
            file_id: 1,
            language: 'typescript',
            children: null,
          },
        ],
      },
      {
        name: 'index.ts',
        path: 'src/index.ts',
        type: 'file',
        file_id: 4,
        language: 'typescript',
        children: null,
      },
    ],
  },
  {
    name: 'README.md',
    path: 'README.md',
    type: 'file',
    file_id: 5,
    language: 'markdown',
    children: null,
  },
]

describe('FileTreeFilter', () => {
  const defaultProps = {
    nodes: sampleTree,
    filterText: '',
    onFilterChange: vi.fn(),
    onFileSelect: vi.fn(),
    onDirectorySelect: vi.fn(),
  }

  it('should render the filter input', () => {
    render(<FileTreeFilter {...defaultProps} />)
    expect(screen.getByLabelText('Filter files')).toBeInTheDocument()
  })

  it('should show results when filterText is non-empty', () => {
    render(<FileTreeFilter {...defaultProps} filterText="Button" />)
    expect(screen.getByText('src/components/Button.tsx')).toBeInTheDocument()
  })

  it('should show "No matches found" for non-matching query', () => {
    render(<FileTreeFilter {...defaultProps} filterText="zzzznotfound" />)
    expect(screen.getByText('No matches found')).toBeInTheDocument()
  })

  it('should not show results when filterText is empty', () => {
    render(<FileTreeFilter {...defaultProps} filterText="" />)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('should call onFileSelect when a file result is clicked', () => {
    const onFileSelect = vi.fn()
    render(<FileTreeFilter {...defaultProps} filterText="Button" onFileSelect={onFileSelect} />)
    fireEvent.click(screen.getByText('src/components/Button.tsx'))
    expect(onFileSelect).toHaveBeenCalledWith('src/components/Button.tsx')
  })

  it('should call onDirectorySelect when a directory result is clicked', () => {
    const onDirectorySelect = vi.fn()
    render(
      <FileTreeFilter
        {...defaultProps}
        filterText="components"
        onDirectorySelect={onDirectorySelect}
      />
    )
    // Click the directory result (first result — "components" name-matches)
    fireEvent.click(screen.getByText('src/components'))
    expect(onDirectorySelect).toHaveBeenCalledWith('src/components')
  })

  it('should call onFilterChange with empty string on Escape', () => {
    const onFilterChange = vi.fn()
    render(<FileTreeFilter {...defaultProps} filterText="Button" onFilterChange={onFilterChange} />)
    const input = screen.getByLabelText('Filter files')
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(onFilterChange).toHaveBeenCalledWith('')
  })

  it('should select result with arrow keys and Enter', () => {
    const onFileSelect = vi.fn()
    render(<FileTreeFilter {...defaultProps} filterText="ts" onFileSelect={onFileSelect} />)
    const input = screen.getByLabelText('Filter files')

    // Press ArrowDown to move to second result, then Enter to select
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'Enter' })

    // Should have called onFileSelect (the exact file depends on ranking)
    expect(onFileSelect).toHaveBeenCalled()
  })

  it('should show clear button when filterText is non-empty', () => {
    const onFilterChange = vi.fn()
    render(<FileTreeFilter {...defaultProps} filterText="test" onFilterChange={onFilterChange} />)
    const clearButton = screen.getByLabelText('Clear filter')
    fireEvent.click(clearButton)
    expect(onFilterChange).toHaveBeenCalledWith('')
  })
})
