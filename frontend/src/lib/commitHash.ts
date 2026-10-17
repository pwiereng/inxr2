/**
 * Commit hash matching.
 *
 * URLs may carry an abbreviated hash (e.g. pasted from `git log --oneline`),
 * while commit lists from the API always hold full 40-char hashes. Comparing
 * them with `===` silently fails for short hashes (#555), so URL-derived
 * commit values should be matched with these helpers instead.
 *
 * Matching mirrors the backend's resolution (CommitAdapter.find_by_hash):
 * case-sensitive, and an ambiguous prefix resolves to nothing rather than to
 * an arbitrary commit.
 */

// Git's minimum abbreviation length; shorter prefixes are too ambiguous.
const MIN_PREFIX_LENGTH = 4

/** True when `ref` is `fullHash` or an abbreviation (prefix) of it. */
export function hashMatches(fullHash: string, ref: string | null | undefined): boolean {
  if (!ref) return false
  if (fullHash === ref) return true
  return ref.length >= MIN_PREFIX_LENGTH && fullHash.startsWith(ref)
}

/**
 * The item whose hash `ref` names: an exact match, else the single item it is
 * a prefix of. Returns undefined when nothing matches or the prefix is ambiguous.
 */
export function findByHash<T>(
  items: readonly T[],
  ref: string | null | undefined,
  getHash: (item: T) => string
): T | undefined {
  if (!ref) return undefined
  const exact = items.find((item) => getHash(item) === ref)
  if (exact !== undefined) return exact
  const matches = items.filter((item) => hashMatches(getHash(item), ref))
  return matches.length === 1 ? matches[0] : undefined
}

/** Map lookup keyed by full hash that also accepts an unambiguous abbreviated `ref`. */
export function getByHash<V>(map: Map<string, V>, ref: string | null | undefined): V | undefined {
  const key = findByHash([...map.keys()], ref, (hash) => hash)
  return key === undefined ? undefined : map.get(key)
}
