import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Dependencies from './Dependencies'
import type { DependencyItem, DependenciesListResponse } from '@/lib/api'

// Mock the API client — api.ts is frozen, so we only stub the one fn this page uses.
vi.mock('@/lib/api', () => ({
  getRepositoryDependencies: vi.fn(),
}))

// Neutralize CodeHeader (pulls repo/branch data from the API) to stay focused.
vi.mock('@/components/CodeHeader', () => ({
  CodeHeader: () => <div data-testid="code-header" />,
}))

// Stub SelectionToolbar so its portal/clipboard wiring stays out of the way.
vi.mock('@/components/SelectionToolbar', () => ({
  SelectionToolbar: () => <div data-testid="selection-toolbar" />,
}))

import { getRepositoryDependencies } from '@/lib/api'

function makeItem(overrides: Partial<DependencyItem> = {}): DependencyItem {
  return {
    id: 1,
    package_name: 'requests',
    language: 'python',
    version_spec: '>=2.0',
    resolved_version: '2.31.0',
    dependency_type: 'runtime',
    is_direct: true,
    file_id: 10,
    file_path: 'requirements.txt',
    source_line: 1,
    ...overrides,
  }
}

function makeResponse(items: DependencyItem[]): DependenciesListResponse {
  return {
    repository_id: 1,
    repository_name: 'myrepo',
    commit_hash: 'abcdef1234567890',
    items,
    total: items.length,
  }
}

function renderDeps(entry = '/dependencies?repo=myrepo') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Dependencies />
    </MemoryRouter>
  )
}

describe('Dependencies', () => {
  beforeEach(() => {
    vi.mocked(getRepositoryDependencies).mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prompts to select a repository when none is set', () => {
    renderDeps('/dependencies')
    expect(screen.getByText(/select a repository/i)).toBeInTheDocument()
    expect(getRepositoryDependencies).not.toHaveBeenCalled()
  })

  it('shows a loading spinner while dependencies resolve', () => {
    vi.mocked(getRepositoryDependencies).mockReturnValue(new Promise(() => {}))
    renderDeps()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('shows an error state when the API rejects', async () => {
    vi.mocked(getRepositoryDependencies).mockRejectedValue(new Error('boom'))
    renderDeps()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('boom'))
  })

  it('shows an empty state when the repository has no dependencies', async () => {
    vi.mocked(getRepositoryDependencies).mockResolvedValue(makeResponse([]))
    renderDeps()
    await waitFor(() => expect(screen.getByText(/no dependencies found/i)).toBeInTheDocument())
  })

  it('renders dependency file groups and the summary count', async () => {
    vi.mocked(getRepositoryDependencies).mockResolvedValue(
      makeResponse([
        makeItem({ id: 1, package_name: 'requests', file_id: 10, file_path: 'requirements.txt' }),
        makeItem({
          id: 2,
          package_name: 'lodash',
          language: 'javascript',
          file_id: 20,
          file_path: 'package.json',
        }),
      ])
    )
    renderDeps()

    await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
    expect(screen.getByText('package.json')).toBeInTheDocument()
    expect(screen.getByText(/2 packages in 2 files/i)).toBeInTheDocument()
  })

  it('narrows the list when a language filter chip is selected', async () => {
    const user = userEvent.setup()
    vi.mocked(getRepositoryDependencies).mockResolvedValue(
      makeResponse([
        makeItem({
          id: 1,
          package_name: 'requests',
          language: 'python',
          file_id: 10,
          file_path: 'requirements.txt',
        }),
        makeItem({
          id: 2,
          package_name: 'lodash',
          language: 'javascript',
          file_id: 20,
          file_path: 'package.json',
        }),
      ])
    )
    renderDeps()

    await waitFor(() => expect(screen.getByText(/2 packages in 2 files/i)).toBeInTheDocument())

    // Pick the JavaScript language chip → only package.json remains.
    await user.click(screen.getByRole('button', { name: 'javascript' }))

    await waitFor(() => expect(screen.getByText(/1 packages in 1 files/i)).toBeInTheDocument())
    expect(screen.queryByText('requirements.txt')).not.toBeInTheDocument()
    expect(screen.getByText('package.json')).toBeInTheDocument()
  })

  it('narrows the list with the free-text filter', async () => {
    const user = userEvent.setup()
    vi.mocked(getRepositoryDependencies).mockResolvedValue(
      makeResponse([
        makeItem({ id: 1, package_name: 'requests', file_id: 10, file_path: 'requirements.txt' }),
        makeItem({ id: 2, package_name: 'lodash', file_id: 20, file_path: 'package.json' }),
      ])
    )
    renderDeps()

    await waitFor(() => expect(screen.getByText(/2 packages in 2 files/i)).toBeInTheDocument())
    await user.type(screen.getByPlaceholderText(/filter packages/i), 'lodash')

    await waitFor(() => expect(screen.getByText(/1 packages in 1 files/i)).toBeInTheDocument())
    expect(screen.queryByText('requirements.txt')).not.toBeInTheDocument()
  })

  it('expands a file group to reveal its dependency rows', async () => {
    const user = userEvent.setup()
    vi.mocked(getRepositoryDependencies).mockResolvedValue(
      makeResponse([
        makeItem({ id: 1, package_name: 'requests', file_id: 10, file_path: 'requirements.txt' }),
      ])
    )
    renderDeps()

    await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
    // Click the row's language chip (not the filename, which navigates to Browse).
    await user.click(screen.getByText('python'))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /search usages of requests/i })).toBeInTheDocument()
    )
  })

  it('groups multiple versions of one package under an expandable node', async () => {
    const user = userEvent.setup()
    vi.mocked(getRepositoryDependencies).mockResolvedValue(
      makeResponse([
        makeItem({
          id: 1,
          package_name: 'requests',
          resolved_version: '2.0.0',
          file_id: 10,
          file_path: 'requirements.txt',
        }),
        makeItem({
          id: 2,
          package_name: 'requests',
          resolved_version: '2.31.0',
          file_id: 10,
          file_path: 'requirements.txt',
        }),
      ])
    )
    renderDeps()

    await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
    // Click the row's language chip to expand the group.
    await user.click(screen.getByText('python'))

    const versionsChip = await screen.findByText('2 versions')
    expect(versionsChip).toBeInTheDocument()
  })
})
