/**
 * Pure helpers for filtering, grouping, and presenting the LogicalView symbol
 * tree.
 *
 * Extracted from LogicalView.tsx so the logic can be unit-tested in isolation,
 * independent of React rendering. This module imports only TYPES from the API
 * client — no React or MUI. Kept as a per-page module (not a shared lib) so it
 * never collides with parallel page refactors.
 */
import type { Symbol as ApiSymbol, SymbolTreeFile, SymbolTreeSymbol } from '@/lib/api'

/** Fallback chip color for unknown/missing kinds. */
export const DEFAULT_KIND_COLOR = '#abb2bf'

// Symbol kind colors (One Dark Pro palette).
export const KIND_COLORS: Record<string, string> = {
  class: '#e5c07b',
  interface: '#56b6c2',
  struct: '#d19a66',
  record: '#d19a66',
  enum: '#c678dd',
  trait: '#98c379',
  function: '#61afef',
  method: '#61afef',
  staticmethod: '#61afef',
  classmethod: '#61afef',
  constant: '#d19a66',
  variable: '#abb2bf',
  class_variable: '#d19a66',
  instance_variable: '#abb2bf',
  field: '#abb2bf',
  property: '#abb2bf',
}

/** Map a symbol kind to its hex chip color; unknown/missing → default. */
export function getKindColor(kind: string): string {
  return KIND_COLORS[kind] ?? DEFAULT_KIND_COLOR
}

/**
 * Human-readable label for a symbol kind. Underscores become spaces; when
 * `plural` is true the label is naively pluralized (handling -y → -ies and
 * -s → -ses, with -ay kept as -ays).
 */
export function getKindLabel(kind: string, plural = false): string {
  const label = kind.replace(/_/g, ' ')
  if (!plural) return label
  if (label.endsWith('y') && !label.endsWith('ay')) return label.slice(0, -1) + 'ies'
  if (label.endsWith('s')) return label + 'es'
  return label + 's'
}

/** Cache of a file's loaded child symbols, keyed by parent symbol id. */
export interface SymbolChildren {
  [parentId: number]: SymbolTreeSymbol[]
}

/** Return the sorted set of distinct languages present in the files. */
export function getAvailableLanguages(files: SymbolTreeFile[]): string[] {
  const langs = new Set<string>()
  for (const f of files) {
    if (f.language) langs.add(f.language)
  }
  return [...langs].sort()
}

/**
 * Symbol kinds that can own child symbols (members, nested types), so a
 * kind-mode row of that kind is expandable. Kind-mode symbols carry no
 * `has_children`, so this list is the only signal: a kind belongs here only if
 * its rows usually have children. Swift protocol/extension/actor, Ruby module
 * and C/C++ union do (#588). `type` and `typedef` are deliberately excluded:
 * in real indexes only ~1-3% have children (e.g. C `typedef struct {...}`), so
 * they would mostly show a chevron that opens to nothing. Those few children
 * stay reachable in Outline mode, which uses the API's `has_children`.
 */
export const CONTAINER_KINDS: ReadonlySet<string> = new Set([
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
])

/** Whether a symbol of this kind can have child symbols. */
export function isContainerKind(kind: string): boolean {
  return CONTAINER_KINDS.has(kind)
}

/**
 * Sum per-file kind counts (`all_kind_counts`) across the given files. Used so
 * the summary bar and kind chips reflect the files currently shown (e.g. under
 * a language filter) rather than repo-wide totals.
 */
export function sumKindCounts(files: SymbolTreeFile[]): Record<string, number> {
  const totals: Record<string, number> = {}
  for (const f of files) {
    for (const [kind, count] of Object.entries(f.all_kind_counts)) {
      totals[kind] = (totals[kind] ?? 0) + count
    }
  }
  return totals
}

/**
 * The kind chips to show: every backend-reported kind, or — under a language
 * filter — only kinds that language's files actually contain. The active kind
 * is always kept so the user can toggle it off.
 */
