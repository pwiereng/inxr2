/**
 * Shared Prism.js language imports and mapping.
 *
 * Both CodeViewer and DiffCodeViewer use this module to avoid
 * duplicating language imports and the language map.
 */
import 'prismjs'
import 'prismjs/components/prism-python'
import 'prismjs/components/prism-typescript'
import 'prismjs/components/prism-javascript'
import 'prismjs/components/prism-jsx'
import 'prismjs/components/prism-tsx'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-yaml'
import 'prismjs/components/prism-bash'
import 'prismjs/components/prism-markdown'
import 'prismjs/components/prism-css'
import 'prismjs/components/prism-sql'
import 'prismjs/components/prism-c'
import 'prismjs/components/prism-java'
import 'prismjs/components/prism-csharp'
// Additional languages
import 'prismjs/components/prism-go'
import 'prismjs/components/prism-rust'
import 'prismjs/components/prism-ruby'
import 'prismjs/components/prism-markup'
import 'prismjs/components/prism-markup-templating'
import 'prismjs/components/prism-php'
import 'prismjs/components/prism-scss'
import 'prismjs/components/prism-sass'
import 'prismjs/components/prism-less'
import 'prismjs/components/prism-toml'
import 'prismjs/components/prism-ini'
import 'prismjs/components/prism-docker'
import 'prismjs/components/prism-makefile'
import 'prismjs/components/prism-kotlin'
import 'prismjs/components/prism-scala'
import 'prismjs/components/prism-swift'
import 'prismjs/components/prism-cpp'

/**
 * Map backend language names to Prism grammar names.
 */
export const languageMap: Record<string, string> = {
  // Original languages
  python: 'python',
  typescript: 'typescript',
  javascript: 'javascript',
  tsx: 'tsx',
  jsx: 'jsx',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  bash: 'bash',
  sh: 'bash',
  shell: 'bash',
  zsh: 'bash',
  markdown: 'markdown',
  md: 'markdown',
  css: 'css',
  sql: 'sql',
  c: 'c',
  java: 'java',
  csharp: 'csharp',
  cs: 'csharp',
  // Newly added
  go: 'go',
  rust: 'rust',
  ruby: 'ruby',
  php: 'php',
  html: 'markup',
  xml: 'markup',
  svg: 'markup',
  markup: 'markup',
  scss: 'scss',
  sass: 'sass',
  less: 'less',
  toml: 'toml',
  ini: 'ini',
  dockerfile: 'docker',
  docker: 'docker',
  makefile: 'makefile',
  kotlin: 'kotlin',
  scala: 'scala',
  swift: 'swift',
  cpp: 'cpp',
}

/**
 * Get the Prism grammar name for a given language.
 *
 * @param language - Backend language name (case-insensitive), or null
 * @returns Prism grammar name, or 'text' if no mapping exists
 */
export function getPrismLanguage(language: string | null): string {
  if (!language) return 'text'
  return languageMap[language.toLowerCase()] ?? 'text'
}
