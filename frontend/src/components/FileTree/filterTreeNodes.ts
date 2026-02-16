import type { TreeNode } from '@/lib/api'

export interface FlatFileEntry {
  node: TreeNode
  /** Full path (e.g. "src/components/Button.tsx") */
  path: string
  /** File/directory name (e.g. "Button.tsx") */
  name: string
  /** "file" or "directory" */
  type: 'file' | 'directory'
}

export interface HighlightMatch {
  before: string
  match: string
  after: string
}

const MAX_RESULTS = 50

/**
 * Recursively flatten a tree of nodes into a flat list of entries.
 * Directories are included alongside their children.
 */
export function flattenTree(nodes: TreeNode[]): FlatFileEntry[] {
  const result: FlatFileEntry[] = []

  function walk(nodeList: TreeNode[]) {
    for (const node of nodeList) {
      result.push({
        node,
        path: node.path,
        name: node.name,
        type: node.type,
      })
      if (node.children) {
        walk(node.children)
      }
    }
  }

  walk(nodes)
  return result
}

/**
 * Filter entries by query and rank by relevance.
 *
 * Ranking tiers (lower = better):
 *   1. Name starts with query
 *   2. Name contains query
 *   3. Path contains query
 *
 * Within the same tier, files rank above directories.
 * Results are capped at MAX_RESULTS.
 */
export function filterAndRank(entries: FlatFileEntry[], query: string): FlatFileEntry[] {
  if (!query.trim()) return []

  const q = query.trim().toLowerCase()

  const scored: { entry: FlatFileEntry; score: number }[] = []

  for (const entry of entries) {
    const nameLower = entry.name.toLowerCase()
    const pathLower = entry.path.toLowerCase()

    let tier: number
    if (nameLower.startsWith(q)) {
      tier = 0
    } else if (nameLower.includes(q)) {
      tier = 1
    } else if (pathLower.includes(q)) {
      tier = 2
    } else {
      continue
    }

    // Within same tier: files (0) before directories (1)
    const typeBonus = entry.type === 'file' ? 0 : 1
    const score = tier * 2 + typeBonus

    scored.push({ entry, score })
  }

  scored.sort((a, b) => a.score - b.score)

  return scored.slice(0, MAX_RESULTS).map((s) => s.entry)
}

/**
 * Find the first case-insensitive match of `query` in `text` and split
 * into before / match / after segments. If no match, `match` is empty
 * and `before` contains the full text.
 */
export function highlightMatch(text: string, query: string): HighlightMatch {
  if (!query) {
    return { before: text, match: '', after: '' }
  }

  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) {
    return { before: text, match: '', after: '' }
  }

  return {
    before: text.slice(0, idx),
    match: text.slice(idx, idx + query.length),
    after: text.slice(idx + query.length),
  }
}
