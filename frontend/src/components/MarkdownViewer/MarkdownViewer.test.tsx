import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import { MarkdownViewer } from './MarkdownViewer'

// react-markdown v10 is ESM-only and doesn't render in jsdom.
// Mock it to test our component's integration behavior.
vi.mock('react-markdown', () => ({
  __esModule: true,
  default: ({
    children,
    components,
  }: {
    children: string
    remarkPlugins?: unknown[]
    components?: Record<string, unknown>
  }) => {
    // Simple markdown-to-HTML conversion for testing
    let html = children

    // Headings
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')

    // Code blocks
    html = html.replace(
      /```(\w+)?\n([\s\S]*?)```/g,
      (_match: string, lang: string | undefined, code: string) => {
        const className = lang ? `language-${lang}` : ''
        if (components?.code) {
          // Let the custom code component handle it
          return `<pre><code class="${className}">${code.trim()}</code></pre>`
        }
        return `<pre><code class="${className}">${code.trim()}</code></pre>`
      }
    )

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')

    // GFM tables (basic support)
    const tableMatch = html.match(/\|(.+)\|\n\|[-| ]+\|\n((?:\|.+\|\n?)*)/)
    if (tableMatch) {
      const headers = tableMatch[1]!
        .split('|')
        .map((h: string) => h.trim())
        .filter(Boolean)
      const rows = tableMatch[2]!
        .trim()
        .split('\n')
        .map((row: string) =>
          row
            .split('|')
            .map((c: string) => c.trim())
            .filter(Boolean)
        )

      const tableHtml = `<table><thead><tr>${headers.map((h: string) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map((row: string[]) => `<tr>${row.map((c: string) => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`
      html = html.replace(/\|(.+)\|\n\|[-| ]+\|\n((?:\|.+\|\n?)*)/, tableHtml)
    }

    // Unordered lists
    const lines = html.split('\n')
    let inList = false
    const outputLines: string[] = []
    let listItems = ''
    for (const line of lines) {
      if (line.startsWith('- ')) {
        if (!inList) inList = true
        listItems += `<li>${line.slice(2)}</li>`
      } else {
        if (inList) {
          outputLines.push(`<ul>${listItems}</ul>`)
          listItems = ''
          inList = false
        }
        outputLines.push(line)
      }
    }
    if (inList) {
      outputLines.push(`<ul>${listItems}</ul>`)
    }
    html = outputLines.join('\n')

    // Paragraphs (lines that aren't already wrapped in tags)
    html = html.replace(/^(?!<[a-z])((?!^\s*$).+)$/gm, (match: string) => {
      // Don't wrap if already inside a tag
      if (match.startsWith('<')) return match
      return `<p>${match}</p>`
    })

    // Remove empty lines
    html = html.replace(/^\s*\n/gm, '')

    return <div dangerouslySetInnerHTML={{ __html: html }} />
  },
}))

// Minimal theme with code palette for testing
const theme = createTheme({
  palette: {
    code: {
      background: '#1e1e1e',
      text: '#d4d4d4',
      lineNumber: '#858585',
      lineNumberHover: '#c6c6c6',
      lineNumberHighlight: '#c6c6c6',
      lineBorder: '#404040',
      highlightBg: 'rgba(255, 255, 0, 0.07)',
      highlightHoverBg: 'rgba(255, 255, 0, 0.12)',
      hoverBg: 'rgba(255, 255, 255, 0.04)',
      symbolUnderline: '#569cd6',
      referenceUnderline: '#9cdcfe',
      diffAddedBg: 'rgba(0, 255, 0, 0.1)',
      diffRemovedBg: 'rgba(255, 0, 0, 0.1)',
      diffModifiedBg: 'rgba(255, 255, 0, 0.1)',
      diffAddedIndicator: '#4caf50',
      diffRemovedIndicator: '#f44336',
    },
    blame: {
      date: '#888',
      hash: '#569cd6',
      author: '#ce9178',
      border: '#404040',
    },
  } as never,
})

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>)
}

describe('MarkdownViewer', () => {
  it('renders headings', () => {
    renderWithTheme(<MarkdownViewer content="# Hello World" />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Hello World')
  })

  it('renders multiple heading levels', () => {
    renderWithTheme(<MarkdownViewer content={'# H1\n## H2\n### H3'} />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('H1')
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('H2')
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent('H3')
  })

  it('renders paragraphs', () => {
    renderWithTheme(<MarkdownViewer content="This is a paragraph." />)
    expect(screen.getByText('This is a paragraph.')).toBeInTheDocument()
  })

  it('renders code blocks', () => {
    const md = '```python\nprint("hello")\n```'
    renderWithTheme(<MarkdownViewer content={md} />)
    expect(screen.getByText(/print/)).toBeInTheDocument()
  })

  it('renders GFM tables', () => {
    const md = '| Name | Age |\n|------|-----|\n| Alice | 30 |'
    renderWithTheme(<MarkdownViewer content={md} />)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
  })

  it('renders links', () => {
    renderWithTheme(<MarkdownViewer content="[Click here](https://example.com)" />)
    const link = screen.getByRole('link', { name: 'Click here' })
    expect(link).toHaveAttribute('href', 'https://example.com')
  })

  it('renders inline code', () => {
    renderWithTheme(<MarkdownViewer content="Use `npm install` to install" />)
    expect(screen.getByText('npm install')).toBeInTheDocument()
  })

  it('renders unordered lists', () => {
    renderWithTheme(<MarkdownViewer content={'- Item 1\n- Item 2\n- Item 3'} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
  })
})
