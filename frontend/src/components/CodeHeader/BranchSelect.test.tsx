import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@/test/utils'
import { BranchSelect } from './BranchSelect'
import type { BranchInfo } from '@/lib/api'

const mockBranches: BranchInfo[] = [
  {
    name: 'main',
    last_indexed_commit: 'abc123',
    oldest_indexed_commit: 'def456',
    commit_count: 10,
    last_indexed_at: '2024-01-01',
  },
  {
    name: 'feature-branch',
    last_indexed_commit: 'ghi789',
    oldest_indexed_commit: 'jkl012',
    commit_count: 5,
    last_indexed_at: '2024-01-01',
  },
]

describe('BranchSelect', () => {
  it('should not produce MUI out-of-range warning when branch is not in options', () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <BranchSelect
        branches={mockBranches}
        loading={false}
        branch="master"
        defaultBranch="main"
        onBranchChange={vi.fn()}
      />
    )

    // Should NOT have any MUI out-of-range warnings
    const allCalls = [...consoleWarnSpy.mock.calls, ...consoleErrorSpy.mock.calls]
    const outOfRangeCalls = allCalls.filter((args) =>
      args.some((arg) => typeof arg === 'string' && arg.includes('out-of-range'))
    )
    expect(outOfRangeCalls).toHaveLength(0)

    consoleWarnSpy.mockRestore()
    consoleErrorSpy.mockRestore()
  })

  it('should display the correct branch when it is in options', () => {
    render(
      <BranchSelect
        branches={mockBranches}
        loading={false}
        branch="main"
        defaultBranch="main"
        onBranchChange={vi.fn()}
      />
    )

    expect(screen.getByText('main')).toBeInTheDocument()
  })

  it('should fall back to defaultBranch when branch is null', () => {
    render(
      <BranchSelect
        branches={mockBranches}
        loading={false}
        branch={null}
        defaultBranch="main"
        onBranchChange={vi.fn()}
      />
    )

    expect(screen.getByText('main')).toBeInTheDocument()
  })
})
