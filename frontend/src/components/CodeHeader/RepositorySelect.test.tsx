import { describe, it, expect, vi, afterEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import { render, screen } from '@/test/utils'
import { RepositorySelect } from './RepositorySelect'
import type { Repository } from '@/lib/api'

const mockRepositories: Repository[] = [
  {
    id: 1,
    name: 'inxr2',
    url: 'https://example.com/inxr2',
    description: null,
    default_branch: 'main',
    created_at: null,
    updated_at: null,
  },
  {
    id: 2,
    name: 'other-repo',
    url: 'https://example.com/other-repo',
    description: null,
    default_branch: 'main',
    created_at: null,
    updated_at: null,
  },
]

function invalidValueCalls(): unknown[][] {
  const allCalls = [...vi.mocked(console.warn).mock.calls, ...vi.mocked(console.error).mock.calls]
  return allCalls.filter((args) =>
    args.some(
      (arg) => typeof arg === 'string' && arg.includes('provided to Autocomplete is invalid')
    )
  )
}

describe('RepositorySelect', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should not warn about an invalid Autocomplete value when the repo is unknown', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <RepositorySelect
        repositories={mockRepositories}
        loading={false}
        repoName="ghost-repo"
        currentTab="browse"
        onRepoChange={vi.fn()}
      />
    )

    // The selector shows what the URL requested rather than silently switching away from it
    expect(screen.getByRole('combobox')).toHaveValue('ghost-repo')
    expect(invalidValueCalls()).toHaveLength(0)
  })

  it('should not warn about an invalid Autocomplete value on the search tab', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <RepositorySelect
        repositories={mockRepositories}
        loading={false}
        repoName="ghost-repo"
        currentTab="search"
        onRepoChange={vi.fn()}
      />
    )

    expect(screen.getByRole('combobox')).toHaveValue('ghost-repo')
    expect(invalidValueCalls()).toHaveLength(0)
  })

  it('should display a known repo and list the real repos in the dropdown', async () => {
    const user = userEvent.setup()
    const onRepoChange = vi.fn()

    render(
      <RepositorySelect
        repositories={mockRepositories}
        loading={false}
        repoName="inxr2"
        currentTab="browse"
        onRepoChange={onRepoChange}
      />
    )

    expect(screen.getByRole('combobox')).toHaveValue('inxr2')

    await user.click(screen.getByRole('button', { name: /open/i }))
    const options = screen.getAllByRole('option').map((o) => o.textContent)
    expect(options).toEqual(['inxr2', 'other-repo'])

    await user.click(screen.getByRole('option', { name: 'other-repo' }))
    expect(onRepoChange).toHaveBeenCalledWith('other-repo')
  })

  it('should offer All Repositories plus the real repos on the search tab', async () => {
    const user = userEvent.setup()
    const onRepoChange = vi.fn()

    render(
      <RepositorySelect
        repositories={mockRepositories}
        loading={false}
        repoName={null}
        currentTab="search"
        onRepoChange={onRepoChange}
      />
    )

    expect(screen.getByRole('combobox')).toHaveValue('All Repositories')

    await user.click(screen.getByRole('button', { name: /open/i }))
    const options = screen.getAllByRole('option').map((o) => o.textContent)
    expect(options).toEqual(['All Repositories', 'inxr2', 'other-repo'])

    await user.click(screen.getByRole('option', { name: 'inxr2' }))
    expect(onRepoChange).toHaveBeenCalledWith('inxr2')
  })
})
