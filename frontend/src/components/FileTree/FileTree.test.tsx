import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/utils'
import userEvent from '@testing-library/user-event'
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
    size_bytes: null,
    line_count: null,

    children: [
      {
        name: 'components',
        path: 'src/components',
        type: 'directory',
        file_id: null,
        language: null,
        size_bytes: null,
        line_count: null,

        children: [
          {
            name: 'Button.tsx',
            path: 'src/components/Button.tsx',
            type: 'file',
            file_id: 1,
            language: 'typescript',
            size_bytes: null,
            line_count: null,

            children: null,
          },
          {
            name: 'Input.tsx',
            path: 'src/components/Input.tsx',
            type: 'file',
            file_id: 2,
            language: 'typescript',
            size_bytes: null,
            line_count: null,

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
        size_bytes: null,
        line_count: null,

        children: [
          {
            name: 'helpers.ts',
            path: 'src/utils/helpers.ts',
            type: 'file',
            file_id: 3,
            language: 'typescript',
            size_bytes: null,
            line_count: null,

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
        size_bytes: null,
        line_count: null,

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
    size_bytes: null,
    line_count: null,

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

      expect(onFileSelect).toHaveBeenCalledWith('README.md')
    })

    it('should call onFileSelect for nested file', () => {
      const onFileSelect = vi.fn()
      render(<FileTree nodes={sampleTree} onFileSelect={onFileSelect} />)

      // Expand src -> components
      fireEvent.click(screen.getByText('src'))
      fireEvent.click(screen.getByText('components'))

      // Click on Button.tsx
      fireEvent.click(screen.getByText('Button.tsx'))

      expect(onFileSelect).toHaveBeenCalledWith('src/components/Button.tsx')
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

  describe('chevron vs. directory row (#572)', () => {
    it('chevron click toggles expansion without selecting the directory', async () => {
      const onDirectorySelect = vi.fn()
      render(<FileTree nodes={sampleTree} onDirectorySelect={onDirectorySelect} />)

      fireEvent.click(screen.getByRole('button', { name: 'Expand src' }))
      expect(screen.getByText('components')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Collapse src' }))
      await waitFor(() => {
        expect(screen.queryByText('components')).not.toBeInTheDocument()
      })

      expect(onDirectorySelect).not.toHaveBeenCalled()
    })

    it('name click selects the directory and expands it', () => {
      const onDirectorySelect = vi.fn()
      render(<FileTree nodes={sampleTree} onDirectorySelect={onDirectorySelect} />)

      fireEvent.click(screen.getByText('src'))

      expect(onDirectorySelect).toHaveBeenCalledWith('src')
      expect(screen.getByText('components')).toBeInTheDocument()
    })

    it('folder icon click selects the directory', () => {
      const onDirectorySelect = vi.fn()
      render(<FileTree nodes={sampleTree} onDirectorySelect={onDirectorySelect} />)

      fireEvent.click(screen.getByTestId('FolderIcon'))

      expect(onDirectorySelect).toHaveBeenCalledWith('src')
    })

    it('name click on an expanded directory collapses it even as it becomes selected', async () => {
      const onDirectorySelect = vi.fn()
      const { rerender } = render(
        <FileTree nodes={sampleTree} onDirectorySelect={onDirectorySelect} />
      )

      fireEvent.click(screen.getByRole('button', { name: 'Expand src' }))
      expect(screen.getByText('components')).toBeInTheDocument()

      fireEvent.click(screen.getByText('src'))
      expect(onDirectorySelect).toHaveBeenCalledWith('src')
      // The parent navigates in response; the auto-expand for the new
      // selectedDirectoryPath must not undo the collapse the click asked for.
      rerender(
        <FileTree
          nodes={sampleTree}
          selectedDirectoryPath="src"
          onDirectorySelect={onDirectorySelect}
        />
      )

      await waitFor(() => {
        expect(screen.queryByText('components')).not.toBeInTheDocument()
      })
    })

    it('name click on the already-selected, expanded directory collapses it without re-selecting', async () => {
      const onDirectorySelect = vi.fn()
      render(
        <FileTree
          nodes={sampleTree}
          selectedDirectoryPath="src"
          onDirectorySelect={onDirectorySelect}
        />
      )
      await waitFor(() => {
        expect(screen.getByText('components')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('src'))

      await waitFor(() => {
        expect(screen.queryByText('components')).not.toBeInTheDocument()
      })
      expect(onDirectorySelect).not.toHaveBeenCalled()
    })

    it('files have no chevron and still call onFileSelect', () => {
      const onFileSelect = vi.fn()
      const onDirectorySelect = vi.fn()
      render(
        <FileTree
          nodes={sampleTree}
          onFileSelect={onFileSelect}
          onDirectorySelect={onDirectorySelect}
        />
      )

      expect(screen.queryByRole('button', { name: 'Expand README.md' })).not.toBeInTheDocument()

      fireEvent.click(screen.getByText('README.md'))
      expect(onFileSelect).toHaveBeenCalledWith('README.md')
      expect(onDirectorySelect).not.toHaveBeenCalled()
    })

    it('chevron is a focusable button exposing aria-expanded and toggles from the keyboard', async () => {
      const user = userEvent.setup()
      const onDirectorySelect = vi.fn()
      render(<FileTree nodes={sampleTree} onDirectorySelect={onDirectorySelect} />)

      const chevron = screen.getByRole('button', { name: 'Expand src' })
      expect(chevron.tagName).toBe('BUTTON')
      expect(chevron).toHaveAttribute('aria-expanded', 'false')

      chevron.focus()
      expect(chevron).toHaveFocus()
      await user.keyboard('{Enter}')

      const collapse = screen.getByRole('button', { name: 'Collapse src' })
      expect(collapse).toHaveAttribute('aria-expanded', 'true')
      expect(screen.getByText('components')).toBeInTheDocument()

      await user.keyboard(' ')
      expect(screen.getByRole('button', { name: 'Expand src' })).toHaveAttribute(
        'aria-expanded',
        'false'
      )
      expect(onDirectorySelect).not.toHaveBeenCalled()
    })
  })

  describe('selected directory highlighting', () => {
    it('highlights the row of the directory shown in the main pane', async () => {
      render(<FileTree nodes={sampleTree} selectedDirectoryPath="src/utils" />)

      await waitFor(() => {
        expect(screen.getByText('utils')).toBeInTheDocument()
      })
      expect(screen.getByText('utils').closest('div[role="button"]')).toHaveClass('Mui-selected')
      expect(screen.getByText('src').closest('div[role="button"]')).not.toHaveClass('Mui-selected')
    })
  })

  describe('file tree filter', () => {
    it('should show filter input when tree has nodes', () => {
      render(<FileTree nodes={sampleTree} />)
      expect(screen.getByLabelText('Filter files')).toBeInTheDocument()
    })

    it('should not show filter input when loading', () => {
      render(<FileTree nodes={[]} loading={true} />)
      expect(screen.queryByLabelText('Filter files')).not.toBeInTheDocument()
    })

    it('should not show filter input when tree is empty', () => {
      render(<FileTree nodes={[]} />)
      expect(screen.queryByLabelText('Filter files')).not.toBeInTheDocument()
    })

    it('should hide tree and show results when typing in filter', () => {
      render(<FileTree nodes={sampleTree} />)

      // Tree nodes visible initially
      expect(screen.getByText('src')).toBeInTheDocument()
      expect(screen.getByText('README.md')).toBeInTheDocument()

      // Type in filter
      fireEvent.change(screen.getByLabelText('Filter files'), { target: { value: 'Button' } })

      // Filter results should appear (path shown in results)
      expect(screen.getByText('src/components/Button.tsx')).toBeInTheDocument()

      // Tree nodes should be hidden (src as a tree node is gone, only filter results remain)
      // The tree List is unmounted when filtering, so the tree-rendered "src" is removed
      // But "src" might still appear as part of the path in results — check that the
      // tree-specific expand/collapse behavior is gone
      expect(screen.queryByText('utils')).not.toBeInTheDocument()
    })

    it('should call onFileSelect when selecting a file from filter results', () => {
      const onFileSelect = vi.fn()
      render(<FileTree nodes={sampleTree} onFileSelect={onFileSelect} />)

      // Type in filter
      fireEvent.change(screen.getByLabelText('Filter files'), { target: { value: 'Button' } })

      // Click on the result (click the path secondary text)
      fireEvent.click(screen.getByText('src/components/Button.tsx'))

      expect(onFileSelect).toHaveBeenCalledWith('src/components/Button.tsx')
    })

    it('should clear filter and restore tree after selecting a result', () => {
      const onFileSelect = vi.fn()
      render(<FileTree nodes={sampleTree} onFileSelect={onFileSelect} />)

      // Type in filter
      fireEvent.change(screen.getByLabelText('Filter files'), { target: { value: 'Button' } })

      // Click on the result
      fireEvent.click(screen.getByText('src/components/Button.tsx'))

      // Filter should be cleared
      expect(screen.getByLabelText('Filter files')).toHaveValue('')

      // Tree should be visible again
      expect(screen.getByText('src')).toBeInTheDocument()
      expect(screen.getByText('README.md')).toBeInTheDocument()
    })
  })
})
