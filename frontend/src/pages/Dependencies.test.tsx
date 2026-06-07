import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import Dependencies from './Dependencies'
import type { TabValue } from '@/components/CodeHeader'
import type { DependencyItem, DependenciesListResponse } from '@/lib/api'

// Mock the API client — api.ts is frozen, so we only stub the one fn this page uses.
vi.mock('@/lib/api', () => ({
  getRepositoryDependencies: vi.fn(),
}))

// Neutralize CodeHeader (pulls repo/branch data from the API) but expose buttons
// that invoke each callback, so the page's navigation handlers are exercised.
vi.mock('@/components/CodeHeader', () => ({
  CodeHeader: (props: {
    onRepoChange: (r: string) => void
    onBranchChange: (b: string) => void
    onCommitChange: (c: string) => void
    onTabChange: (t: TabValue) => void
  }) => (
    <div data-testid="code-header">
      <button onClick={() => props.onRepoChange('newrepo')}>repo</button>
      <button onClick={() => props.onBranchChange('newbranch')}>branch</button>
      <button onClick={() => props.onCommitChange('abc123')}>commit</button>
      <button onClick={() => props.onTabChange('browse')}>tab-browse</button>
      <button onClick={() => props.onTabChange('search')}>tab-search</button>
      <button onClick={() => props.onTabChange('history')}>tab-history</button>
      <button onClick={() => props.onTabChange('logical-view')}>tab-logical</button>
      <button onClick={() => props.onTabChange('dependencies')}>tab-deps</button>
      <button onClick={() => props.onTabChange('help')}>tab-help</button>
    </div>
  ),
}))

// Stub SelectionToolbar so its portal/clipboard wiring stays out of the way.
vi.mock('@/components/SelectionToolbar', () => ({
  SelectionToolbar: () => <div data-testid="selection-toolbar" />,
}))

import { getRepositoryDependencies } from '@/lib/api'

