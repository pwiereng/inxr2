import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import History from './History'
import type { CommitInfo } from '@/lib/api'

// getCommits is the only api surface History touches. Mock it so each test
// drives the loading / error / empty / populated branches directly.
vi.mock('@/lib/api', () => ({
  getCommits: vi.fn(),
}))

// Neutralize CodeHeader (pulls repo/branch data from @/lib/api) so these tests
// stay focused on History itself. The stub exposes buttons that invoke each
// callback so we can exercise the navigation handlers.
vi.mock('@/components/CodeHeader', () => ({
  CodeHeader: (props: {
    onRepoChange: (r: string) => void
    onBranchChange: (b: string) => void
    onCommitChange: (c: string) => void
    onTabChange: (t: string) => void
  }) => (
    <div data-testid="code-header">
      <button onClick={() => props.onRepoChange('newrepo')}>hdr-repo</button>
      <button onClick={() => props.onBranchChange('newbranch')}>hdr-branch</button>
      <button onClick={() => props.onCommitChange('abc123')}>hdr-commit</button>
      <button onClick={() => props.onTabChange('browse')}>hdr-browse</button>
      <button onClick={() => props.onTabChange('search')}>hdr-search</button>
      <button onClick={() => props.onTabChange('history')}>hdr-history</button>
      <button onClick={() => props.onTabChange('logical-view')}>hdr-logical</button>
      <button onClick={() => props.onTabChange('dependencies')}>hdr-deps</button>
      <button onClick={() => props.onTabChange('help')}>hdr-help</button>
    </div>
  ),
}))

// Stub the selection toolbar machinery so text-selection side effects don't
// interfere with the render-branch and navigation assertions.
vi.mock('@/hooks/useSelectionToolbar', () => ({
  useSelectionToolbar: () => ({
    toolbar: null,
    containerRef: { current: null },
    handleClose: vi.fn(),
  }),
}))
vi.mock('@/components/SelectionToolbar', () => ({
  SelectionToolbar: () => null,
}))
vi.mock('@/components/CopyButton/CopyButton', () => ({
  CopyButton: () => <button data-testid="copy-button">copy</button>,
}))

import { getCommits } from '@/lib/api'
const mockGetCommits = vi.mocked(getCommits)

function LocationDisplay() {
  const loc = useLocation()
  return <div data-testid="location">{loc.pathname + loc.search}</div>
}

function renderHistory(entry = '/history') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <History />
      <LocationDisplay />
    </MemoryRouter>
  )
}

function makeCommit(overrides: Partial<CommitInfo> = {}): CommitInfo {
  return {
    hash: 'a'.repeat(40),
    short_hash: 'aaaaaaa',
    message: 'Commit summary',
    author_name: 'Alice',
    author_email: 'alice@example.com',
    commit_date: '2026-01-01T00:00:00Z',
    is_indexed: true,
    tags: [],
    is_branch_specific: false,
    is_merge_base: false,
    ...overrides,
  }
}

