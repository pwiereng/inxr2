import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import Help from './Help'
import type { TabValue } from '@/components/CodeHeader'

// Neutralize CodeHeader (pulls repo/branch data from @/lib/api) so these tests
// stay focused on Help itself. The stub exposes buttons that invoke each
// callback so we can exercise the navigation handlers.
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

// Stub MarkdownViewer so we can assert exactly what content reached it.
vi.mock('@/components/MarkdownViewer', () => ({
  MarkdownViewer: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}))

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function LocationDisplay() {
  const loc = useLocation()
  return <div data-testid="location">{loc.pathname + loc.search}</div>
}

function renderHelp(entry = '/help') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Help />
      <LocationDisplay />
    </MemoryRouter>
  )
}

describe('Help', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    // Default: resolve so navigation tests don't hang on the loading branch.
    mockFetch.mockResolvedValue({ ok: true, text: async () => '# Help' })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows a loading spinner before the help content resolves', () => {
    mockFetch.mockReturnValue(new Promise(() => {}))
    renderHelp()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    expect(screen.queryByTestId('markdown')).not.toBeInTheDocument()
  })

  it('fetches /HELP.md and passes its text to MarkdownViewer', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      text: async () => '# Welcome\n\nThis is help.',
    })
    renderHelp()

    await waitFor(() => expect(screen.getByTestId('markdown')).toBeInTheDocument())
    expect(mockFetch).toHaveBeenCalledWith('/HELP.md')
    expect(screen.getByTestId('markdown')).toHaveTextContent('# Welcome This is help.')
  })

  it('renders fallback content when the fetch responds with !ok', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      text: async () => '',
    })
    renderHelp()

    await waitFor(() =>
      expect(screen.getByTestId('markdown')).toHaveTextContent('Unable to load help content')
    )
  })

  it('renders fallback content when the fetch rejects', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    mockFetch.mockRejectedValue(new Error('network down'))
    renderHelp()

    await waitFor(() =>
      expect(screen.getByTestId('markdown')).toHaveTextContent('Unable to load help content')
    )
  })

  describe('navigation handlers', () => {
    it('handleRepoChange sets repo and drops branch/commit', async () => {
      const user = userEvent.setup()
      renderHelp('/help?repo=old&branch=main&commit=deadbeef')

      await waitFor(() => expect(screen.getByTestId('markdown')).toBeInTheDocument())
      await user.click(screen.getByText('repo'))

      expect(screen.getByTestId('location')).toHaveTextContent('/help?repo=newrepo')
      expect(screen.getByTestId('location')).not.toHaveTextContent('branch')
    })

    it('handleBranchChange sets branch and drops commit', async () => {
      const user = userEvent.setup()
      renderHelp('/help?repo=myrepo&branch=main&commit=deadbeef')

      await waitFor(() => expect(screen.getByTestId('markdown')).toBeInTheDocument())
      await user.click(screen.getByText('branch'))

      expect(screen.getByTestId('location')).toHaveTextContent('/help?repo=myrepo&branch=newbranch')
      expect(screen.getByTestId('location')).not.toHaveTextContent('commit')
    })

    it('handleCommitChange sets commit and keeps repo/branch', async () => {
      const user = userEvent.setup()
      renderHelp('/help?repo=myrepo&branch=main')

      await waitFor(() => expect(screen.getByTestId('markdown')).toBeInTheDocument())
      await user.click(screen.getByText('commit'))

      expect(screen.getByTestId('location')).toHaveTextContent('commit=abc123')
      expect(screen.getByTestId('location')).toHaveTextContent('repo=myrepo')
    })

    it('handleTabChange → browse navigates to the repo browse path when repo is set', async () => {
      const user = userEvent.setup()
      renderHelp('/help?repo=myrepo&branch=main&commit=deadbeef')

      await waitFor(() => expect(screen.getByTestId('markdown')).toBeInTheDocument())
      await user.click(screen.getByText('tab-browse'))

      expect(screen.getByTestId('location')).toHaveTextContent('/browse/myrepo')
      expect(screen.getByTestId('location')).toHaveTextContent('repo=myrepo')
    })

    it('handleTabChange → browse navigates home when no repo is set', async () => {
      const user = userEvent.setup()
      renderHelp('/help')

      await waitFor(() => expect(screen.getByTestId('markdown')).toBeInTheDocument())
      await user.click(screen.getByText('tab-browse'))

      expect(screen.getByTestId('location')).toHaveTextContent('/')
      expect(screen.getByTestId('location')).not.toHaveTextContent('browse')
    })

    it('handleTabChange navigates to search/history/logical-view/dependencies', async () => {
      const user = userEvent.setup()
      const cases: Array<[string, string]> = [
        ['tab-search', '/search'],
        ['tab-history', '/history'],
        ['tab-logical', '/logical-view'],
        ['tab-deps', '/dependencies'],
      ]
      for (const [button, path] of cases) {
        const { unmount } = renderHelp('/help?repo=myrepo')
        await waitFor(() => expect(screen.getByTestId('markdown')).toBeInTheDocument())
        await user.click(screen.getByText(button))
        expect(screen.getByTestId('location')).toHaveTextContent(path)
        unmount()
      }
    })

    it('handleTabChange → help stays on the help page', async () => {
      const user = userEvent.setup()
      renderHelp('/help?repo=myrepo')

      await waitFor(() => expect(screen.getByTestId('markdown')).toBeInTheDocument())
      await user.click(screen.getByText('tab-help'))

      expect(screen.getByTestId('location')).toHaveTextContent('/help')
    })
  })
})
