/**
 * Pure helpers for filtering, grouping, and presenting repository dependencies.
 *
 * Extracted from Dependencies.tsx so the logic can be unit-tested in isolation,
 * independent of React rendering. This module imports only TYPES from the API
 * client — no React or MUI.
 */
import type { DependencyItem } from '@/lib/api'

/** Fallback chip color for unknown/missing languages and types. */
export const DEFAULT_DEPENDENCY_COLOR = '#abb2bf'

// Language colors (One Dark Pro palette, consistent with LogicalView)
export const LANGUAGE_COLORS: Record<string, string> = {
  python: '#61afef',
  javascript: '#e5c07b',
  java: '#d19a66',
  csharp: '#c678dd',
  swift: '#fa7343',
}

// Dependency type colors
export const TYPE_COLORS: Record<string, string> = {
  runtime: '#98c379',
  dev: '#61afef',
  optional: '#e5c07b',
  build: '#d19a66',
  peer: '#c678dd',
}

/** Map a language name to its hex chip color; unknown/missing → default. */
export function getLanguageColor(language: string | null | undefined): string {
  if (!language) return DEFAULT_DEPENDENCY_COLOR
  return LANGUAGE_COLORS[language] ?? DEFAULT_DEPENDENCY_COLOR
}

/** Map a dependency type to its hex chip color; unknown/missing → default. */
export function getTypeColor(type: string | null | undefined): string {
  if (!type) return DEFAULT_DEPENDENCY_COLOR
  return TYPE_COLORS[type] ?? DEFAULT_DEPENDENCY_COLOR
}

export interface FileGroup {
  filePath: string
  fileId: number
  language: string
  items: DependencyItem[]
}

export interface PackageGroup {
  packageName: string
  items: DependencyItem[]
}

export interface DependencyFilters {
  /** Exact language match; null/empty matches all languages. */
  language?: string | null
  /** Exact dependency_type match; null/empty matches all types. */
  type?: string | null
  /** Exact is_direct match; null matches both direct and transitive. */
  direct?: boolean | null
  /** Case-insensitive substring over package name and file path; empty matches all. */
  search?: string
}

/**
 * Filter dependencies by language, type, direct/transitive scope, and a
 * case-insensitive substring over package name and file path. Each predicate is
 * independent; an omitted/empty/null filter is a passthrough. `direct: false`
 * is honored (only `null`/`undefined` disables the scope predicate).
 */
export function filterDependencies(
  items: DependencyItem[],
  filters: DependencyFilters = {}
): DependencyItem[] {
  const { language, type, direct, search } = filters
  let result = items
  if (language) {
    result = result.filter((d) => d.language === language)
  }
  if (type) {
    result = result.filter((d) => d.dependency_type === type)
  }
  if (direct !== null && direct !== undefined) {
    result = result.filter((d) => d.is_direct === direct)
  }
  if (search) {
    const lower = search.toLowerCase()
    result = result.filter(
      (d) =>
        d.package_name.toLowerCase().includes(lower) ||
        (d.file_path ?? '').toLowerCase().includes(lower)
    )
  }
  return result
}

/** Return the sorted set of distinct languages present in the items. */
export function getAvailableLanguages(items: DependencyItem[]): string[] {
  const langs = new Set<string>()
  for (const item of items) {
    if (item.language) langs.add(item.language)
  }
  return [...langs].sort()
}

/** Return the sorted set of distinct dependency types present in the items. */
export function getAvailableTypes(items: DependencyItem[]): string[] {
  const types = new Set<string>()
  for (const item of items) {
    if (item.dependency_type) types.add(item.dependency_type)
  }
  return [...types].sort()
}

/**
 * Group items by manifest file (keyed by file_id), sorted by file path.
 * The group's filePath/language come from the first item seen for that file.
 */
export function groupByFile(items: DependencyItem[]): FileGroup[] {
  const groupMap = new Map<number, FileGroup>()
  for (const item of items) {
    let group = groupMap.get(item.file_id)
    if (!group) {
      group = {
        filePath: item.file_path ?? '',
        fileId: item.file_id,
        language: item.language,
        items: [],
      }
      groupMap.set(item.file_id, group)
    }
    group.items.push(item)
  }
  return [...groupMap.values()].sort((a, b) => a.filePath.localeCompare(b.filePath))
}

/** Group items by package name, preserving sort order of first occurrence. */
export function groupByPackage(items: DependencyItem[]): PackageGroup[] {
  const map = new Map<string, DependencyItem[]>()
  for (const item of items) {
    const existing = map.get(item.package_name)
    if (existing) {
      existing.push(item)
    } else {
      map.set(item.package_name, [item])
    }
  }
  return [...map.entries()].map(([packageName, pkgItems]) => ({
    packageName,
    items: pkgItems,
  }))
}

/** Number of direct dependencies in the list. */
export function countDirect(items: DependencyItem[]): number {
  return items.filter((d) => d.is_direct).length
}

/** Number of transitive (non-direct) dependencies in the list. */
export function countTransitive(items: DependencyItem[]): number {
  return items.filter((d) => !d.is_direct).length
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
