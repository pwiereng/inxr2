import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import { DirectoryListing } from './DirectoryListing'
import type { TreeNode } from '@/lib/api'

// Extend the theme with fileTree palette required by FileTypeIcon
const theme = createTheme({
  palette: {
    fileTree: {
      folder: '#90a4ae',
      defaultFile: '#78909c',
    },
  } as never,
})

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>)
}

const sampleTree: TreeNode[] = [
  {
    name: 'src',
    path: 'src',
    type: 'directory',
    file_id: null,
    language: null,
    children: [
      {
        name: 'main.py',
        path: 'src/main.py',
        type: 'file',
        file_id: 1,
        language: 'python',
        children: null,
      },
      {
        name: 'utils',
        path: 'src/utils',
        type: 'directory',
        file_id: null,
        language: null,
        children: [
          {
            name: 'helpers.py',
            path: 'src/utils/helpers.py',
            type: 'file',
            file_id: 2,
            language: 'python',
            children: null,
          },
        ],
      },
    ],
  },
  {
    name: 'README.md',
    path: 'README.md',
    type: 'file',
    file_id: 3,
    language: 'markdown',
    children: null,
  },
]

describe('DirectoryListing', () => {
  const defaultProps = {
    treeNodes: sampleTree,
    directoryPath: null as string | null,
    onFileSelect: vi.fn(),
    onDirectorySelect: vi.fn(),
    onParentClick: vi.fn(),
  }

  it('should show root-level entries when directoryPath is null', () => {
    renderWithTheme(<DirectoryListing {...defaultProps} />)
    expect(screen.getByText('src/')).toBeInTheDocument()
    expect(screen.getByText('README.md')).toBeInTheDocument()
  })

  it('should show directory children when directoryPath is set', () => {
    renderWithTheme(<DirectoryListing {...defaultProps} directoryPath="src" />)
    expect(screen.getByText('utils/')).toBeInTheDocument()
    expect(screen.getByText('main.py')).toBeInTheDocument()
    // Root-level items should not appear
    expect(screen.queryByText('README.md')).not.toBeInTheDocument()
  })

  it('should show .. then directories then files', () => {
    renderWithTheme(<DirectoryListing {...defaultProps} directoryPath="src" />)
    const rows = screen.getAllByRole('row')
    // First row is "..", then directories, then files
    expect(rows[0]).toHaveTextContent('..')
    expect(rows[1]).toHaveTextContent('utils/')
    expect(rows[2]).toHaveTextContent('main.py')
  })

  it('should not show .. at root level', () => {
    renderWithTheme(<DirectoryListing {...defaultProps} />)
    expect(screen.queryByText('..')).not.toBeInTheDocument()
  })

  it('should call onParentClick when .. is clicked', () => {
    const onParentClick = vi.fn()
    renderWithTheme(
      <DirectoryListing {...defaultProps} directoryPath="src" onParentClick={onParentClick} />
    )
    fireEvent.click(screen.getByText('..'))
    expect(onParentClick).toHaveBeenCalled()
  })

  it('should call onFileSelect when a file is clicked', () => {
    const onFileSelect = vi.fn()
    renderWithTheme(
      <DirectoryListing {...defaultProps} directoryPath="src" onFileSelect={onFileSelect} />
    )
    fireEvent.click(screen.getByText('main.py'))
    expect(onFileSelect).toHaveBeenCalledWith('src/main.py')
  })

  it('should call onDirectorySelect when a directory is clicked', () => {
    const onDirectorySelect = vi.fn()
    renderWithTheme(
      <DirectoryListing
        {...defaultProps}
        directoryPath="src"
        onDirectorySelect={onDirectorySelect}
      />
    )
    fireEvent.click(screen.getByText('utils/'))
    expect(onDirectorySelect).toHaveBeenCalledWith('src/utils')
  })

  it('should show empty message for empty directory', () => {
    renderWithTheme(
      <DirectoryListing
        {...defaultProps}
        treeNodes={[
          {
            name: 'empty',
            path: 'empty',
            type: 'directory',
            file_id: null,
            language: null,
            children: [],
          },
        ]}
        directoryPath="empty"
      />
    )
    expect(screen.getByText('This directory is empty')).toBeInTheDocument()
  })
})
