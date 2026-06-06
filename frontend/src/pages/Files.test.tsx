import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Files from './Files'
import * as api from '@/lib/api'
import type { FileInfo } from '@/lib/api'
import { AppProvider } from '@/contexts/AppContext'

vi.mock('@/lib/api', () => ({
  getRepositoryFiles: vi.fn(),
}))

const mockFiles: FileInfo[] = [
  {
    id: 1,
    repository_id: 1,
    commit_id: 1,
    path: 'src/main.py',
    language: 'python',
    size_bytes: 1024,
    line_count: 42,
  },
  {
    id: 2,
    repository_id: 1,
    commit_id: 1,
    path: 'src/app.ts',
    language: 'typescript',
    size_bytes: 2048,
    line_count: 88,
  },
]

function renderFiles() {
  return render(
    <MemoryRouter initialEntries={['/repositories/1/files']}>
      <AppProvider>
        <Routes>
          <Route path="/repositories/:repositoryId/files" element={<Files />} />
        </Routes>
      </AppProvider>
    </MemoryRouter>
  )
}

describe('Files', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner initially', async () => {
    vi.mocked(api.getRepositoryFiles).mockReturnValue(new Promise(() => {}))
    renderFiles()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('calls getRepositoryFiles with the numeric repository id', async () => {
    vi.mocked(api.getRepositoryFiles).mockResolvedValue(mockFiles)
    renderFiles()
    await waitFor(() => expect(api.getRepositoryFiles).toHaveBeenCalledWith(1))
  })

  it('renders files after load', async () => {
    vi.mocked(api.getRepositoryFiles).mockResolvedValue(mockFiles)
    renderFiles()

    await waitFor(() => expect(screen.getByText('src/main.py')).toBeInTheDocument())
    expect(screen.getByText('src/app.ts')).toBeInTheDocument()
    expect(screen.getByText('2 files')).toBeInTheDocument()
  })

  it('shows empty state when no files', async () => {
    vi.mocked(api.getRepositoryFiles).mockResolvedValue([])
    renderFiles()

    await waitFor(() => expect(screen.getByText('No files found')).toBeInTheDocument())
  })

  it('shows error state on API failure', async () => {
    vi.mocked(api.getRepositoryFiles).mockRejectedValue(new Error('Failed to fetch files'))
    renderFiles()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText(/Failed to fetch files/)).toBeInTheDocument()
  })

  it('filters files by search term', async () => {
    vi.mocked(api.getRepositoryFiles).mockResolvedValue(mockFiles)
    const user = userEvent.setup()
    renderFiles()

    await waitFor(() => expect(screen.getByText('src/main.py')).toBeInTheDocument())

    await user.type(screen.getByLabelText('Search files'), 'app')

    await waitFor(() => expect(screen.queryByText('src/main.py')).not.toBeInTheDocument())
    expect(screen.getByText('src/app.ts')).toBeInTheDocument()
    expect(screen.getByText('1 file matching "app"')).toBeInTheDocument()
  })

  it('filters files when a language is selected from the dropdown', async () => {
    vi.mocked(api.getRepositoryFiles).mockResolvedValue(mockFiles)
    const user = userEvent.setup()
    renderFiles()

    await waitFor(() => expect(screen.getByText('src/main.py')).toBeInTheDocument())

    // Open the Language Select and pick "typescript"
    await user.click(screen.getByRole('combobox'))
    await user.click(screen.getByRole('option', { name: 'typescript' }))

    await waitFor(() => expect(screen.queryByText('src/main.py')).not.toBeInTheDocument())
    expect(screen.getByText('src/app.ts')).toBeInTheDocument()
    expect(screen.getByText('1 file')).toBeInTheDocument()
  })

  it('shows no-match message when filters exclude everything', async () => {
    vi.mocked(api.getRepositoryFiles).mockResolvedValue(mockFiles)
    const user = userEvent.setup()
    renderFiles()

    await waitFor(() => expect(screen.getByText('src/main.py')).toBeInTheDocument())

    await user.type(screen.getByLabelText('Search files'), 'zzz')

    await waitFor(() => expect(screen.getByText('No files match your filters')).toBeInTheDocument())
  })

  it('does not fetch when repositoryId is missing', async () => {
    vi.mocked(api.getRepositoryFiles).mockResolvedValue(mockFiles)
    render(
      <MemoryRouter initialEntries={['/files']}>
        <AppProvider>
          <Routes>
            <Route path="/files" element={<Files />} />
          </Routes>
        </AppProvider>
      </MemoryRouter>
    )
    await act(async () => {
      await Promise.resolve()
    })
    expect(api.getRepositoryFiles).not.toHaveBeenCalled()
  })
})
