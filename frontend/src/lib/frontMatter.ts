/**
 * YAML front matter extraction for the Markdown viewer (#553).
 *
 * Without this, a leading `---\n...\n---` block reaches the markdown renderer,
 * which parses the closing `---` as a setext heading underline and renders the
 * YAML as an <h2>. Like GitHub, the block is only recognised at the very start
 * of the file and must be terminated; anything else is left to the renderer.
 *
 * Only simple top-level `key: value` mappings are turned into entries (for a
 * metadata table). This is deliberately not a YAML parser — nested or
 * multi-line values are folded into the preceding key as text, and anything
 * that isn't a mapping yields `entries: null` so callers can show it raw.
 */

export interface FrontMatterEntry {
  key: string
  value: string
}

export interface FrontMatter {
  raw: string
  entries: FrontMatterEntry[] | null
}

export interface SplitFrontMatterResult {
  frontMatter: FrontMatter | null
  body: string
}

const OPEN_RE = /^\uFEFF?---[ \t]*\r?\n/
const CLOSE_RE = /^(?:---|\.\.\.)[ \t]*$/
const KEY_VALUE_RE = /^([^\s#:][^:]*?):(?:[ \t]+(.*))?$/

export function splitFrontMatter(content: string): SplitFrontMatterResult {
  const open = OPEN_RE.exec(content)
  if (!open) return { frontMatter: null, body: content }

  // Walk line by line, tracking offsets so the body keeps its original line endings.
  let offset = open[0].length
  const lines: string[] = []
  while (offset <= content.length) {
    const newline = content.indexOf('\n', offset)
    const end = newline === -1 ? content.length : newline
    const line = content.slice(offset, end).replace(/\r$/, '')
    const next = newline === -1 ? content.length : newline + 1

    if (CLOSE_RE.test(line)) {
      const raw = lines.join('\n')
      return { frontMatter: { raw, entries: parseEntries(lines) }, body: content.slice(next) }
    }
    if (newline === -1) break
    lines.push(line)
    offset = next
  }

  // Unterminated: not front matter.
  return { frontMatter: null, body: content }
}

function parseEntries(lines: string[]): FrontMatterEntry[] | null {
  const entries: FrontMatterEntry[] = []
  for (const line of lines) {
    if (line.trim() === '' || line.trimStart().startsWith('#')) continue

    const last = entries[entries.length - 1]
    if (/^[ \t]/.test(line) || line.startsWith('- ')) {
      // Continuation of the previous key (nested mapping, list item, folded text)
      if (!last) return null
      const text = line.trim()
      last.value = last.value ? `${last.value}\n${text}` : text
      continue
    }

    const match = KEY_VALUE_RE.exec(line)
    if (!match) return null
    entries.push({ key: (match[1] ?? '').trim(), value: unquote((match[2] ?? '').trim()) })
  }
  return entries
}

function unquote(value: string): string {
  if (value.length >= 2) {
    const first = value[0]
    if ((first === '"' || first === "'") && value[value.length - 1] === first) {
      return value.slice(1, -1)
    }
  }
  return value
}
