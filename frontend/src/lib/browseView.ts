/**
 * Pure presentation helpers for the Browse page.
 *
 * Extracted from Browse.tsx so the hash-formatting and tab-navigation logic
 * can be unit-tested without rendering the component. This module is
 * framework-free: it imports types only (no React/MUI) so it stays cheap to
 * import and trivial to test.
 */

import type { TabValue } from '@/components/CodeHeader'

/**
 * Truncate a commit hash to its 7-character short form for display.
 *
 * Returns 'latest' when the hash is absent (null/undefined/empty) — this is
 * the tree/diff header fallback meaning "current branch HEAD".
 */
export function getShortHash(hash: string | null | undefined): string {
  if (!hash) return 'latest'
  return hash.substring(0, 7)
}

/**
 * Display text for a diff-panel version dropdown entry.
 *
 * Like {@link getShortHash} but uses '...' as the unresolved placeholder
 * because in the diff dropdowns a missing commit means "still resolving"
 * rather than "latest".
 */
export function getVersionDisplay(commit: string | null | undefined): string {
  return commit ? commit.substring(0, 7) : '...'
}

/** Repo/branch/commit context threaded into header tab navigation targets. */
export interface TabNavParams {
  repoName?: string | null
  selectedBranch?: string | null
  selectedCommit?: string | null
}

/**
 * Build the destination URL for a header tab, preserving the current
 * repo/branch/commit as query params.
 *
 * Returns `null` for the 'browse' tab (we're already on Browse, so there is
 * nothing to navigate to).
 */
export function getTabNavTarget(tab: TabValue, params: TabNavParams): string | null {
  if (tab === 'browse') return null

  const search = new URLSearchParams()
  if (params.repoName) search.set('repo', params.repoName)
  if (params.selectedBranch) search.set('branch', params.selectedBranch)
  if (params.selectedCommit) search.set('commit', params.selectedCommit)
  const query = search.toString()

  switch (tab) {
    case 'search':
      return `/search?${query}`
    case 'history':
      return `/history?${query}`
    case 'logical-view':
      return `/logical-view?${query}`
    case 'dependencies':
      return `/dependencies?${query}`
    case 'help':
      return `/help?${query}`
  }
}
