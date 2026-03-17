import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Activity from './Activity'
import * as api from '@/lib/api'
import type { Repository } from '@/lib/api'
import { AppProvider } from '@/contexts/AppContext'

vi.mock('@/lib/api', () => ({
  getActivityLog: vi.fn(),
  getRepositories: vi.fn(),
}))

const mockEntries = [
  {
    id: 1,
    source: 'http',
    tool_or_path: '/api/search',
    logged_at: '2024-01-15T10:30:00Z',
    params: { q: 'hello' },
    repository: 'inxr2',
    status_code: 200,
    duration_ms: 42,
    result_count: 5,
    session_id: null,
  },
  {
    id: 2,
    source: 'mcp',
    tool_or_path: 'search_code',
    logged_at: '2024-01-15T10:31:00Z',
    params: { query: 'foo', repository: 'inxr2' },
    repository: 'inxr2',
    status_code: null,
    duration_ms: 88,
    result_count: 3,
    session_id: null,
  },
]

function renderActivity() {
  return render(
    <MemoryRouter>
      <AppProvider>
        <Activity />
      </AppProvider>
    </MemoryRouter>
  )
}

const mockRepositories: Repository[] = [
  {
    id: 1,
    name: 'inxr2',
    url: 'https://github.com/test/inxr2',
    description: null,
    default_branch: 'main',
    created_at: null,
    updated_at: null,
  },
]

describe('Activity', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepositories).mockResolvedValue(mockRepositories)
  })

  it('shows loading spinner initially', () => {
    vi.mocked(api.getActivityLog).mockReturnValue(new Promise(() => {}))
    renderActivity()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('renders entries after load', async () => {
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: mockEntries, total: 2 })
    renderActivity()

    await waitFor(() => expect(screen.getByText('/api/search')).toBeInTheDocument())
    expect(screen.getByText('search_code')).toBeInTheDocument()
    expect(screen.getByText('http')).toBeInTheDocument()
    expect(screen.getByText('mcp')).toBeInTheDocument()
  })

  it('shows empty state when no entries', async () => {
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: [], total: 0 })
    renderActivity()

    await waitFor(() => expect(screen.getByText(/No activity recorded yet/)).toBeInTheDocument())
  })

  it('shows error state on API failure', async () => {
    vi.mocked(api.getActivityLog).mockRejectedValue(new Error('Server error'))
    renderActivity()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText('Server error')).toBeInTheDocument()
  })

  it('filters by source when changed', async () => {
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: mockEntries, total: 2 })
    const user = userEvent.setup()
    renderActivity()

    await waitFor(() => expect(screen.getByText('/api/search')).toBeInTheDocument())

    // First combobox is the Source filter
    const [sourceCombobox] = screen.getAllByRole('combobox')
    await user.click(sourceCombobox!)
    await user.click(screen.getByRole('option', { name: 'MCP' }))

    await waitFor(() => {
      expect(api.getActivityLog).toHaveBeenCalledWith(expect.objectContaining({ source: 'mcp' }))
    })
  })

  it('filters by repository when changed', async () => {
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: mockEntries, total: 2 })
    const user = userEvent.setup()
    renderActivity()

    await waitFor(() => expect(screen.getByText('/api/search')).toBeInTheDocument())

    // Second combobox is the Repository filter
    const [, repoCombobox] = screen.getAllByRole('combobox')
    await user.click(repoCombobox!)
    await user.click(screen.getByRole('option', { name: 'inxr2' }))

    await waitFor(() => {
      expect(api.getActivityLog).toHaveBeenCalledWith(
        expect.objectContaining({ repository: 'inxr2' })
      )
    })
  })

  it('auto-refreshes every 5 seconds', async () => {
    vi.useFakeTimers()
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: mockEntries, total: 2 })

    renderActivity()

    // Let initial load settle
    await act(async () => {
      await Promise.resolve()
    })

    const callsBefore = vi.mocked(api.getActivityLog).mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(5000)
      await Promise.resolve()
    })

    expect(vi.mocked(api.getActivityLog).mock.calls.length).toBeGreaterThan(callsBefore)
    vi.useRealTimers()
  })

  it('stops auto-refresh when toggle is turned off', async () => {
    vi.useFakeTimers()
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: mockEntries, total: 2 })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) })

    renderActivity()
    await act(async () => {
      await Promise.resolve()
    })

    // Turn off auto-refresh
    await act(async () => {
      await user.click(screen.getByRole('checkbox'))
    })

    const callsAfterToggle = vi.mocked(api.getActivityLog).mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(15000)
      await Promise.resolve()
    })

    expect(vi.mocked(api.getActivityLog).mock.calls.length).toBe(callsAfterToggle)
    vi.useRealTimers()
  })

  it('expands params row on click', async () => {
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: mockEntries, total: 2 })
    const user = userEvent.setup()
    renderActivity()

    await waitFor(() => expect(screen.getByText('/api/search')).toBeInTheDocument())

    // Click the first expand button (first entry has params { q: 'hello' })
    const expandButtons = screen.getAllByRole('button', { name: 'Expand params' })
    await user.click(expandButtons[0]!)

    await waitFor(() => expect(screen.getByText(/"q"/)).toBeInTheDocument())
  })

  it('shows status chips for HTTP entries', async () => {
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: mockEntries, total: 2 })
    renderActivity()

    await waitFor(() => expect(screen.getByText('200')).toBeInTheDocument())
  })

  it('shows entry count in header', async () => {
    vi.mocked(api.getActivityLog).mockResolvedValue({ entries: mockEntries, total: 2 })
    renderActivity()

    await waitFor(() => expect(screen.getByText('2 entries')).toBeInTheDocument())
  })
})
