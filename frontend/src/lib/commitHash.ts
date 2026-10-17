/**
 * Commit hash matching.
 *
 * URLs may carry an abbreviated hash (e.g. pasted from `git log --oneline`),
 * while commit lists from the API always hold full 40-char hashes. Comparing
 * them with `===` silently fails for short hashes (#555), so URL-derived
 * commit values should be matched with these helpers instead.
 */

// Git's minimum abbreviation length; shorter prefixes are too ambiguous.
const MIN_PREFIX_LENGTH = 4

/** True when `ref` is `fullHash` or an abbreviation (prefix) of it. */
export function hashMatches(fullHash: string, ref: string | null | undefined): boolean {
  if (!ref) return false
  if (fullHash === ref) return true
  if (ref.length < MIN_PREFIX_LENGTH) return false
  return fullHash.toLowerCase().startsWith(ref.toLowerCase())
}

/** Map lookup keyed by full hash that also accepts an abbreviated `ref`. */
export function getByHash<V>(map: Map<string, V>, ref: string | null | undefined): V | undefined {
  if (!ref) return undefined
  const exact = map.get(ref)
  if (exact !== undefined) return exact
  for (const [hash, value] of map) {
    if (hashMatches(hash, ref)) return value
  }
  return undefined
}