export function visibleKinds(options: {
  availableKinds: string[]
  files: SymbolTreeFile[]
  selectedLanguage: string | null
  activeKind: string | null
}): string[] {
  const { availableKinds, files, selectedLanguage, activeKind } = options
  if (!selectedLanguage) return availableKinds
  const counts = sumKindCounts(files.filter((f) => f.language === selectedLanguage))
  return availableKinds.filter((k) => (counts[k] ?? 0) > 0 || k === activeKind)
}

export interface FileFilterOptions {
  /** Exact language match; null/empty matches all languages. */
  selectedLanguage?: string | null
  /** Case-insensitive substring over path or loaded symbol names; empty matches all. */
  filterText?: string
  /** Case-insensitive substring that excludes matching files; empty matches all. */
  excludeText?: string
  /** Loaded symbols per file id, used by the include/exclude text predicates. */
  fileSymbols?: Record<number, SymbolTreeSymbol[]>
  /** Restrict to files whose id is in this set; null disables the predicate. */
  symbolSearchMatchFileIds?: Set<number> | null
}

/**
 * Filter outline-mode files by language, an inclusive text substring (path or
 * loaded symbol names), an exclusive text substring, and an optional
 * symbol-search file-id set. Each predicate is independent; an omitted/empty/null
 * filter is a passthrough.
 */
export function filterFiles(
  files: SymbolTreeFile[],
  options: FileFilterOptions = {}
): SymbolTreeFile[] {
  const {
    selectedLanguage,
    filterText,
    excludeText,
    fileSymbols = {},
    symbolSearchMatchFileIds,
  } = options
  let result = files
  if (selectedLanguage) {
    result = result.filter((f) => f.language === selectedLanguage)
  }
  if (filterText) {
    const lower = filterText.toLowerCase()
    result = result.filter(
      (f) =>
        f.path.toLowerCase().includes(lower) ||
        (fileSymbols[f.file_id] ?? []).some((s) => s.name.toLowerCase().includes(lower))
    )
  }
  if (excludeText) {
    const lower = excludeText.toLowerCase()
    result = result.filter(
      (f) =>
        !f.path.toLowerCase().includes(lower) &&
        !(fileSymbols[f.file_id] ?? []).some((s) => s.name.toLowerCase().includes(lower))
    )
  }
  if (symbolSearchMatchFileIds) {
    result = result.filter((f) => symbolSearchMatchFileIds.has(f.file_id))
  }
  return result
}

/**
 * Kind-mode filters applied client-side. There is deliberately no language
 * option: the kind-mode fetch passes `language=` to the server, which filters on
 * `files.language` as assigned at index time (extension + shebang detection).
 * Re-deriving the language from the path here drifted from the backend and
 * dropped every Swift symbol, among others (#588).
 */
export interface KindSymbolFilterOptions {
  /** Case-insensitive substring over name or file path; empty matches all. */
  filterText?: string
  /** Case-insensitive substring that excludes matching symbols; empty matches all. */
  excludeText?: string
  /** Case-insensitive substring over name only; empty matches all. */
  symbolSearch?: string
}

/**
 * Filter kind-mode symbols by an inclusive text substring (name or path), an
 * exclusive text substring, and a name-only symbol search. Each predicate is independent; an omitted/empty/null
 * filter is a passthrough.
 */
export function filterKindSymbols(
  symbols: ApiSymbol[],
  options: KindSymbolFilterOptions = {}
): ApiSymbol[] {
  const { filterText, excludeText, symbolSearch } = options
  let result = symbols
  if (filterText) {
    const lower = filterText.toLowerCase()
    result = result.filter(
      (s) =>
        s.name.toLowerCase().includes(lower) ||
        (s.file_path?.toLowerCase().includes(lower) ?? false)
    )
  }
  if (excludeText) {
    const lower = excludeText.toLowerCase()
    result = result.filter(
      (s) =>
        !s.name.toLowerCase().includes(lower) &&
        !(s.file_path?.toLowerCase().includes(lower) ?? false)
    )
  }
  if (symbolSearch && symbolSearch.trim()) {
    const lower = symbolSearch.trim().toLowerCase()
    result = result.filter((s) => s.name.toLowerCase().includes(lower))
  }
  return result
}