describe('History', () => {
  beforeEach(() => {
    mockGetCommits.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prompts to select a repository when no repo param is present', () => {
    renderHistory('/history')
    expect(screen.getByText('Select a repository to view commit history')).toBeInTheDocument()
    expect(mockGetCommits).not.toHaveBeenCalled()
  })

  it('shows a loading spinner while commits are being fetched', () => {
    mockGetCommits.mockReturnValue(new Promise(() => {}))
    renderHistory('/history?repo=myrepo')
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('renders the error message when getCommits rejects', async () => {
    mockGetCommits.mockRejectedValue(new Error('boom'))
    renderHistory('/history?repo=myrepo')
    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument())
  })

  it('renders "No commits found" when the repo has no commits', async () => {
    mockGetCommits.mockResolvedValue({ commits: [], total: 0 })
    renderHistory('/history?repo=myrepo')
    await waitFor(() => expect(screen.getByText('No commits found')).toBeInTheDocument())
  })

  it('passes the repo and branch through to getCommits', async () => {
    mockGetCommits.mockResolvedValue({ commits: [], total: 0 })
    renderHistory('/history?repo=myrepo&branch=dev')
    await waitFor(() => expect(mockGetCommits).toHaveBeenCalledWith('myrepo', 'dev', 1000))
  })

  it('renders commit summaries, bodies, and short hashes when populated', async () => {
    mockGetCommits.mockResolvedValue({
      commits: [
        makeCommit({
          hash: 'b'.repeat(40),
          short_hash: 'bbbbbbb',
          message: 'Add feature\n\nDetailed body text.',
        }),
      ],
      total: 1,
    })
    renderHistory('/history?repo=myrepo')

    await waitFor(() => expect(screen.getByText('Add feature')).toBeInTheDocument())
    expect(screen.getByText('Detailed body text.')).toBeInTheDocument()
    expect(screen.getByText('bbbbbbb')).toBeInTheDocument()
  })

  it('scrolls the focused commit into view when the commit param matches a rendered hash', async () => {
    // jsdom does not implement scrollIntoView; stub it so the focus effect runs.
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    const focusedHash = 'e'.repeat(40)
    mockGetCommits.mockResolvedValue({
      commits: [
        makeCommit({ hash: 'f'.repeat(40), short_hash: 'fffffff' }),
        makeCommit({ hash: focusedHash, short_hash: 'eeeeeee', message: 'Focused commit' }),
      ],
      total: 2,
    })
    renderHistory(`/history?repo=myrepo&commit=${focusedHash}`)

    await waitFor(() => expect(screen.getByText('Focused commit')).toBeInTheDocument())
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    )
  })

  it('navigates to the browse view when an indexed commit hash is clicked', async () => {
    const user = userEvent.setup()
    mockGetCommits.mockResolvedValue({
      commits: [makeCommit({ hash: 'c'.repeat(40), short_hash: 'ccccccc', is_indexed: true })],
      total: 1,
    })
    renderHistory('/history?repo=myrepo&branch=main')

    const hashButton = await screen.findByRole('button', { name: 'ccccccc' })
    await user.click(hashButton)

    const location = screen.getByTestId('location')
    expect(location).toHaveTextContent('/browse/myrepo')
    expect(location).toHaveTextContent(`commit=${'c'.repeat(40)}`)
    expect(location).toHaveTextContent('branch=main')
    expect(location).toHaveTextContent('co=1')
  })

  it('renders a non-indexed commit hash as plain text that does not navigate', async () => {
    const user = userEvent.setup()
    mockGetCommits.mockResolvedValue({
      commits: [makeCommit({ hash: 'd'.repeat(40), short_hash: 'ddddddd', is_indexed: false })],
      total: 1,
    })
    renderHistory('/history?repo=myrepo&branch=main')

    await waitFor(() => expect(screen.getByText('(not indexed)')).toBeInTheDocument())
    // The short hash is not rendered as a clickable button.
    expect(screen.queryByRole('button', { name: 'ddddddd' })).not.toBeInTheDocument()

    // Clicking the plain-text hash must not navigate away from /history.
    await user.click(screen.getByText('ddddddd'))
    expect(screen.getByTestId('location')).toHaveTextContent('/history?repo=myrepo&branch=main')
  })

  describe('header navigation handlers', () => {
    beforeEach(() => {
      mockGetCommits.mockResolvedValue({ commits: [], total: 0 })
    })

    it('handleRepoChange sets repo and drops branch/commit', async () => {
      const user = userEvent.setup()
      renderHistory('/history?repo=old&branch=main&commit=deadbeef')
      await user.click(screen.getByText('hdr-repo'))

      const location = screen.getByTestId('location')
      expect(location).toHaveTextContent('/history?repo=newrepo')
      expect(location).not.toHaveTextContent('branch')
    })

    it('handleBranchChange sets branch and drops commit', async () => {
      const user = userEvent.setup()
      renderHistory('/history?repo=myrepo&branch=main&commit=deadbeef')
      await user.click(screen.getByText('hdr-branch'))

      const location = screen.getByTestId('location')
      expect(location).toHaveTextContent('/history?repo=myrepo&branch=newbranch')
      expect(location).not.toHaveTextContent('commit')
    })

    it('handleCommitChange sets commit and keeps repo/branch', async () => {
      const user = userEvent.setup()
      renderHistory('/history?repo=myrepo&branch=main')
      await user.click(screen.getByText('hdr-commit'))

      const location = screen.getByTestId('location')
      expect(location).toHaveTextContent('commit=abc123')
      expect(location).toHaveTextContent('repo=myrepo')
      expect(location).toHaveTextContent('branch=main')
    })

    it('handleTabChange navigates to each destination tab, preserving repo/branch/commit', async () => {
      const user = userEvent.setup()
      const cases: Array<[string, string]> = [
        ['hdr-browse', '/browse/myrepo'],
        ['hdr-search', '/search'],
        ['hdr-logical', '/logical-view'],
        ['hdr-deps', '/dependencies'],
        ['hdr-help', '/help'],
      ]
      for (const [button, path] of cases) {
        const { unmount } = renderHistory('/history?repo=myrepo&branch=main&commit=deadbeef')
        await user.click(screen.getByText(button))
        const location = screen.getByTestId('location')
        expect(location).toHaveTextContent(path)
        // handleTabChange threads repo/branch/commit into the destination query;
        // assert they survive so a regression dropping `?${params}` is caught
        // (a bare '/search' would otherwise still match the path substring).
        expect(location).toHaveTextContent('repo=myrepo')
        expect(location).toHaveTextContent('branch=main')
        expect(location).toHaveTextContent('commit=deadbeef')
        unmount()
      }
    })

    it('handleTabChange → history stays on the history page', async () => {
      const user = userEvent.setup()
      renderHistory('/history?repo=myrepo&branch=main')
      await user.click(screen.getByText('hdr-history'))
      expect(screen.getByTestId('location')).toHaveTextContent('/history?repo=myrepo&branch=main')
    })
  })
})
