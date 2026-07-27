import { describe, it, expect, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { render, screen } from '@/test/utils'
import { consoleCalls } from '@/test/consoleGuard'
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

// The suite-wide console guard already fails any test that logs (see
// consoleGuard.ts), so these read the recorded calls rather than spying. Naming
// MUI's specific wording keeps the #530 regression explicit: if the warning
// comes back, this fails pointing straight at the cause.
function invalidValueCalls(): string[] {
  return consoleCalls()
    .map((call) => call.text)
    .filter((text) => text.includes('provided to Autocomplete is invalid'))
}

describe('RepositorySelect', () => {
  it('should not warn about an invalid Autocomplete value when the repo is unknown', async () => {
    const user = userEvent.setup()

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

    // ...and it is a real option, not just a displayed string: the dropdown offers it
    // alongside the loaded repos, so reopening the menu doesn't drop the requested repo.
    await user.click(screen.getByRole('button', { name: /open/i }))
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'inxr2',
      'other-repo',
      'ghost-repo',
    ])

    expect(invalidValueCalls()).toHaveLength(0)
  })

  it('should not warn about an invalid Autocomplete value on the search tab', async () => {
    const user = userEvent.setup()

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

    // The search tab's custom filterOptions strips and re-prepends ALL_REPOS_OPTION, so this
    // also covers the injected value surviving that path exactly once, with no duplicate.
    await user.click(screen.getByRole('button', { name: /open/i }))
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'All Repositories',
      'inxr2',
      'other-repo',
      'ghost-repo',
    ])

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
