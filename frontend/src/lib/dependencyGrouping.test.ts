import { describe, it, expect } from 'vitest'
import type { DependencyItem } from '@/lib/api'
import {
  DEFAULT_DEPENDENCY_COLOR,
  LANGUAGE_COLORS,
  TYPE_COLORS,
  getLanguageColor,
  getTypeColor,
  filterDependencies,
  getAvailableLanguages,
  getAvailableTypes,
  groupByFile,
  groupByPackage,
  countDirect,
  countTransitive,
  fileName,
  fileDir,
} from './dependencyGrouping'

/** Build a DependencyItem with sensible defaults, overridable per field. */
function makeItem(overrides: Partial<DependencyItem> = {}): DependencyItem {
  return {
    id: 1,
    package_name: 'requests',
    language: 'python',
    version_spec: '>=2.0',
    resolved_version: '2.31.0',
    dependency_type: 'runtime',
    is_direct: true,
    file_id: 10,
    file_path: 'requirements.txt',
    source_line: 1,
    ...overrides,
  }
}

describe('getLanguageColor', () => {
  it('returns the mapped color for a known language', () => {
    expect(getLanguageColor('python')).toBe(LANGUAGE_COLORS.python)
    expect(getLanguageColor('swift')).toBe('#fa7343')
  })

  it('returns the default for an unknown language', () => {
    expect(getLanguageColor('cobol')).toBe(DEFAULT_DEPENDENCY_COLOR)
  })

  it('returns the default for null/undefined/empty', () => {
    expect(getLanguageColor(null)).toBe(DEFAULT_DEPENDENCY_COLOR)
    expect(getLanguageColor(undefined)).toBe(DEFAULT_DEPENDENCY_COLOR)
    expect(getLanguageColor('')).toBe(DEFAULT_DEPENDENCY_COLOR)
  })
})

describe('getTypeColor', () => {
  it('returns the mapped color for a known type', () => {
    expect(getTypeColor('runtime')).toBe(TYPE_COLORS.runtime)
    expect(getTypeColor('peer')).toBe('#c678dd')
  })

  it('returns the default for an unknown type', () => {
    expect(getTypeColor('mystery')).toBe(DEFAULT_DEPENDENCY_COLOR)
  })

  it('returns the default for null/undefined/empty', () => {
    expect(getTypeColor(null)).toBe(DEFAULT_DEPENDENCY_COLOR)
    expect(getTypeColor(undefined)).toBe(DEFAULT_DEPENDENCY_COLOR)
    expect(getTypeColor('')).toBe(DEFAULT_DEPENDENCY_COLOR)
  })
})

describe('filterDependencies', () => {
  const items = [
    makeItem({
      id: 1,
      package_name: 'requests',
      language: 'python',
      dependency_type: 'runtime',
      is_direct: true,
      file_path: 'requirements.txt',
    }),
    makeItem({
      id: 2,
      package_name: 'pytest',
      language: 'python',
      dependency_type: 'dev',
      is_direct: true,
      file_path: 'requirements-dev.txt',
    }),
    makeItem({
      id: 3,
      package_name: 'lodash',
      language: 'javascript',
      dependency_type: 'runtime',
      is_direct: false,
      file_path: 'package.json',
    }),
    makeItem({
      id: 4,
      package_name: 'urllib3',
      language: 'python',
      dependency_type: 'runtime',
      is_direct: false,
      file_path: 'requirements.txt',
    }),
  ]

  it('returns all items when no filters are given', () => {
    expect(filterDependencies(items)).toEqual(items)
    expect(filterDependencies(items, {})).toEqual(items)
  })

  it('filters by language alone', () => {
    const result = filterDependencies(items, { language: 'javascript' })
    expect(result.map((d) => d.id)).toEqual([3])
  })

  it('filters by type alone', () => {
    const result = filterDependencies(items, { type: 'dev' })
    expect(result.map((d) => d.id)).toEqual([2])
  })

  it('filters by direct=true alone', () => {
    const result = filterDependencies(items, { direct: true })
    expect(result.map((d) => d.id)).toEqual([1, 2])
  })

  it('honors falsy-but-valid direct=false', () => {
    const result = filterDependencies(items, { direct: false })
    expect(result.map((d) => d.id)).toEqual([3, 4])
  })

  it('treats direct=null as no scope filter', () => {
    expect(filterDependencies(items, { direct: null })).toEqual(items)
  })

  it('filters by search over package name (case-insensitive)', () => {
    const result = filterDependencies(items, { search: 'REQUEST' })
    expect(result.map((d) => d.id)).toEqual([1])
  })

  it('filters by search over file path', () => {
    const result = filterDependencies(items, { search: 'package.json' })
    expect(result.map((d) => d.id)).toEqual([3])
  })

  it('treats a null file_path as an empty string for search', () => {
    const withNullPath = [makeItem({ id: 9, package_name: 'foo', file_path: null })]
    expect(filterDependencies(withNullPath, { search: 'foo' }).map((d) => d.id)).toEqual([9])
    expect(filterDependencies(withNullPath, { search: 'nomatch' })).toEqual([])
  })

  it('composes multiple predicates', () => {
    const result = filterDependencies(items, {
      language: 'python',
      type: 'runtime',
      direct: false,
    })
    expect(result.map((d) => d.id)).toEqual([4])
  })

  it('returns an empty array when nothing matches', () => {
    expect(filterDependencies(items, { language: 'rust' })).toEqual([])
  })

  it('does not mutate the input array', () => {
    const copy = [...items]
    filterDependencies(items, { language: 'python' })
    expect(items).toEqual(copy)
  })
})

