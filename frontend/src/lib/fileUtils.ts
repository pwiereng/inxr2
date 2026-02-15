/**
 * File utility functions for determining file types.
 */

const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.bmp'])

const MARKDOWN_EXTENSIONS = new Set(['.md', '.markdown', '.mdown', '.mkd'])

/**
 * Check if a file path points to an image file based on its extension.
 */
export function isImageFile(path: string): boolean {
  const lastDot = path.lastIndexOf('.')
  if (lastDot === -1) return false
  const ext = path.substring(lastDot).toLowerCase()
  return IMAGE_EXTENSIONS.has(ext)
}

/**
 * Check if a file is markdown based on language field or file extension.
 */
export function isMarkdownFile(path: string, language: string | null): boolean {
  if (language === 'markdown') return true
  const lastDot = path.lastIndexOf('.')
  if (lastDot === -1) return false
  const ext = path.substring(lastDot).toLowerCase()
  return MARKDOWN_EXTENSIONS.has(ext)
}

/**
 * Map file extension to language name for syntax highlighting.
 * Used as fallback when the API returns language: null.
 */
const EXTENSION_LANGUAGE_MAP: Record<string, string> = {
  '.py': 'python',
  '.pyi': 'python',
  '.js': 'javascript',
  '.jsx': 'javascript',
  '.mjs': 'javascript',
  '.ts': 'typescript',
  '.tsx': 'typescript',
  '.mts': 'typescript',
  '.json': 'json',
  '.yaml': 'yaml',
  '.yml': 'yaml',
  '.toml': 'toml',
  '.ini': 'ini',
  '.cfg': 'ini',
  '.html': 'html',
  '.htm': 'html',
  '.xml': 'xml',
  '.svg': 'svg',
  '.css': 'css',
  '.scss': 'scss',
  '.sass': 'sass',
  '.less': 'less',
  '.sql': 'sql',
  '.c': 'c',
  '.h': 'c',
  '.cpp': 'cpp',
  '.cc': 'cpp',
  '.hpp': 'cpp',
  '.java': 'java',
  '.cs': 'csharp',
  '.go': 'go',
  '.rs': 'rust',
  '.rb': 'ruby',
  '.php': 'php',
  '.swift': 'swift',
  '.kt': 'kotlin',
  '.scala': 'scala',
  '.sh': 'bash',
  '.bash': 'bash',
  '.zsh': 'bash',
  '.md': 'markdown',
  '.markdown': 'markdown',
  '.mk': 'makefile',
}

const FILENAME_LANGUAGE_MAP: Record<string, string> = {
  Dockerfile: 'dockerfile',
  'Dockerfile.dev': 'dockerfile',
  Makefile: 'makefile',
}

/**
 * Detect language from file path, with API language as priority.
 * Falls back to file extension/name detection when API returns null.
 */
export function detectLanguage(path: string, apiLanguage: string | null): string | null {
  if (apiLanguage) return apiLanguage
  const fileName = path.split('/').pop() ?? ''
  if (FILENAME_LANGUAGE_MAP[fileName]) return FILENAME_LANGUAGE_MAP[fileName]
  const lastDot = fileName.lastIndexOf('.')
  if (lastDot === -1) return null
  const ext = fileName.substring(lastDot).toLowerCase()
  return EXTENSION_LANGUAGE_MAP[ext] ?? null
}
