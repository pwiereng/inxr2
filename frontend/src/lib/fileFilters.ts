/**
 * Pure helpers for filtering and presenting the repository file list.
 *
 * Extracted from Files.tsx so the logic can be unit-tested in isolation,
 * independent of React rendering.
 */
import type { FileInfo } from '@/lib/api'

export type LanguageColor = 'primary' | 'secondary' | 'default'

const LANGUAGE_COLORS: Record<string, 'primary' | 'secondary'> = {
  python: 'primary',
  javascript: 'secondary',
  typescript: 'primary',
  java: 'secondary',
  go: 'primary',
  rust: 'secondary',
}

/**
 * Map a language name to a MUI chip color. Case-insensitive; unknown or
 * missing languages fall back to 'default'.
 */
export function getLanguageColor(language: string | null): LanguageColor {
  if (!language) return 'default'
  return LANGUAGE_COLORS[language.toLowerCase()] ?? 'default'
}

/**
 * Return the sorted set of distinct, non-empty languages present in the files.
 */
export function getUniqueLanguages(files: FileInfo[]): string[] {
  return Array.from(
    new Set(files.map((f) => f.language).filter((l): l is string => Boolean(l)))
  ).sort()
}

/**
 * Filter files by a case-insensitive path substring and an exact language match.
 * An empty search term matches all paths; an empty language matches all languages.
 */
export function filterFiles(
  files: FileInfo[],
  searchTerm: string,
  filterLanguage: string
): FileInfo[] {
  const needle = searchTerm.toLowerCase()
  return files.filter((file) => {
    const matchesSearch = file.path.toLowerCase().includes(needle)
    const matchesLanguage = !filterLanguage || file.language === filterLanguage
    return matchesSearch && matchesLanguage
  })
}
