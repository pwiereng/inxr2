import { describe, it, expect } from 'vitest'
import {
  DEFAULT_KIND_COLOR,
  KIND_COLORS,
  getKindColor,
  getKindLabel,
  getAvailableLanguages,
  CONTAINER_KINDS,
  isContainerKind,
  sumKindCounts,
  visibleKinds,
  parentQualifiedName,
  filterFiles,
  filterKindSymbols,
  groupKindSymbols,
  computeSummaryStats,
  fileName,
  fileDir,
} from './logicalView'
import type { Symbol as ApiSymbol, SymbolTreeFile, SymbolTreeSymbol } from '@/lib/api'

function makeFile(overrides: Partial<SymbolTreeFile> = {}): SymbolTreeFile {
  return {
    file_id: 1,
    path: 'src/app.py',
    language: 'python',
    symbol_count: 3,
    kind_counts: {},
    all_kind_counts: {},
    ...overrides,
  }
}

function makeTreeSymbol(overrides: Partial<SymbolTreeSymbol> = {}): SymbolTreeSymbol {
  return {
    id: 1,
    name: 'foo',
    kind: 'function',
    start_line: 1,
    end_line: 2,
    file_path: 'src/app.py',
    has_children: false,
    signature: null,
    inheritance: [],
    ...overrides,
  }
}

function makeApiSymbol(overrides: Partial<ApiSymbol> = {}): ApiSymbol {
  return {
    id: 1,
    name: 'foo',
    qualified_name: null,
    kind: 'function',
    file_id: 1,
    file_path: 'src/app.py',
    repository_id: 1,
    commit_id: 1,
    start_line: 1,
    start_column: 0,
    end_line: 2,
    end_column: 0,
    signature: null,
    docstring: null,
    ...overrides,
  }
}

describe('getKindColor', () => {
  it('returns the mapped color for a known kind', () => {
    expect(getKindColor('class')).toBe('#e5c07b')
    expect(getKindColor('function')).toBe('#61afef')
    expect(getKindColor('enum')).toBe('#c678dd')
    expect(getKindColor('trait')).toBe('#98c379')
  })

  it('falls back to the default color for an unknown kind', () => {
    expect(getKindColor('totally_unknown')).toBe(DEFAULT_KIND_COLOR)
    expect(getKindColor('')).toBe(DEFAULT_KIND_COLOR)
  })

  it('every entry in KIND_COLORS round-trips through getKindColor', () => {
    for (const [kind, color] of Object.entries(KIND_COLORS)) {
      expect(getKindColor(kind)).toBe(color)
    }
  })
})

describe('getKindLabel', () => {
  it('replaces underscores with spaces (singular)', () => {
    expect(getKindLabel('class_variable')).toBe('class variable')
    expect(getKindLabel('function')).toBe('function')
  })

  it('pluralizes -y to -ies (but keeps -ay as -ays)', () => {
    expect(getKindLabel('property', true)).toBe('properties')
    expect(getKindLabel('array', true)).toBe('arrays')
  })

  it('pluralizes -s to -ses', () => {
    expect(getKindLabel('class', true)).toBe('classes')
  })

  it('appends -s for the regular case', () => {
    expect(getKindLabel('method', true)).toBe('methods')
    expect(getKindLabel('instance_variable', true)).toBe('instance variables')
  })

  it('defaults to singular when plural is omitted', () => {
    expect(getKindLabel('method')).toBe('method')
  })
})

describe('getAvailableLanguages', () => {
  it('returns the sorted distinct languages, ignoring null', () => {
    const files = [
      makeFile({ file_id: 1, language: 'typescript' }),
      makeFile({ file_id: 2, language: 'python' }),
      makeFile({ file_id: 3, language: 'python' }),
      makeFile({ file_id: 4, language: null }),
    ]
    expect(getAvailableLanguages(files)).toEqual(['python', 'typescript'])
  })

  it('returns an empty array for no files', () => {
    expect(getAvailableLanguages([])).toEqual([])
  })
})

describe('isContainerKind', () => {
  // Parent kinds that own children in real indexes, per language (#588).
  it.each([
    'class',
    'interface',
    'struct',
    'record',
    'enum',
    'trait',
    'namespace',
    'module',
    'protocol',
    'extension',
    'actor',
    'union',
    'typedef',
    'type',
  ])('%s is a container kind', (kind) => {
    expect(isContainerKind(kind)).toBe(true)
    expect(CONTAINER_KINDS.has(kind)).toBe(true)
  })

  it.each(['function', 'method', 'field', 'property', 'variable', 'constant'])(
    '%s is not a container kind',
    (kind) => {
      expect(isContainerKind(kind)).toBe(false)
    }
  )
})

