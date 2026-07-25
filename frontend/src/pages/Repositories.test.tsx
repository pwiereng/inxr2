import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Repositories from './Repositories'
import * as api from '@/lib/api'
import type { RepositoryStats } from '@/lib/api'
import { ROUTER_FUTURE_FLAGS } from '@/lib/routerFuture'

vi.mock('@/lib/api', () => ({
  getAllRepositoryStats: vi.fn(),
}))

function makeStats(overrides: Partial<RepositoryStats> = {}): RepositoryStats {
  return {
    repository_id: 1,
    name: 'my-repo',
    total_files: 10,
    total_symbols: 100,
    total_references: 200,
    languages: { python: 5 },
    total_lines: 1000,
    total_references_resolved: 150,
    total_references_unresolved: 50,
    commit_date_earliest: null,
    commit_date_latest: null,
    last_indexed_at: null,
    last_indexed_commit: null,
    last_indexing_duration_seconds: null,
    last_resolving_duration_seconds: null,
    git_head_commit: null,
    is_stale: false,
    ...overrides,
  }
}

function renderRepositories() {
  return render(
    <MemoryRouter future={ROUTER_FUTURE_FLAGS}>
      <Repositories />
    </MemoryRouter>
  )
}

describe('Repositories', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner initially', () => {
    vi.mocked(api.getAllRepositoryStats).mockReturnValue(new Promise(() => {}))
    renderRepositories()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('shows error state on API failure', async () => {
    vi.mocked(api.getAllRepositoryStats).mockRejectedValue(new Error('Boom'))
    renderRepositories()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText('Error: Boom')).toBeInTheDocument()
  })

  it('shows a generic message for non-Error rejections', async () => {
    vi.mocked(api.getAllRepositoryStats).mockRejectedValue('nope')
    renderRepositories()

    await waitFor(() => expect(screen.getByText('Error: Unknown error')).toBeInTheDocument())
  })

  it('shows empty state when no repositories are indexed', async () => {
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue([])
    renderRepositories()

    await waitFor(() =>
      expect(screen.getByText('No repositories indexed yet.')).toBeInTheDocument()
    )
    expect(screen.getByText('Use the API to index a local directory')).toBeInTheDocument()
  })

  it('renders a card per repo and links to the URL-encoded browse path', async () => {
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue([
      makeStats({ repository_id: 1, name: 'my repo' }),
      makeStats({ repository_id: 2, name: 'other' }),
    ])
    renderRepositories()

    await waitFor(() => expect(screen.getByText('my repo')).toBeInTheDocument())
    expect(screen.getByText('other')).toBeInTheDocument()

    const links = screen.getAllByRole('link')
    expect(links[0]).toHaveAttribute('href', '/browse/my%20repo')
    expect(links[1]).toHaveAttribute('href', '/browse/other')
  })

  it('renders the "Last indexed" chip when last_indexed_at is present', async () => {
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue([
      makeStats({ last_indexed_at: '2026-01-15T10:30:00Z' }),
    ])
    renderRepositories()

    await waitFor(() =>
      expect(screen.getByText('Last indexed: 2026-01-15 10:30 UTC')).toBeInTheDocument()
    )
  })

  it('omits the "Last indexed" chip when last_indexed_at is null', async () => {
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue([
      makeStats({ name: 'plain', last_indexed_at: null }),
    ])
    renderRepositories()

    await waitFor(() => expect(screen.getByText('plain')).toBeInTheDocument())
    expect(screen.queryByText(/Last indexed:/)).not.toBeInTheDocument()
  })

  it('renders a duration chip with resolve suffix when both durations are present', async () => {
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue([
      makeStats({
        last_indexing_duration_seconds: 90,
        last_resolving_duration_seconds: 45,
      }),
    ])
    renderRepositories()

    await waitFor(() =>
      expect(screen.getByText('Duration: 1m 30s (resolve: 45s)')).toBeInTheDocument()
    )
  })

  it('renders a duration chip without resolve suffix when resolving duration is null', async () => {
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue([
      makeStats({
        last_indexing_duration_seconds: 30,
        last_resolving_duration_seconds: null,
      }),
    ])
    renderRepositories()

    await waitFor(() => expect(screen.getByText('Duration: 30s')).toBeInTheDocument())
    expect(screen.queryByText(/resolve:/)).not.toBeInTheDocument()
  })

  it('omits the duration chip when indexing duration is null', async () => {
    vi.mocked(api.getAllRepositoryStats).mockResolvedValue([
      makeStats({ name: 'no-duration', last_indexing_duration_seconds: null }),
    ])
    renderRepositories()

    await waitFor(() => expect(screen.getByText('no-duration')).toBeInTheDocument())
    expect(screen.queryByText(/Duration:/)).not.toBeInTheDocument()
  })
})
