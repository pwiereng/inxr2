import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import { MarkdownViewer, MermaidDiagram } from './MarkdownViewer'

// react-markdown v10 is ESM-only and doesn't render in jsdom.
// Mock it to test our component's integration behavior.

function processMarkdownText(text: string): string {
  let html = text

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')

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
    if (match.startsWith('<')) return match
    return `<p>${match}</p>`
  })

  // Remove empty lines
  html = html.replace(/^\s*\n/gm, '')

  return html
}

vi.mock('react-markdown', () => ({
  __esModule: true,
  default: ({
    children,
    components,
  }: {
    children: string
    remarkPlugins?: unknown[]
    components?: {
      code?: (props: { className?: string; children?: React.ReactNode }) => React.ReactElement
    }
  }) => {
    const parts: React.ReactNode[] = []
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g
    let lastIndex = 0
    let key = 0
    let match: RegExpExecArray | null

    while ((match = codeBlockRegex.exec(children)) !== null) {
      if (match.index > lastIndex) {
        const textBefore = children.slice(lastIndex, match.index)
        parts.push(
          <div key={key++} dangerouslySetInnerHTML={{ __html: processMarkdownText(textBefore) }} />
        )
      }

      const lang = match[1]
      const code = (match[2] ?? '').trim()
      const className = lang ? `language-${lang}` : ''

      if (components?.code) {
        const CodeComp = components.code
        parts.push(
          <pre key={key++}>
            <CodeComp className={className}>{code}</CodeComp>
          </pre>
        )
      } else {
        parts.push(
          <pre key={key++}>
            <code className={className}>{code}</code>
          </pre>
        )
      }

      lastIndex = match.index + match[0].length
    }

    if (lastIndex < children.length || parts.length === 0) {
      parts.push(
        <div
          key={key++}
          dangerouslySetInnerHTML={{ __html: processMarkdownText(children.slice(lastIndex)) }}
        />
      )
    }

    return <div>{parts}</div>
  },
}))

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({
      svg: '<svg data-testid="mermaid-svg"><text>diagram</text></svg>',
      diagramType: 'flowchart',
    }),
  },
}))

// DOMPurify is a passthrough in tests — we test component behaviour, not sanitization.
vi.mock('dompurify', () => ({
  default: {
    sanitize: vi.fn((svg: string) => svg),
  },
}))

