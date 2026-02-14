import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { FileTypeIcon } from './file-icons'

describe('FileTypeIcon', () => {
  /** Helper: render the icon and return its text content */
  function renderLabel(filename: string, language: string | null): string {
    const { container } = render(
      <FileTypeIcon filename={filename} language={language} />,
    )
    return container.textContent ?? ''
  }

  describe('priority: filename > language > extension', () => {
    it('should match by exact filename (case-insensitive)', () => {
      expect(renderLabel('Dockerfile', null)).toBe('DK')
    })

    it('should match by language when no filename match', () => {
      expect(renderLabel('unknown_file', 'python')).toBe('PY')
    })

    it('should match by file extension when no language', () => {
      expect(renderLabel('app.ts', null)).toBe('TS')
    })

    it('should resolve compound extension before simple extension', () => {
      // index.d.ts should match the d.ts compound mapping (DT), not the ts mapping (TS)
      expect(renderLabel('index.d.ts', null)).toBe('DT')
    })

    it('should prioritize filename over language', () => {
      // package.json gets NP (npm package), not {} (generic json)
      expect(renderLabel('package.json', 'json')).toBe('NP')
    })

    it('should prioritize language over extension', () => {
      expect(renderLabel('Component.tsx', 'tsx')).toBe('TX')
    })
  })

  describe('fallback for unknown types', () => {
    it('should render empty for unknown files with no fallback', () => {
      const { container } = render(
        <FileTypeIcon filename="mystery_file" language={null} />,
      )
      expect(container.textContent).toBe('')
    })

    it('should render fallback element for unknown files', () => {
      const { container } = render(
        <FileTypeIcon
          filename="mystery_file"
          language={null}
          fallback={<span data-testid="fb">?</span>}
        />,
      )
      expect(container.textContent).toBe('?')
    })
  })

  describe('web frontend languages', () => {
    it('should handle CSS', () => expect(renderLabel('style.css', null)).toBe('CSS'))
    it('should handle HTML', () => expect(renderLabel('page.html', null)).toBe('<>'))
    it('should handle JSON', () => expect(renderLabel('data.json', null)).toBe('{}'))
    it('should handle YAML', () => expect(renderLabel('config.yaml', null)).toBe('YM'))
    it('should handle SCSS', () => expect(renderLabel('theme.scss', null)).toBe('SC'))
    it('should handle Vue', () => expect(renderLabel('App.vue', null)).toBe('VU'))
    it('should handle Svelte', () =>
      expect(renderLabel('App.svelte', null)).toBe('SV'))
  })

  describe('systems languages', () => {
    it('should handle Go', () => expect(renderLabel('main.go', null)).toBe('GO'))
    it('should handle Rust', () => expect(renderLabel('lib.rs', null)).toBe('RS'))
    it('should handle Java', () => expect(renderLabel('App.java', null)).toBe('JV'))
    it('should handle C#', () => expect(renderLabel('Program.cs', null)).toBe('C#'))
    it('should handle C', () => expect(renderLabel('main.c', null)).toBe('C'))
    it('should handle C++', () => expect(renderLabel('main.cpp', null)).toBe('++'))
    it('should handle Swift', () =>
      expect(renderLabel('main.swift', null)).toBe('SW'))
    it('should handle Kotlin', () => expect(renderLabel('Main.kt', null)).toBe('KT'))
    it('should handle Dart', () => expect(renderLabel('main.dart', null)).toBe('DT'))
  })

  describe('scripting languages', () => {
    it('should handle Ruby', () => expect(renderLabel('script.rb', null)).toBe('RB'))
    it('should handle PHP', () => expect(renderLabel('index.php', null)).toBe('PHP'))
    it('should handle Shell', () => expect(renderLabel('script.sh', null)).toBe('$_'))
    it('should handle Perl', () => expect(renderLabel('script.pl', null)).toBe('PL'))
    it('should handle Lua', () => expect(renderLabel('script.lua', null)).toBe('LU'))
    it('should handle R', () => expect(renderLabel('analysis.r', null)).toBe('R'))
  })

  describe('special filenames', () => {
    it('should handle Makefile', () =>
      expect(renderLabel('Makefile', null)).toBe('MK'))
    it('should handle .gitignore', () =>
      expect(renderLabel('.gitignore', null)).toBe('GI'))
    it('should handle tsconfig.json', () =>
      expect(renderLabel('tsconfig.json', null)).toBe('TS'))
    it('should handle requirements.txt', () =>
      expect(renderLabel('requirements.txt', null)).toBe('RQ'))
    it('should handle docker-compose.yml', () =>
      expect(renderLabel('docker-compose.yml', null)).toBe('DC'))
    it('should handle .env', () => expect(renderLabel('.env', null)).toBe('ENV'))
  })

  describe('media & document files', () => {
    it('should handle PNG', () => expect(renderLabel('photo.png', null)).toBe('PNG'))
    it('should handle JPG', () => expect(renderLabel('photo.jpg', null)).toBe('JPG'))
    it('should handle SVG', () => expect(renderLabel('icon.svg', null)).toBe('SVG'))
    it('should handle PDF', () => expect(renderLabel('doc.pdf', null)).toBe('PDF'))
  })

  describe('documentation files', () => {
    it('should handle README.md', () =>
      expect(renderLabel('README.md', null)).toBe('RM'))
    it('should handle Markdown', () =>
      expect(renderLabel('notes.md', null)).toBe('MD'))
    it('should handle plain text', () =>
      expect(renderLabel('notes.txt', null)).toBe('TXT'))
  })

  describe('Python ecosystem', () => {
    it('should handle .py', () => expect(renderLabel('main.py', null)).toBe('PY'))
    it('should handle .ipynb', () =>
      expect(renderLabel('notebook.ipynb', null)).toBe('NB'))
    it('should handle pyproject.toml', () =>
      expect(renderLabel('pyproject.toml', null)).toBe('PP'))
  })

  describe('rendering', () => {
    it('should render badge with correct text for known type', () => {
      const { container } = render(
        <FileTypeIcon filename="app.py" language="python" />,
      )
      expect(container.textContent).toBe('PY')
    })

    it('should render badge as a span element', () => {
      const { container } = render(
        <FileTypeIcon filename="index.ts" language="typescript" />,
      )
      const badge = container.querySelector('span')
      expect(badge).not.toBeNull()
      expect(badge!.textContent).toBe('TS')
    })
  })
})
