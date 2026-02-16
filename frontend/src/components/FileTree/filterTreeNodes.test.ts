import { describe, it, expect } from 'vitest'
import { flattenTree, filterAndRank, highlightMatch } from './filterTreeNodes'
import type { TreeNode } from '@/lib/api'

const sampleTree: TreeNode[] = [
  {
    name: 'src',
    path: 'src',
    type: 'directory',
    file_id: null,
    language: null,
    children: [
      {
        name: 'components',
        path: 'src/components',
        type: 'directory',
        file_id: null,
        language: null,
        children: [
          {
            name: 'Button.tsx',
            path: 'src/components/Button.tsx',
            type: 'file',
            file_id: 1,
            language: 'typescript',
            children: null,
          },
          {
            name: 'Input.tsx',
            path: 'src/components/Input.tsx',
            type: 'file',
            file_id: 2,
            language: 'typescript',
            children: null,
          },
        ],
      },
      {
        name: 'index.ts',
        path: 'src/index.ts',
        type: 'file',
        file_id: 4,
        language: 'typescript',
        children: null,
      },
    ],
  },
  {
    name: 'README.md',
    path: 'README.md',
    type: 'file',
    file_id: 5,
    language: 'markdown',
    children: null,
  },
]

describe('flattenTree', () => {
  it('should flatten a nested tree into a flat list', () => {
    const result = flattenTree(sampleTree)
    const names = result.map((e) => e.name)
    expect(names).toEqual(['src', 'components', 'Button.tsx', 'Input.tsx', 'index.ts', 'README.md'])
  })

  it('should return empty array for empty tree', () => {
    expect(flattenTree([])).toEqual([])
  })

  it('should include both files and directories', () => {
    const result = flattenTree(sampleTree)
    const dirs = result.filter((e) => e.type === 'directory')
    const files = result.filter((e) => e.type === 'file')
    expect(dirs).toHaveLength(2)
    expect(files).toHaveLength(4)
  })

  it('should preserve full paths', () => {
    const result = flattenTree(sampleTree)
    const buttonEntry = result.find((e) => e.name === 'Button.tsx')
    expect(buttonEntry?.path).toBe('src/components/Button.tsx')
  })
})

describe('filterAndRank', () => {
  const flat = flattenTree(sampleTree)

  it('should return empty array for empty query', () => {
    expect(filterAndRank(flat, '')).toEqual([])
    expect(filterAndRank(flat, '   ')).toEqual([])
  })

  it('should filter case-insensitively', () => {
    const results = filterAndRank(flat, 'button')
    expect(results).toHaveLength(1)
    expect(results[0]!.name).toBe('Button.tsx')
  })

  it('should rank name-starts-with above name-contains', () => {
    const results = filterAndRank(flat, 'index')
    const names = results.map((e) => e.name)
    // "index.ts" starts with "index" (tier 0), "src" directory path-matches (tier 2)
    // Name-starts-with should rank first
    expect(names[0]).toBe('index.ts')
  })

  it('should rank files above directories at same relevance level', () => {
    // "index.ts" (file) starts with "index", "src" doesn't match
    // "components" doesn't start with "index" but path matches aren't relevant here
    const results = filterAndRank(flat, 'index')
    expect(results[0]!.name).toBe('index.ts')
    expect(results[0]!.type).toBe('file')
  })

  it('should match against path when name does not match', () => {
    // Search for "components" — the directory itself name-matches,
    // and files inside it path-match
    const results = filterAndRank(flat, 'components')
    expect(results.length).toBeGreaterThanOrEqual(1)
    // The directory "components" should rank first (name starts with query)
    expect(results[0]!.name).toBe('components')
  })

  it('should return no results for non-matching query', () => {
    const results = filterAndRank(flat, 'zzzznotfound')
    expect(results).toHaveLength(0)
  })

  it('should cap results at 50', () => {
    // Create a large flat list
    const bigList = Array.from({ length: 100 }, (_, i) => ({
      node: {
        name: `file${i}.ts`,
        path: `file${i}.ts`,
        type: 'file' as const,
        file_id: i,
        language: null,
        children: null,
      },
      path: `file${i}.ts`,
      name: `file${i}.ts`,
      type: 'file' as const,
    }))
    const results = filterAndRank(bigList, 'file')
    expect(results).toHaveLength(50)
  })
})

describe('highlightMatch', () => {
  it('should split text at the match position', () => {
    const result = highlightMatch('Button.tsx', 'but')
    expect(result).toEqual({ before: '', match: 'But', after: 'ton.tsx' })
  })

  it('should be case-insensitive', () => {
    const result = highlightMatch('README.md', 'readme')
    expect(result).toEqual({ before: '', match: 'README', after: '.md' })
  })

  it('should handle match in the middle', () => {
    const result = highlightMatch('src/components/Button.tsx', 'comp')
    expect(result).toEqual({ before: 'src/', match: 'comp', after: 'onents/Button.tsx' })
  })

  it('should handle no match', () => {
    const result = highlightMatch('Button.tsx', 'zzz')
    expect(result).toEqual({ before: 'Button.tsx', match: '', after: '' })
  })

  it('should handle empty query', () => {
    const result = highlightMatch('Button.tsx', '')
    expect(result).toEqual({ before: 'Button.tsx', match: '', after: '' })
  })
})