export interface KindSymbolGroup {
  groupKey: string
  className: string | null
  filePath: string | null
  symbols: ApiSymbol[]
}

/**
 * The parent portion of a qualified name, split on the last `.` or `::`
 * separator (PHP `App\Foo::bar`, Ruby `Mod::Klass`, everything else `A.b`).
 * Returns null when there is no parent.
 */
export function parentQualifiedName(qualifiedName: string | null): string | null {
  if (!qualifiedName) return null
  const idx = Math.max(qualifiedName.lastIndexOf('.'), qualifiedName.lastIndexOf('::'))
  return idx > 0 ? qualifiedName.slice(0, idx) : null
}

/**
 * Group kind-mode symbols by their parent class, derived from the qualified
 * name (`"ClassName.method"` / `"ClassName::method"` → `"ClassName"`). Symbols with no parent are
 * collected into a single leading `__ungrouped` group; the remaining groups are
 * sorted by their `parentName::filePath` key. The group key disambiguates
 * same-named classes living in different files.
 */
export function groupKindSymbols(symbols: ApiSymbol[]): KindSymbolGroup[] {
  const groups: KindSymbolGroup[] = []
  const groupMap = new Map<string, { filePath: string | null; symbols: ApiSymbol[] }>()
  const ungrouped: ApiSymbol[] = []

  for (const sym of symbols) {
    const parentName = parentQualifiedName(sym.qualified_name)

    if (parentName) {
      const key = `${parentName}::${sym.file_path ?? ''}`
      const existing = groupMap.get(key)
      if (existing) {
        existing.symbols.push(sym)
      } else {
        groupMap.set(key, { filePath: sym.file_path, symbols: [sym] })
      }
    } else {
      ungrouped.push(sym)
    }
  }

  if (ungrouped.length > 0) {
    groups.push({ groupKey: '__ungrouped', className: null, filePath: null, symbols: ungrouped })
  }
  const sortedEntries = [...groupMap.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  for (const [key, group] of sortedEntries) {
    groups.push({
      groupKey: key,
      className: key.split('::')[0]!,
      filePath: group.filePath,
      symbols: group.symbols,
    })
  }

  return groups
}

export interface SummaryStats {
  files: number
  kinds: Record<string, number>
}

/**
 * Compute the summary-bar stats. In kind mode the kinds map holds only the
 * active kind's filtered count (omitted entirely when zero); otherwise it sums
 * the per-kind counts of the files currently shown, so a language or text
 * filter narrows the counts along with the file list.
 */
export function computeSummaryStats(options: {
  activeKind: string | null
  filteredFiles: SymbolTreeFile[]
  filteredKindSymbolsCount: number
}): SummaryStats {
  const { activeKind, filteredFiles, filteredKindSymbolsCount } = options
  const files = filteredFiles.length
  if (activeKind) {
    const count = filteredKindSymbolsCount
    return { files, kinds: count > 0 ? { [activeKind]: count } : {} }
  }
  return { files, kinds: sumKindCounts(filteredFiles) }
}

/** The final path segment (file name); returns the input if there is no slash. */
export function fileName(path: string): string {
  const parts = path.split('/')
  return parts[parts.length - 1] ?? path
}

/**
 * The directory portion of a path, with a trailing slash; empty string for a
 * root-level file (no slash).
 */
export function fileDir(path: string): string {
  const parts = path.split('/')
  if (parts.length <= 1) return ''
  return parts.slice(0, -1).join('/') + '/'
}
