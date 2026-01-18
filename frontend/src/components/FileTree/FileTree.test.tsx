import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { FileTree } from './FileTree'
import type { TreeNode } from '@/lib/api'

// Sample tree structure for testing
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
          {
            name: 'Input.tsx',
            path: 'src/components/Input.tsx',
            type: 'file',
            file_id: 2,
            language: 'typescript',
            children: null,
          },
        ],
      },
      {
        name: 'utils',
        path: 'src/utils',
        type: 'directory',
        file_id: null,
        language: null,
        children: [
          {
            name: 'helpers.ts',
            path: 'src/utils/helpers.ts',
            type: 'file',
            file_id: 3,
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

describe('FileTree', () => {
  describe('rendering', () => {
    it('should render top-level nodes', () => {
      render(<FileTree nodes={sampleTree} />)

      expect(screen.getByText('src')).toBeInTheDocument()
      expect(screen.getByText('README.md')).toBeInTheDocument()
    })

    it('should show loading spinner when loading', () => {
      render(<FileTree nodes={[]} loading={true} />)

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    it('should show empty message when no files', () => {
      render(<FileTree nodes={[]} />)

      expect(screen.getByText('No files found')).toBeInTheDocument()
    })
  })

  describe('directory expansion', () => {
    it('should expand directory on click', () => {
      render(<FileTree nodes={sampleTree} />)

      // Initially, nested files should not be visible
      expect(screen.queryByText('components')).not.toBeInTheDocument()

      // Click on src directory
      fireEvent.click(screen.getByText('src'))

      // Now components should be visible
      expect(screen.getByText('components')).toBeInTheDocument()
      expect(screen.getByText('utils')).toBeInTheDocument()
      expect(screen.getByText('index.ts')).toBeInTheDocument()
    })

    it('should collapse directory on second click', async () => {
      render(<FileTree nodes={sampleTree} />)

      // Expand
      fireEvent.click(screen.getByText('src'))
      expect(screen.getByText('components')).toBeInTheDocument()

      // Collapse
      fireEvent.click(screen.getByText('src'))

      // Wait for collapse animation and unmount
      await waitFor(
        () => {
          expect(screen.queryByText('components')).not.toBeInTheDocument()
        },
        { timeout: 1000 }
      )
    })
  })

  describe('file selection', () => {
    it('should call onFileSelect when file is clicked', () => {
      const onFileSelect = vi.fn()
      render(<FileTree nodes={sampleTree} onFileSelect={onFileSelect} />)

      // Click on README.md (top-level file)
      fireEvent.click(screen.getByText('README.md'))

      expect(onFileSelect).toHaveBeenCalledWith(5, 'README.md')
    })

    it('should call onFileSelect for nested file', () => {
      const onFileSelect = vi.fn()
      render(<FileTree nodes={sampleTree} onFileSelect={onFileSelect} />)

      // Expand src -> components
      fireEvent.click(screen.getByText('src'))
      fireEvent.click(screen.getByText('components'))

      // Click on Button.tsx
      fireEvent.click(screen.getByText('Button.tsx'))

      expect(onFileSelect).toHaveBeenCalledWith(1, 'src/components/Button.tsx')
    })
  })

  describe('auto-expand on selection', () => {
    it('should auto-expand path to selected file', async () => {
      const { rerender } = render(<FileTree nodes={sampleTree} selectedFileId={null} />)

      // Initially nested file is not visible
      expect(screen.queryByText('Button.tsx')).not.toBeInTheDocument()

      // Set selectedFileId to a nested file
      rerender(<FileTree nodes={sampleTree} selectedFileId={1} />)

      // Wait for useEffect to run
      await waitFor(() => {
        expect(screen.getByText('Button.tsx')).toBeInTheDocument()
      })

      // Parent directories should be expanded
      expect(screen.getByText('src')).toBeInTheDocument()
      expect(screen.getByText('components')).toBeInTheDocument()
    })

    it('should auto-expand when selectedFileId changes to different file', async () => {
      const { rerender } = render(<FileTree nodes={sampleTree} selectedFileId={1} />)

      // Wait for initial expansion
      await waitFor(() => {
        expect(screen.getByText('Button.tsx')).toBeInTheDocument()
      })

      // Change to a file in a different directory
      rerender(<FileTree nodes={sampleTree} selectedFileId={3} />)

      // Wait for new expansion
      await waitFor(() => {
        expect(screen.getByText('helpers.ts')).toBeInTheDocument()
      })

      // utils directory should now be expanded
      expect(screen.getByText('utils')).toBeInTheDocument()
    })
  })

  describe('selected file highlighting', () => {
    it('should highlight selected file', async () => {
      render(<FileTree nodes={sampleTree} selectedFileId={5} />)

      // README.md should have selected class
      const readmeItem = screen.getByText('README.md').closest('div[role="button"]')
      expect(readmeItem).toHaveClass('Mui-selected')
    })
  })
})
