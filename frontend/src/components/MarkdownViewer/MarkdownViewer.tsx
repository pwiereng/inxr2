import { useEffect, useId, useMemo, useState } from 'react'
import { Box } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import mermaid from 'mermaid'
import DOMPurify from 'dompurify'
import Prism from 'prismjs'
import { getPrismLanguage } from '@/lib/prismLanguages'

// Initialize mermaid once at module level (startOnLoad only — theme is set per-render
// via the %%{init}%% directive to avoid global-state races when multiple diagrams mount).
mermaid.initialize({ startOnLoad: false })

interface MarkdownViewerProps {
  content: string
}

interface MermaidDiagramProps {
  code: string
  isDark: boolean
}

export function MermaidDiagram({ code, isDark }: MermaidDiagramProps): React.ReactElement {
  const [svg, setSvg] = useState<string | null>(null)
  const rawId = useId()
  const id = `mermaid${rawId.replace(/:/g, '-')}`

  useEffect(() => {
    let cancelled = false
    // Embed theme per-render via the mermaid init directive so each diagram is
    // self-contained and concurrent renders don't race on global mermaid state.
    const theme = isDark ? 'dark' : 'default'
    const themedCode = `%%{init: {"theme": "${theme}"}}%%\n${code}`
    mermaid
      .render(id, themedCode)
      .then(({ svg: renderedSvg }) => {
        if (!cancelled) {
          const sanitized = DOMPurify.sanitize(renderedSvg, {
            USE_PROFILES: { svg: true, svgFilters: true },
          })
          setSvg(sanitized)
        }
      })
      .catch((err: unknown) => {
        console.error('MermaidDiagram render failed:', err)
      })
    return () => {
      cancelled = true
    }
  }, [code, id, isDark])

  if (svg !== null) {
    return <div dangerouslySetInnerHTML={{ __html: svg }} />
  }

  return (
    <pre>
      <code>{code}</code>
    </pre>
  )
}

export function MarkdownViewer({ content }: MarkdownViewerProps): React.ReactElement {
  const theme = useTheme()
  const isDark = theme.palette.mode === 'dark'

  const markdownStyles = useMemo(
    () => ({
      fontFamily: '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      fontSize: '14px',
      lineHeight: 1.7,
      color: theme.palette.text.primary,
      p: 3,
      '& h1, & h2, & h3, & h4, & h5, & h6': {
        mt: 3,
        mb: 1,
        fontWeight: 600,
        lineHeight: 1.3,
      },
      '& h1': { fontSize: '2em', pb: 0.5, borderBottom: `1px solid ${theme.palette.divider}` },
      '& h2': { fontSize: '1.5em', pb: 0.5, borderBottom: `1px solid ${theme.palette.divider}` },
      '& h3': { fontSize: '1.25em' },
      '& h4': { fontSize: '1em' },
      '& p': { my: 1 },
      '& a': {
        color: theme.palette.primary.main,
        textDecoration: 'none',
        '&:hover': { textDecoration: 'underline' },
      },
      '& code': {
        fontFamily: 'monospace',
        fontSize: '0.875em',
        bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
        borderRadius: '3px',
        px: 0.5,
        py: 0.25,
      },
      '& pre': {
        my: 1.5,
        p: 2,
        borderRadius: 1,
        overflow: 'auto',
        bgcolor: 'background.default',
        '& code': {
          bgcolor: 'transparent',
          px: 0,
          py: 0,
          fontSize: '13px',
        },
      },
      '& blockquote': {
        my: 1,
        mx: 0,
        pl: 2,
        borderLeft: `4px solid ${theme.palette.divider}`,
        color: theme.palette.text.secondary,
      },
      '& ul, & ol': { pl: 3, my: 1 },
      '& li': { my: 0.25 },
      '& table': {
        borderCollapse: 'collapse',
        width: '100%',
        my: 1.5,
      },
      '& th, & td': {
        border: `1px solid ${theme.palette.divider}`,
        px: 1.5,
        py: 0.75,
        textAlign: 'left',
      },
      '& th': {
        fontWeight: 600,
        bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)',
      },
      '& hr': {
        border: 'none',
        borderTop: `1px solid ${theme.palette.divider}`,
        my: 2,
      },
      '& img': {
        maxWidth: '100%',
        height: 'auto',
      },
      '& input[type="checkbox"]': {
        mr: 0.5,
      },
    }),
    [theme]
  )

  return (
    <Box sx={markdownStyles}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className ?? '')
            const lang = match?.[1] ?? null
            const codeString = String(children).replace(/\n$/, '')

            if (lang === 'mermaid') {
              return <MermaidDiagram code={codeString} isDark={isDark} />
            }

            const prismLang = lang ? getPrismLanguage(lang) : null
            if (prismLang && prismLang !== 'text') {
              const grammar = Prism.languages[prismLang]
              if (grammar) {
                const html = Prism.highlight(codeString, grammar, prismLang)
                return (
                  <code
                    className={className}
                    dangerouslySetInnerHTML={{ __html: html }}
                    {...props}
                  />
                )
              }
            }

            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </Box>
  )
}

export default MarkdownViewer
