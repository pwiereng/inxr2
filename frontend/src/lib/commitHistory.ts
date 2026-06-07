// Pure helpers extracted from the History page (src/pages/History.tsx).
// Keep this module framework-free: it imports TYPES only from '@/lib/api'
// (no React / MUI), so the logic can be unit-tested in isolation.

/**
 * Split a git commit message into its summary (first line) and body (the
 * remainder, trimmed). Mirrors `git log` conventions where the first line is
 * the subject and a blank line separates it from the body.
 */
export function splitCommitMessage(message: string): { summary: string; body: string } {
  const parts = message.split('\n')
  const summary = parts[0] || ''
  const body = parts.slice(1).join('\n').trim()
  return { summary, body }
}

/**
 * Build the cache key used to decide whether a fresh commit load is needed.
 * A null/undefined branch collapses to an empty segment so "repo" and
 * "repo (no branch)" share the same key.
 */
export function makeLoadKey(repoName: string, branch: string | null | undefined): string {
  return `${repoName}:${branch ?? ''}`
}

/**
 * Decide whether commits should be (re)loaded: only when the requested key
 * differs from the one already loaded.
 */
export function shouldLoadCommits(prevKey: string | null, nextKey: string): boolean {
  return prevKey !== nextKey
}

/**
 * Build the browse path + query for navigating to an indexed commit.
 * `co=1` always limits the browse view to changed files by default.
 * The caller owns the `is_indexed`/`repoName` guard and the navigate() call.
 */
export function buildCommitBrowseTarget(
  repoName: string,
  branch: string | null | undefined,
  commitHash: string
): string {
  const params = new URLSearchParams()
  if (branch) params.set('branch', branch)
  params.set('commit', commitHash)
  params.set('co', '1') // Show only changed files by default
  return `/browse/${repoName}?${params.toString()}`
}