describe('sumKindCounts', () => {
  it('sums all_kind_counts across files', () => {
    const files = [
      makeFile({ file_id: 1, all_kind_counts: { class: 2, function: 1 } }),
      makeFile({ file_id: 2, all_kind_counts: { class: 3, struct: 4 } }),
    ]
    expect(sumKindCounts(files)).toEqual({ class: 5, function: 1, struct: 4 })
  })

  it('returns an empty map for no files', () => {
    expect(sumKindCounts([])).toEqual({})
  })
})

describe('visibleKinds', () => {
  const files = [
    makeFile({ file_id: 1, language: 'swift', all_kind_counts: { class: 1, protocol: 2 } }),
    makeFile({ file_id: 2, language: 'python', all_kind_counts: { class: 3, function: 5 } }),
  ]
  const availableKinds = ['class', 'function', 'protocol']

  it('returns every available kind with no language filter', () => {
    expect(
      visibleKinds({ availableKinds, files, selectedLanguage: null, activeKind: null })
    ).toEqual(availableKinds)
  })

  it("keeps only the selected language's kinds", () => {
    expect(
      visibleKinds({ availableKinds, files, selectedLanguage: 'swift', activeKind: null })
    ).toEqual(['class', 'protocol'])
    expect(
      visibleKinds({ availableKinds, files, selectedLanguage: 'python', activeKind: null })
    ).toEqual(['class', 'function'])
  })

  it('always keeps the active kind so it can be toggled off', () => {
    expect(
      visibleKinds({ availableKinds, files, selectedLanguage: 'python', activeKind: 'protocol' })
    ).toEqual(['class', 'function', 'protocol'])
  })
})

describe('parentQualifiedName', () => {
  it.each([
    ['Alpha.method', 'Alpha'],
    ['pkg.Mod.Cls.method', 'pkg.Mod.Cls'],
    ['App\\Contracts\\SpotRepository::snapshot', 'App\\Contracts\\SpotRepository'],
    ['App\\Console\\Check::$signature', 'App\\Console\\Check'],
    ['RakefileHelpers::TestFileFilter', 'RakefileHelpers'],
    ['Outer::Inner.method', 'Outer::Inner'],
  ])('%s → %s', (qn, parent) => {
    expect(parentQualifiedName(qn)).toBe(parent)
  })

  it.each([null, '', 'topLevel', '.weird', '::weird'])('%s has no parent', (qn) => {
    expect(parentQualifiedName(qn)).toBeNull()
  })
})

describe('filterFiles', () => {
  const files = [
    makeFile({ file_id: 1, path: 'src/app.py', language: 'python' }),
    makeFile({ file_id: 2, path: 'src/util.ts', language: 'typescript' }),
    makeFile({ file_id: 3, path: 'test/app_test.py', language: 'python' }),
  ]

  it('returns all files when no options are given', () => {
    expect(filterFiles(files)).toEqual(files)
  })

  it('filters by exact language', () => {
    expect(filterFiles(files, { selectedLanguage: 'python' }).map((f) => f.file_id)).toEqual([1, 3])
  })

  it('filters by include text on the path (case-insensitive)', () => {
    expect(filterFiles(files, { filterText: 'UTIL' }).map((f) => f.file_id)).toEqual([2])
  })

  it('include text also matches loaded symbol names', () => {
    const fileSymbols = { 2: [makeTreeSymbol({ name: 'parseThing' })] }
    expect(
      filterFiles(files, { filterText: 'parsething', fileSymbols }).map((f) => f.file_id)
    ).toEqual([2])
  })

  it('exclude text drops files matching path or symbol name', () => {
    const fileSymbols = { 1: [makeTreeSymbol({ name: 'helper' })] }
    expect(
      filterFiles(files, { excludeText: 'helper', fileSymbols }).map((f) => f.file_id)
    ).toEqual([2, 3])
  })

  it('restricts to the symbol-search file-id set', () => {
    const ids = new Set([1, 3])
    expect(filterFiles(files, { symbolSearchMatchFileIds: ids }).map((f) => f.file_id)).toEqual([
      1, 3,
    ])
  })

  it('a null symbol-search set disables the predicate', () => {
    expect(filterFiles(files, { symbolSearchMatchFileIds: null })).toEqual(files)
  })

  it('composes every predicate together', () => {
    const fileSymbols = { 3: [makeTreeSymbol({ name: 'keepme' })] }
    const result = filterFiles(files, {
      selectedLanguage: 'python',
      filterText: 'app',
      excludeText: 'src',
      fileSymbols,
      symbolSearchMatchFileIds: new Set([1, 3]),
    })
    // python ∧ path/symbol has 'app' ∧ not 'src' ∧ id∈{1,3} → only test/app_test.py
    expect(result.map((f) => f.file_id)).toEqual([3])
  })
})

