import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@/test/utils'
import { CommitSelect } from './CommitSelect'
import type { CommitInfo } from '@/lib/api'

const mockCommits: CommitInfo[] = [
  {
    hash: 'abc123def456',
    short_hash: 'abc123d',
    message: 'First commit',
    author_name: 'Test Author',
    author_email: 'test@example.com',
    commit_date: '2024-01-01T10:30:00Z',
    is_indexed: true,
    tags: [],
    is_branch_specific: false,
    is_merge_base: false,
  },
  {
    hash: 'def456ghi789',
    short_hash: 'def456g',
    message: 'Second commit',
    author_name: 'Test Author',
    author_email: 'test@example.com',
    commit_date: '2024-01-02T14:45:00Z',
    is_indexed: true,
    tags: [],
    is_branch_specific: false,
    is_merge_base: false,
  },
]

describe('CommitSelect', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should not produce MUI out-of-range warning when commit is not in options', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <CommitSelect
        commits={mockCommits}
        loading={false}
        commitDisplayValue="e20da5f999888777666555"
        onCommitChange={vi.fn()}
      />
    )

    // Should show "latest" as the rendered value since commit is not in list
    expect(screen.getByText('latest')).toBeInTheDocument()

    // Should NOT have any MUI out-of-range warnings
    const warnCalls = vi.mocked(console.warn).mock.calls
    const errorCalls = vi.mocked(console.error).mock.calls
    const allCalls = [...warnCalls, ...errorCalls]
    const outOfRangeCalls = allCalls.filter((args) =>
      args.some((arg) => typeof arg === 'string' && arg.includes('out-of-range'))
    )
    expect(outOfRangeCalls).toHaveLength(0)
  })

  it('should display the correct hash when commit is in options', () => {
    render(
      <CommitSelect
        commits={mockCommits}
        loading={false}
        commitDisplayValue="abc123def456"
        onCommitChange={vi.fn()}
      />
    )

    expect(screen.getByText('abc123d')).toBeInTheDocument()
  })

  it('should display "latest" when commitDisplayValue is empty', () => {
    render(
      <CommitSelect
        commits={mockCommits}
        loading={false}
        commitDisplayValue=""
        onCommitChange={vi.fn()}
      />
    )

    expect(screen.getByText('latest')).toBeInTheDocument()
  })
})