function LocationDisplay() {
  const loc = useLocation()
  return <div data-testid="location">{loc.pathname + loc.search}</div>
}

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
      <LocationDisplay />
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
          version_spec: null,
          resolved_version: '2.0.0',
          file_id: 10,
          file_path: 'requirements.txt',
        }),
        makeItem({
          id: 2,
          package_name: 'requests',
          version_spec: null,
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

    // The package collapses to a single "2 versions" node...
    const versionsChip = await screen.findByText('2 versions')
    expect(versionsChip).toBeInTheDocument()

    // ...whose detail rows show each version (toggling the node exercises its handler).
    await user.click(versionsChip)
    await waitFor(() => expect(screen.getByText('2.0.0')).toBeInTheDocument())
    expect(screen.getByText('2.31.0')).toBeInTheDocument()
  })

  describe('navigation handlers', () => {
    beforeEach(() => {
      // Resolve so the page mounts past its loading branch for header-driven nav.
      vi.mocked(getRepositoryDependencies).mockResolvedValue(makeResponse([]))
    })

    it('handleRepoChange sets repo and drops branch/commit', async () => {
      const user = userEvent.setup()
      renderDeps('/dependencies?repo=old&branch=main&commit=deadbeef')

      await user.click(screen.getByText('repo'))

      expect(screen.getByTestId('location')).toHaveTextContent('/dependencies?repo=newrepo')
      expect(screen.getByTestId('location')).not.toHaveTextContent('branch')
    })

    it('handleBranchChange sets branch and drops commit', async () => {
      const user = userEvent.setup()
      renderDeps('/dependencies?repo=myrepo&branch=main&commit=deadbeef')

      await user.click(screen.getByText('branch'))

      expect(screen.getByTestId('location')).toHaveTextContent('branch=newbranch')
      expect(screen.getByTestId('location')).not.toHaveTextContent('commit')
    })

    it('handleCommitChange sets commit and keeps repo/branch', async () => {
      const user = userEvent.setup()
      renderDeps('/dependencies?repo=myrepo&branch=main')

      await user.click(screen.getByText('commit'))

      expect(screen.getByTestId('location')).toHaveTextContent('commit=abc123')
      expect(screen.getByTestId('location')).toHaveTextContent('repo=myrepo')
    })

    it('handleTabChange → browse navigates to the repo browse path when repo is set', async () => {
      const user = userEvent.setup()
      renderDeps('/dependencies?repo=myrepo&branch=main&commit=deadbeef')

      await user.click(screen.getByText('tab-browse'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/browse/myrepo')
      expect(loc).toHaveTextContent('repo=myrepo')
    })

    it('handleTabChange → browse navigates home when no repo is set', async () => {
      const user = userEvent.setup()
      renderDeps('/dependencies')

      await user.click(screen.getByText('tab-browse'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/')
      expect(loc).not.toHaveTextContent('browse')
    })

    it('handleTabChange preserves repo/branch/commit into search/history/logical/deps/help', async () => {
      const user = userEvent.setup()
      const cases: Array<[string, string]> = [
        ['tab-search', '/search'],
        ['tab-history', '/history'],
        ['tab-logical', '/logical-view'],
        ['tab-deps', '/dependencies'],
        ['tab-help', '/help'],
      ]
      for (const [button, path] of cases) {
        const { unmount } = renderDeps('/dependencies?repo=myrepo&branch=main&commit=deadbeef')
        await user.click(screen.getByText(button))
        const loc = screen.getByTestId('location')
        expect(loc).toHaveTextContent(path)
        expect(loc).toHaveTextContent('repo=myrepo')
        expect(loc).toHaveTextContent('branch=main')
        expect(loc).toHaveTextContent('commit=deadbeef')
        unmount()
      }
    })
  })

  describe('list navigation', () => {
    it('clicking a file name navigates to its encoded browse path, preserving branch', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([
          makeItem({ id: 1, package_name: 'requests', file_id: 10, file_path: 'requirements.txt' }),
        ])
      )
      renderDeps('/dependencies?repo=myrepo&branch=main')

      await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
      await user.click(screen.getByText('requirements.txt'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/browse/myrepo/requirements.txt')
      expect(loc).toHaveTextContent('branch=main')
    })

    it('clicking "search usages" navigates to a dependency search for the package', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([
          makeItem({ id: 1, package_name: 'requests', file_id: 10, file_path: 'requirements.txt' }),
        ])
      )
      renderDeps('/dependencies?repo=myrepo&branch=main')

      await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
      // Expand the group (via the language chip), then click the row's search button.
      await user.click(screen.getByText('python'))
      await user.click(await screen.findByRole('button', { name: /search usages of requests/i }))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/search')
      expect(loc).toHaveTextContent('query=requests')
      expect(loc).toHaveTextContent('types=dependency')
      expect(loc).toHaveTextContent('repo=myrepo')
    })

    it('clicking a file name carries both branch and commit into the browse path', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([
          makeItem({
            id: 1,
            package_name: 'requests',
            file_id: 10,
            file_path: 'src/requirements.txt',
          }),
        ])
      )
      renderDeps('/dependencies?repo=myrepo&branch=main&commit=deadbeef')

      await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
      // Each path segment is encoded; the slash between dir and file is preserved.
      await user.click(screen.getByText('requirements.txt'))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/browse/myrepo/src/requirements.txt')
      expect(loc).toHaveTextContent('branch=main')
      expect(loc).toHaveTextContent('commit=deadbeef')
    })

    it('search usages from a row carries the branch param', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([
          makeItem({ id: 1, package_name: 'requests', file_id: 10, file_path: 'requirements.txt' }),
        ])
      )
      renderDeps('/dependencies?repo=myrepo&branch=feature')

      await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
      await user.click(screen.getByText('python'))
      await user.click(await screen.findByRole('button', { name: /search usages of requests/i }))

      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/search')
      expect(loc).toHaveTextContent('query=requests')
      expect(loc).toHaveTextContent('branch=feature')
    })
  })

  describe('filter chips and toggles', () => {
    function twoTypeResponse() {
      return makeResponse([
        makeItem({
          id: 1,
          package_name: 'requests',
          dependency_type: 'runtime',
          is_direct: true,
          file_id: 10,
          file_path: 'requirements.txt',
        }),
        makeItem({
          id: 2,
          package_name: 'pytest',
          dependency_type: 'dev',
          is_direct: false,
          file_id: 10,
          file_path: 'requirements.txt',
        }),
      ])
    }

    it('narrows by a type chip, toggles it off, and resets via the Type "All" chip', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(twoTypeResponse())
      renderDeps()

      await waitFor(() => expect(screen.getByText(/2 packages in 1 files/i)).toBeInTheDocument())
      // Only one language here, so the only "All" chips are Type then Scope.
      const typeAll = () => screen.getAllByRole('button', { name: 'All' })[0] as HTMLElement

      // Select the "dev" type chip → only the dev dependency remains.
      await user.click(screen.getByRole('button', { name: 'dev' }))
      await waitFor(() => expect(screen.getByText(/1 packages in 1 files/i)).toBeInTheDocument())

      // Toggling the same chip again clears the filter → back to both.
      await user.click(screen.getByRole('button', { name: 'dev' }))
      await waitFor(() => expect(screen.getByText(/2 packages in 1 files/i)).toBeInTheDocument())

      // Re-select "dev", then reset with the Type "All" chip.
      await user.click(screen.getByRole('button', { name: 'dev' }))
      await waitFor(() => expect(screen.getByText(/1 packages in 1 files/i)).toBeInTheDocument())
      await user.click(typeAll())
      await waitFor(() => expect(screen.getByText(/2 packages in 1 files/i)).toBeInTheDocument())
    })

    it('narrows to direct dependencies via the Scope chip and resets by re-clicking', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(twoTypeResponse())
      renderDeps()

      await waitFor(() => expect(screen.getByText(/2 packages in 1 files/i)).toBeInTheDocument())

      // Direct (1) → only the direct dependency remains. The label count reflects
      // the currently filtered list, so it stays "Direct (1)" once applied.
      await user.click(screen.getByRole('button', { name: /Direct \(1\)/i }))
      await waitFor(() => expect(screen.getByText(/1 packages in 1 files/i)).toBeInTheDocument())
      expect(screen.getByText('requests')).toBeInTheDocument()
      expect(screen.queryByText('pytest')).not.toBeInTheDocument()

      // Toggling Direct again clears scope → both reappear (count returns to 2).
      await user.click(screen.getByRole('button', { name: /Direct \(1\)/i }))
      await waitFor(() => expect(screen.getByText(/2 packages in 1 files/i)).toBeInTheDocument())
    })

    it('narrows to transitive dependencies via the Scope chip and resets via Scope "All"', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(twoTypeResponse())
      renderDeps()

      await waitFor(() => expect(screen.getByText(/2 packages in 1 files/i)).toBeInTheDocument())
      const scopeAll = () => screen.getAllByRole('button', { name: 'All' })[1] as HTMLElement

      // Transitive (1) → only the transitive dependency remains.
      await user.click(screen.getByRole('button', { name: /Transitive \(1\)/i }))
      await waitFor(() => expect(screen.getByText(/1 packages in 1 files/i)).toBeInTheDocument())
      expect(screen.getByText('pytest')).toBeInTheDocument()
      expect(screen.queryByText('requests')).not.toBeInTheDocument()

      // Re-clicking Transitive clears the scope.
      await user.click(screen.getByRole('button', { name: /Transitive \(1\)/i }))
      await waitFor(() => expect(screen.getByText(/2 packages in 1 files/i)).toBeInTheDocument())

      // Select Transitive again, then reset with the Scope "All" chip.
      await user.click(screen.getByRole('button', { name: /Transitive \(1\)/i }))
      await waitFor(() => expect(screen.getByText(/1 packages in 1 files/i)).toBeInTheDocument())
      await user.click(scopeAll())
      await waitFor(() => expect(screen.getByText(/2 packages in 1 files/i)).toBeInTheDocument())
    })

    it('shows the indexed commit hash in the summary', async () => {
      vi.mocked(getRepositoryDependencies).mockResolvedValue({
        ...makeResponse([makeItem()]),
        commit_hash: 'abcdef1234567890',
      })
      renderDeps()

      await waitFor(() => expect(screen.getByText('abcdef1')).toBeInTheDocument())
    })
  })

  describe('group rendering edge cases', () => {
    it('falls back to a "(file #id)" label and disables navigation when file_path is missing', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([makeItem({ id: 1, package_name: 'requests', file_id: 99, file_path: null })])
      )
      renderDeps('/dependencies?repo=myrepo&branch=main')

      await waitFor(() => expect(screen.getByText('(file #99)')).toBeInTheDocument())

      // The fallback label is not a navigation target — clicking it does nothing.
      await user.click(screen.getByText('(file #99)'))
      const loc = screen.getByTestId('location')
      expect(loc).toHaveTextContent('/dependencies')
      expect(loc).not.toHaveTextContent('/browse')
    })

    it('collapses an expanded file group when toggled again', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([
          makeItem({ id: 1, package_name: 'requests', file_id: 10, file_path: 'requirements.txt' }),
        ])
      )
      renderDeps()

      await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())

      // Expand via the language chip → the search button appears.
      await user.click(screen.getByText('python'))
      await waitFor(() =>
        expect(
          screen.getByRole('button', { name: /search usages of requests/i })
        ).toBeInTheDocument()
      )

      // Collapse via the same chip → the search button is removed.
      await user.click(screen.getByText('python'))
      await waitFor(() =>
        expect(
          screen.queryByRole('button', { name: /search usages of requests/i })
        ).not.toBeInTheDocument()
      )
    })

    it('collapses an expanded multi-version package group when toggled again', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([
          makeItem({
            id: 1,
            package_name: 'requests',
            version_spec: null,
            resolved_version: '2.0.0',
            file_id: 10,
            file_path: 'requirements.txt',
          }),
          makeItem({
            id: 2,
            package_name: 'requests',
            version_spec: null,
            resolved_version: '2.31.0',
            file_id: 10,
            file_path: 'requirements.txt',
          }),
        ])
      )
      renderDeps()

      await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
      await user.click(screen.getByText('python'))

      const versionsChip = await screen.findByText('2 versions')
      // Expand the package group → both version rows are listed and, with both the
      // file and package groups open, no collapsed (ChevronRight) chevrons remain.
      await user.click(versionsChip)
      await waitFor(() => expect(screen.getByText('2.0.0')).toBeInTheDocument())
      expect(screen.queryByTestId('ChevronRightIcon')).not.toBeInTheDocument()

      // Collapse it again (exercises togglePackage's delete path) → the package
      // group's chevron flips back to ChevronRight.
      await user.click(versionsChip)
      await waitFor(() => expect(screen.getByTestId('ChevronRightIcon')).toBeInTheDocument())
    })

    it('renders a single-version row using resolved_version and a transitive badge', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([
          makeItem({
            id: 1,
            package_name: 'requests',
            version_spec: null,
            resolved_version: '2.31.0',
            is_direct: false,
            file_id: 10,
            file_path: 'requirements.txt',
          }),
        ])
      )
      renderDeps()

      await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
      await user.click(screen.getByText('python'))

      // version_spec is null → the row falls back to resolved_version.
      await waitFor(() => expect(screen.getByText('2.31.0')).toBeInTheDocument())
      // is_direct false → the row carries a "transitive" badge.
      expect(screen.getByText('transitive')).toBeInTheDocument()
    })

    it('shows "(no version)" and a transitive badge for version rows lacking any version', async () => {
      const user = userEvent.setup()
      vi.mocked(getRepositoryDependencies).mockResolvedValue(
        makeResponse([
          makeItem({
            id: 1,
            package_name: 'requests',
            version_spec: null,
            resolved_version: null,
            is_direct: false,
            file_id: 10,
            file_path: 'requirements.txt',
          }),
          makeItem({
            id: 2,
            package_name: 'requests',
            version_spec: null,
            resolved_version: '2.31.0',
            is_direct: true,
            file_id: 10,
            file_path: 'requirements.txt',
          }),
        ])
      )
      renderDeps()

      await waitFor(() => expect(screen.getByText('requirements.txt')).toBeInTheDocument())
      await user.click(screen.getByText('python'))
      await user.click(await screen.findByText('2 versions'))

      // The version-less item renders the "(no version)" placeholder.
      await waitFor(() => expect(screen.getByText('(no version)')).toBeInTheDocument())
      // is_direct false → that version row carries a "transitive" badge.
      expect(screen.getByText('transitive')).toBeInTheDocument()
    })
  })

  it('falls back to a generic message when the API rejects with a non-Error', async () => {
    vi.mocked(getRepositoryDependencies).mockRejectedValue('plain string failure')
    renderDeps()
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/failed to load dependencies/i)
    )
  })
})