describe('filterKindSymbols', () => {
  const symbols = [
    makeApiSymbol({ id: 1, name: 'render', file_path: 'src/view.tsx' }),
    makeApiSymbol({ id: 2, name: 'parse', file_path: 'src/parser.py' }),
    makeApiSymbol({ id: 3, name: 'renderHelper', file_path: 'src/helpers.py' }),
  ]

  it('returns all symbols when no options are given', () => {
    expect(filterKindSymbols(symbols)).toEqual(symbols)
  })

  // #588: the server already applied `language=`; the client must not drop
  // symbols by re-deriving a language from the path. Every parser-supported
  // extension (and extensionless shebang scripts) survives every filter that
  // doesn't textually exclude it.
  it.each([
    'UI/AlphabetModel.swift',
    'stubs/model.pyi',
    'src/model.mjs',
    'src/model.cjs',
    'src/model.cc',
    'src/model.cxx',
    'src/model.c++',
    'include/model.hpp',
    'include/model.hh',
    'include/model.hxx',
    'include/model.h++',
    'lib/tasks/model.rake',
    'bin/deploy',
  ])('keeps a server-returned symbol from %s', (path) => {
    const syms = [makeApiSymbol({ id: 5, name: 'Target', file_path: path })]
    expect(filterKindSymbols(syms).map((s) => s.id)).toEqual([5])
    expect(
      filterKindSymbols(syms, {
        filterText: 'target',
        excludeText: 'zzz',
        symbolSearch: 'Tar',
      }).map((s) => s.id)
    ).toEqual([5])
  })

  it('filters by include text on name or path', () => {
    expect(filterKindSymbols(symbols, { filterText: 'parser' }).map((s) => s.id)).toEqual([2])
    expect(filterKindSymbols(symbols, { filterText: 'render' }).map((s) => s.id)).toEqual([1, 3])
  })

  it('excludes by text on name or path', () => {
    expect(filterKindSymbols(symbols, { excludeText: 'render' }).map((s) => s.id)).toEqual([2])
  })

  it('symbol search matches name only (not path)', () => {
    expect(filterKindSymbols(symbols, { symbolSearch: 'parse' }).map((s) => s.id)).toEqual([2])
    // 'view' appears in a path but not a name → no matches
    expect(filterKindSymbols(symbols, { symbolSearch: 'view' })).toEqual([])
  })

  it('treats a whitespace-only symbol search as no filter', () => {
    expect(filterKindSymbols(symbols, { symbolSearch: '   ' })).toEqual(symbols)
  })

  it('handles a null file_path under include and exclude text', () => {
    const nullPath = [makeApiSymbol({ id: 7, name: 'orphan', file_path: null })]
    // include matches on name even when the path is null
    expect(filterKindSymbols(nullPath, { filterText: 'orphan' }).map((s) => s.id)).toEqual([7])
    // exclude on a non-matching term keeps the null-path symbol
    expect(filterKindSymbols(nullPath, { excludeText: 'nomatch' }).map((s) => s.id)).toEqual([7])
    // include where neither name nor (null) path matches → dropped
    expect(filterKindSymbols(nullPath, { filterText: 'nomatch' })).toEqual([])
  })

  it('composes include, exclude, and search', () => {
    const result = filterKindSymbols(symbols, {
      filterText: 'render',
      excludeText: '.tsx',
      symbolSearch: 'render',
    })
    expect(result.map((s) => s.id)).toEqual([3])
  })
})