// Minimal theme with code palette for testing
const lightTheme = createTheme({
  palette: {
    mode: 'light',
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

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
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

// Keep the original theme alias for backward compatibility
const theme = lightTheme

function renderWithTheme(ui: React.ReactElement, themeOverride = theme) {
  return render(<ThemeProvider theme={themeOverride}>{ui}</ThemeProvider>)
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

  it('renders mermaid blocks as SVG diagrams', async () => {
    const md = '```mermaid\ngraph TD\n  A --> B\n```'
    renderWithTheme(<MarkdownViewer content={md} />)
    const svg = await screen.findByTestId('mermaid-svg')
    expect(svg).toBeInTheDocument()
  })

  it('does not render mermaid code as plain text', async () => {
    const md = '```mermaid\ngraph TD\n  A --> B\n```'
    renderWithTheme(<MarkdownViewer content={md} />)
    await screen.findByTestId('mermaid-svg')
    // The mermaid source should not appear as raw code
    expect(screen.queryByText('graph TD')).not.toBeInTheDocument()
  })
})

describe('MermaidDiagram', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    // Restore default resolved value after clearing (clearAllMocks wipes mockResolvedValue).
    const { default: mermaidMock } = await import('mermaid')
    vi.mocked(mermaidMock.render).mockResolvedValue({
      svg: '<svg data-testid="mermaid-svg"><text>diagram</text></svg>',
      diagramType: 'flowchart',
    })
  })

  it('renders SVG when mermaid.render resolves', async () => {
    const { default: mermaidMock } = await import('mermaid')
    vi.mocked(mermaidMock.render).mockResolvedValue({
      svg: '<svg data-testid="mermaid-svg"><text>diagram</text></svg>',
      diagramType: 'flowchart',
    })

    renderWithTheme(<MermaidDiagram code="graph TD\n  A --> B" isDark={false} />)
    const svg = await screen.findByTestId('mermaid-svg')
    expect(svg).toBeInTheDocument()
  })

  it('renders with default theme in light mode', async () => {
    const { default: mermaidMock } = await import('mermaid')

    await act(async () => {
      renderWithTheme(<MermaidDiagram code="graph TD\n  A --> B" isDark={false} />)
    })

    expect(mermaidMock.render).toHaveBeenCalledWith(
      expect.any(String),
      expect.stringContaining('"theme": "default"')
    )
  })

  it('renders with dark theme in dark mode', async () => {
    const { default: mermaidMock } = await import('mermaid')

    await act(async () => {
      renderWithTheme(<MermaidDiagram code="graph TD\n  A --> B" isDark={true} />)
    })

    expect(mermaidMock.render).toHaveBeenCalledWith(
      expect.any(String),
      expect.stringContaining('"theme": "dark"')
    )
  })

  it('re-renders with updated theme when isDark prop changes', async () => {
    const { default: mermaidMock } = await import('mermaid')
    const code = 'graph TD\n  A --> B'

    const { rerender } = renderWithTheme(<MermaidDiagram code={code} isDark={false} />)
    await screen.findByTestId('mermaid-svg')

    rerender(
      <ThemeProvider theme={darkTheme}>
        <MermaidDiagram code={code} isDark={true} />
      </ThemeProvider>
    )

    await waitFor(() => {
      expect(mermaidMock.render).toHaveBeenLastCalledWith(
        expect.any(String),
        expect.stringContaining('"theme": "dark"')
      )
    })
  })

  it('falls back to code block when mermaid.render rejects', async () => {
    const { default: mermaidMock } = await import('mermaid')
    vi.mocked(mermaidMock.render).mockRejectedValue(new Error('parse error'))

    renderWithTheme(<MermaidDiagram code="invalid mermaid" isDark={false} />)
    // Fallback: the code should appear in a <pre><code> block
    expect(screen.getByText('invalid mermaid')).toBeInTheDocument()
  })

  it('passes dark theme from MarkdownViewer to mermaid render', async () => {
    const { default: mermaidMock } = await import('mermaid')

    await act(async () => {
      renderWithTheme(
        <MarkdownViewer content={'```mermaid\ngraph TD\n  A --> B\n```'} />,
        darkTheme
      )
    })

    expect(mermaidMock.render).toHaveBeenCalledWith(
      expect.any(String),
      expect.stringContaining('"theme": "dark"')
    )
  })

  it('sanitizes SVG output via DOMPurify', async () => {
    const { default: DOMPurifyMock } = await import('dompurify')

    await act(async () => {
      renderWithTheme(<MermaidDiagram code="graph TD\n  A --> B" isDark={false} />)
    })

    await screen.findByTestId('mermaid-svg')
    expect(DOMPurifyMock.sanitize).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        USE_PROFILES: { svg: true, svgFilters: true },
        ADD_TAGS: ['foreignObject', 'style'],
      })
    )
  })

  // Regression test for #408: DOMPurify SVG profile strips <foreignObject> (used
  // by Mermaid for multi-line node labels) and <style> (used for diagram styling).
  // ADD_TAGS must include both so diagrams render correctly.
  it('sanitize config includes ADD_TAGS for foreignObject and style (#408)', async () => {
    const { default: DOMPurifyMock } = await import('dompurify')

    await act(async () => {
      renderWithTheme(<MermaidDiagram code="graph TD\n  A --> B" isDark={false} />)
    })

    await screen.findByTestId('mermaid-svg')
    expect(DOMPurifyMock.sanitize).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        ADD_TAGS: expect.arrayContaining(['foreignObject', 'style']),
      })
    )
  })
})
