import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@/test/utils'
import { fireEvent } from '@testing-library/react'
import { consoleCalls } from '@/test/consoleGuard'
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
  it('should not produce MUI out-of-range warning when commit is not in options', () => {
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

    // Should NOT have any MUI out-of-range warnings. The suite-wide console
    // guard (consoleGuard.ts) already fails this test on any console output;
    // naming the wording keeps the #517 regression explicit in the failure.
    const outOfRangeCalls = consoleCalls().filter((call) => call.text.includes('out-of-range'))
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

  it('should render CircularProgress when loading is true', () => {
    render(
      <CommitSelect
        commits={mockCommits}
        loading={true}
        commitDisplayValue=""
        onCommitChange={vi.fn()}
      />
    )

    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('should render nothing when commits is empty', () => {
    const { container } = render(
      <CommitSelect commits={[]} loading={false} commitDisplayValue="" onCommitChange={vi.fn()} />
    )

    expect(container.firstChild).toBeNull()
  })

  it('should show HEAD badge on first commit but not second', () => {
    render(
      <CommitSelect
        commits={mockCommits}
        loading={false}
        commitDisplayValue=""
        onCommitChange={vi.fn()}
      />
    )

    const selectElement = screen.getByRole('combobox')
    fireEvent.mouseDown(selectElement)

    const headBadges = screen.getAllByText('HEAD')
    expect(headBadges).toHaveLength(1)

    // Verify it's associated with the first commit (abc123d) not the second
    const firstItem = screen.getByText('abc123d').closest('li')
    expect(firstItem).toHaveTextContent('HEAD')
    const secondItem = screen.getByText('def456g').closest('li')
    expect(secondItem).not.toHaveTextContent('HEAD')
  })

  it('should show FORK badge for commit with is_merge_base true', () => {
    const commitsWithMergeBase: CommitInfo[] = [
      ...mockCommits,
      {
        hash: 'fork111aaa222bbb333cc',
        short_hash: 'fork111',
        message: 'Fork commit',
        author_name: 'Test Author',
        author_email: 'test@example.com',
        commit_date: '2024-01-03T10:00:00Z',
        is_indexed: true,
        tags: [],
        is_branch_specific: false,
        is_merge_base: true,
      },
    ]

    render(
      <CommitSelect
        commits={commitsWithMergeBase}
        loading={false}
        commitDisplayValue=""
        onCommitChange={vi.fn()}
      />
    )

    const selectElement = screen.getByRole('combobox')
    fireEvent.mouseDown(selectElement)

    expect(screen.getByText('FORK')).toBeInTheDocument()
  })

  it('should render tag badges for commits with tags', () => {
    const commitsWithTags: CommitInfo[] = [
      {
        hash: 'tag111aaa222bbb333ccc4',
        short_hash: 'tag111a',
        message: 'Tagged commit',
        author_name: 'Test Author',
        author_email: 'test@example.com',
        commit_date: '2024-01-01T10:00:00Z',
        is_indexed: true,
        tags: ['v1.0', 'stable'],
        is_branch_specific: false,
        is_merge_base: false,
      },
    ]

    render(
      <CommitSelect
        commits={commitsWithTags}
        loading={false}
        commitDisplayValue=""
        onCommitChange={vi.fn()}
      />
    )

    const selectElement = screen.getByRole('combobox')
    fireEvent.mouseDown(selectElement)

    expect(screen.getByText('v1.0')).toBeInTheDocument()
    expect(screen.getByText('stable')).toBeInTheDocument()
  })

  it('should render branch-specific commit without error', () => {
    const commitsWithBranchSpecific: CommitInfo[] = [
      {
        hash: 'branch1aaa222bbb333ccc',
        short_hash: 'branch1',
        message: 'Branch-specific commit',
        author_name: 'Test Author',
        author_email: 'test@example.com',
        commit_date: '2024-01-01T10:00:00Z',
        is_indexed: true,
        tags: [],
        is_branch_specific: true,
        is_merge_base: false,
      },
    ]

    render(
      <CommitSelect
        commits={commitsWithBranchSpecific}
        loading={false}
        commitDisplayValue=""
        onCommitChange={vi.fn()}
      />
    )

    const selectElement = screen.getByRole('combobox')
    fireEvent.mouseDown(selectElement)

    expect(screen.getByText('branch1')).toBeInTheDocument()
  })

  it('should call onCommitChange with full hash when a commit is selected', () => {
    const onCommitChange = vi.fn()

    render(
      <CommitSelect
        commits={mockCommits}
        loading={false}
        commitDisplayValue=""
        onCommitChange={onCommitChange}
      />
    )

    const selectElement = screen.getByRole('combobox')
    fireEvent.mouseDown(selectElement)

    const secondCommitItem = screen.getByText('def456g').closest('li')!
    fireEvent.click(secondCommitItem)

    expect(onCommitChange).toHaveBeenCalledWith('def456ghi789')
  })
})