describe('groupKindSymbols', () => {
  it('collects symbols with no parent into a leading ungrouped group', () => {
    const symbols = [
      makeApiSymbol({ id: 1, name: 'topLevel', qualified_name: 'topLevel' }),
      makeApiSymbol({ id: 2, name: 'another', qualified_name: null }),
    ]
    const groups = groupKindSymbols(symbols)
    expect(groups).toHaveLength(1)
    expect(groups[0]!.groupKey).toBe('__ungrouped')
    expect(groups[0]!.className).toBeNull()
    expect(groups[0]!.symbols.map((s) => s.id)).toEqual([1, 2])
  })

  it('groups symbols by parent class from qualified_name', () => {
    const symbols = [
      makeApiSymbol({
        id: 1,
        name: 'method_a',
        qualified_name: 'Beta.method_a',
        file_path: 'b.py',
      }),
      makeApiSymbol({
        id: 2,
        name: 'method_b',
        qualified_name: 'Alpha.method_b',
        file_path: 'a.py',
      }),
      makeApiSymbol({
        id: 3,
        name: 'method_c',
        qualified_name: 'Alpha.method_c',
        file_path: 'a.py',
      }),
    ]
    const groups = groupKindSymbols(symbols)
    // Sorted by "ClassName::filePath" key → Alpha before Beta
    expect(groups.map((g) => g.className)).toEqual(['Alpha', 'Beta'])
    expect(groups[0]!.symbols.map((s) => s.id)).toEqual([2, 3])
    expect(groups[0]!.filePath).toBe('a.py')
    expect(groups[1]!.symbols.map((s) => s.id)).toEqual([1])
  })

  it('separates same-named classes living in different files', () => {
    const symbols = [
      makeApiSymbol({ id: 1, qualified_name: 'Foo.a', file_path: 'one.py' }),
      makeApiSymbol({ id: 2, qualified_name: 'Foo.b', file_path: 'two.py' }),
    ]
    const groups = groupKindSymbols(symbols)
    expect(groups).toHaveLength(2)
    expect(groups.map((g) => g.filePath)).toEqual(['one.py', 'two.py'])
  })

  it('places ungrouped symbols before class groups', () => {
    const symbols = [
      makeApiSymbol({ id: 1, qualified_name: 'Zeta.m', file_path: 'z.py' }),
      makeApiSymbol({ id: 2, qualified_name: 'free_func' }),
    ]
    const groups = groupKindSymbols(symbols)
    expect(groups[0]!.groupKey).toBe('__ungrouped')
    expect(groups[1]!.className).toBe('Zeta')
  })

  it('groups a parented symbol that has a null file_path under an empty path key', () => {
    const groups = groupKindSymbols([
      makeApiSymbol({ id: 1, qualified_name: 'Cls.m', file_path: null }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0]!.className).toBe('Cls')
    expect(groups[0]!.filePath).toBeNull()
  })

  it('groups PHP members under their class via the :: separator', () => {
    const groups = groupKindSymbols([
      makeApiSymbol({
        id: 1,
        qualified_name: 'App\\Repo::find',
        file_path: 'app/Repo.php',
      }),
      makeApiSymbol({
        id: 2,
        qualified_name: 'App\\Repo::save',
        file_path: 'app/Repo.php',
      }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0]!.className).toBe('App\\Repo')
    expect(groups[0]!.symbols.map((s) => s.id)).toEqual([1, 2])
  })

  it('treats a leading-dot qualified name (dotIdx 0) as ungrouped', () => {
    const groups = groupKindSymbols([makeApiSymbol({ id: 1, qualified_name: '.weird' })])
    expect(groups[0]!.groupKey).toBe('__ungrouped')
  })

  it('uses a nested qualified name down to the last dot as the parent', () => {
    const symbols = [
      makeApiSymbol({ id: 1, qualified_name: 'pkg.Mod.Cls.method', file_path: 'm.py' }),
    ]
    const groups = groupKindSymbols(symbols)
    expect(groups[0]!.className).toBe('pkg.Mod.Cls')
  })

  it('returns an empty array for no symbols', () => {
    expect(groupKindSymbols([])).toEqual([])
  })
})

describe('computeSummaryStats', () => {
  const files = [
    makeFile({ file_id: 1, language: 'python', all_kind_counts: { class: 3, function: 7 } }),
    makeFile({ file_id: 2, language: 'swift', all_kind_counts: { class: 2, struct: 1 } }),
  ]

  it("sums the shown files' kind counts in outline mode (no active kind)", () => {
    const stats = computeSummaryStats({
      activeKind: null,
      filteredFiles: files,
      filteredKindSymbolsCount: 0,
    })
    expect(stats).toEqual({ files: 2, kinds: { class: 5, function: 7, struct: 1 } })
  })

  it('narrows outline-mode counts to the filtered files (e.g. a language filter)', () => {
    const stats = computeSummaryStats({
      activeKind: null,
      filteredFiles: files.filter((f) => f.language === 'swift'),
      filteredKindSymbolsCount: 0,
    })
    expect(stats).toEqual({ files: 1, kinds: { class: 2, struct: 1 } })
  })

  it('reports only the active kind count in kind mode', () => {
    const stats = computeSummaryStats({
      activeKind: 'function',
      filteredFiles: files,
      filteredKindSymbolsCount: 12,
    })
    expect(stats).toEqual({ files: 2, kinds: { function: 12 } })
  })

  it('omits the kinds entry when the active kind has zero matches', () => {
    const stats = computeSummaryStats({
      activeKind: 'function',
      filteredFiles: files,
      filteredKindSymbolsCount: 0,
    })
    expect(stats).toEqual({ files: 2, kinds: {} })
  })
})

describe('fileName', () => {
  it('returns the final path segment', () => {
    expect(fileName('src/lib/app.py')).toBe('app.py')
  })

  it('returns the input when there is no slash', () => {
    expect(fileName('app.py')).toBe('app.py')
  })
})

describe('fileDir', () => {
  it('returns the directory portion with a trailing slash', () => {
    expect(fileDir('src/lib/app.py')).toBe('src/lib/')
  })

  it('returns an empty string for a root-level file', () => {
    expect(fileDir('app.py')).toBe('')
  })
})