describe('getAvailableLanguages', () => {
  it('returns distinct, sorted languages', () => {
    const items = [
      makeItem({ language: 'python' }),
      makeItem({ language: 'javascript' }),
      makeItem({ language: 'python' }),
      makeItem({ language: 'csharp' }),
    ]
    expect(getAvailableLanguages(items)).toEqual(['csharp', 'javascript', 'python'])
  })

  it('excludes empty languages', () => {
    const items = [makeItem({ language: 'python' }), makeItem({ language: '' })]
    expect(getAvailableLanguages(items)).toEqual(['python'])
  })

  it('returns an empty array for no items', () => {
    expect(getAvailableLanguages([])).toEqual([])
  })
})

describe('getAvailableTypes', () => {
  it('returns distinct, sorted types', () => {
    const items = [
      makeItem({ dependency_type: 'runtime' }),
      makeItem({ dependency_type: 'dev' }),
      makeItem({ dependency_type: 'runtime' }),
    ]
    expect(getAvailableTypes(items)).toEqual(['dev', 'runtime'])
  })

  it('excludes empty types', () => {
    const items = [makeItem({ dependency_type: 'runtime' }), makeItem({ dependency_type: '' })]
    expect(getAvailableTypes(items)).toEqual(['runtime'])
  })

  it('returns an empty array for no items', () => {
    expect(getAvailableTypes([])).toEqual([])
  })
})

describe('groupByFile', () => {
  it('groups items by file_id and sorts by file path', () => {
    const items = [
      makeItem({ id: 1, file_id: 20, file_path: 'package.json', language: 'javascript' }),
      makeItem({ id: 2, file_id: 10, file_path: 'requirements.txt', language: 'python' }),
      makeItem({ id: 3, file_id: 10, file_path: 'requirements.txt', language: 'python' }),
    ]
    const groups = groupByFile(items)
    expect(groups.map((g) => g.filePath)).toEqual(['package.json', 'requirements.txt'])
    const reqGroup = groups.find((g) => g.fileId === 10)
    expect(reqGroup?.items.map((i) => i.id)).toEqual([2, 3])
    expect(reqGroup?.language).toBe('python')
  })

  it('falls back to an empty filePath when file_path is null', () => {
    const groups = groupByFile([makeItem({ file_id: 5, file_path: null })])
    expect(groups[0]?.filePath).toBe('')
    expect(groups[0]?.fileId).toBe(5)
  })

  it('returns an empty array for no items', () => {
    expect(groupByFile([])).toEqual([])
  })
})

describe('groupByPackage', () => {
  it('groups items by package name preserving first-occurrence order', () => {
    const items = [
      makeItem({ id: 1, package_name: 'requests' }),
      makeItem({ id: 2, package_name: 'lodash' }),
      makeItem({ id: 3, package_name: 'requests' }),
    ]
    const groups = groupByPackage(items)
    expect(groups.map((g) => g.packageName)).toEqual(['requests', 'lodash'])
    expect(groups[0]?.items.map((i) => i.id)).toEqual([1, 3])
    expect(groups[1]?.items.map((i) => i.id)).toEqual([2])
  })

  it('returns an empty array for no items', () => {
    expect(groupByPackage([])).toEqual([])
  })
})

describe('countDirect / countTransitive', () => {
  const items = [
    makeItem({ is_direct: true }),
    makeItem({ is_direct: true }),
    makeItem({ is_direct: false }),
  ]

  it('counts direct dependencies', () => {
    expect(countDirect(items)).toBe(2)
  })

  it('counts transitive dependencies', () => {
    expect(countTransitive(items)).toBe(1)
  })

  it('returns zero for empty input', () => {
    expect(countDirect([])).toBe(0)
    expect(countTransitive([])).toBe(0)
  })
})

describe('fileName', () => {
  it('returns the final segment of a nested path', () => {
    expect(fileName('src/lib/package.json')).toBe('package.json')
  })

  it('returns the input for a root-level file', () => {
    expect(fileName('requirements.txt')).toBe('requirements.txt')
  })

  it('returns an empty string for a trailing slash', () => {
    expect(fileName('src/lib/')).toBe('')
  })
})

describe('fileDir', () => {
  it('returns the directory with a trailing slash for a nested path', () => {
    expect(fileDir('src/lib/package.json')).toBe('src/lib/')
  })

  it('returns an empty string for a root-level file', () => {
    expect(fileDir('requirements.txt')).toBe('')
  })

  it('returns the directory for a trailing-slash path', () => {
    expect(fileDir('src/lib/')).toBe('src/lib/')
  })
})
