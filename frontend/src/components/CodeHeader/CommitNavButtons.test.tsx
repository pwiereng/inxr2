import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import { CommitNavButtons } from './CommitNavButtons'
import type { CommitInfo } from '@/lib/api'

const makeCommit = (hash: string, message: string): CommitInfo => ({
  hash,
  short_hash: hash.substring(0, 7),
  message,
  author_name: 'Test Author',
  author_email: 'test@example.com',
  commit_date: '2024-01-01T10:00:00Z',
  is_indexed: true,
  tags: [],
  is_branch_specific: false,
  is_merge_base: false,
})

// commits[0] = HEAD (newest), commits[2] = oldest
const threeCommits: CommitInfo[] = [
  makeCommit('aaaa111', 'HEAD commit'),
  makeCommit('bbbb222', 'Middle commit'),
  makeCommit('cccc333', 'Oldest commit'),
]

describe('CommitNavButtons', () => {
  it('should render nothing when commits is empty', () => {
    const { container } = render(
      <CommitNavButtons commits={[]} commitDisplayValue="" onCommitChange={vi.fn()} />
    )
    expect(container.innerHTML).toBe('')
  })

  it('should render both buttons when commits exist', () => {
    render(
      <CommitNavButtons
        commits={threeCommits}
        commitDisplayValue="bbbb222"
        onCommitChange={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /older commit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /newer commit/i })).toBeInTheDocument()
  })

  it('should disable newer button at HEAD (index 0)', () => {
    render(
      <CommitNavButtons
        commits={threeCommits}
        commitDisplayValue="aaaa111"
        onCommitChange={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /newer commit/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /older commit/i })).not.toBeDisabled()
  })

  it('should disable older button at oldest commit (last index)', () => {
    render(
      <CommitNavButtons
        commits={threeCommits}
        commitDisplayValue="cccc333"
        onCommitChange={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /older commit/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /newer commit/i })).not.toBeDisabled()
  })

  it('should enable both buttons when in the middle', () => {
    render(
      <CommitNavButtons
        commits={threeCommits}
        commitDisplayValue="bbbb222"
        onCommitChange={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /older commit/i })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: /newer commit/i })).not.toBeDisabled()
  })

  it('should navigate to older commit on back click', () => {
    const onCommitChange = vi.fn()
    render(
      <CommitNavButtons
        commits={threeCommits}
        commitDisplayValue="aaaa111"
        onCommitChange={onCommitChange}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /older commit/i }))
    expect(onCommitChange).toHaveBeenCalledWith('bbbb222')
  })

  it('should navigate to newer commit on forward click', () => {
    const onCommitChange = vi.fn()
    render(
      <CommitNavButtons
        commits={threeCommits}
        commitDisplayValue="cccc333"
        onCommitChange={onCommitChange}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /newer commit/i }))
    expect(onCommitChange).toHaveBeenCalledWith('bbbb222')
  })

  it('should treat unknown commit as HEAD (index 0)', () => {
    const onCommitChange = vi.fn()
    render(
      <CommitNavButtons
        commits={threeCommits}
        commitDisplayValue="unknown_hash"
        onCommitChange={onCommitChange}
      />
    )
    // Newer should be disabled (treated as index 0)
    expect(screen.getByRole('button', { name: /newer commit/i })).toBeDisabled()
    // Older should navigate to index 1
    fireEvent.click(screen.getByRole('button', { name: /older commit/i }))
    expect(onCommitChange).toHaveBeenCalledWith('bbbb222')
  })

  it('should disable both buttons when only one commit exists', () => {
    const singleCommit = [makeCommit('aaaa111', 'Only commit')]
    render(
      <CommitNavButtons
        commits={singleCommit}
        commitDisplayValue="aaaa111"
        onCommitChange={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /older commit/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /newer commit/i })).toBeDisabled()
  })
})
