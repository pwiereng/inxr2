import { describe, it, expect } from 'vitest'
import { isImageFile, isMarkdownFile, detectLanguage } from './fileUtils'

describe('isImageFile', () => {
  it('returns true for common image extensions', () => {
    expect(isImageFile('photo.png')).toBe(true)
    expect(isImageFile('photo.jpg')).toBe(true)
    expect(isImageFile('photo.jpeg')).toBe(true)
    expect(isImageFile('animation.gif')).toBe(true)
    expect(isImageFile('icon.svg')).toBe(true)
    expect(isImageFile('favicon.ico')).toBe(true)
    expect(isImageFile('image.webp')).toBe(true)
    expect(isImageFile('image.bmp')).toBe(true)
  })

  it('is case-insensitive', () => {
    expect(isImageFile('photo.PNG')).toBe(true)
    expect(isImageFile('photo.JPG')).toBe(true)
    expect(isImageFile('photo.Svg')).toBe(true)
  })

  it('returns false for non-image files', () => {
    expect(isImageFile('script.py')).toBe(false)
    expect(isImageFile('style.css')).toBe(false)
    expect(isImageFile('data.json')).toBe(false)
    expect(isImageFile('README.md')).toBe(false)
    expect(isImageFile('Dockerfile')).toBe(false)
  })

  it('returns false for files without extensions', () => {
    expect(isImageFile('Makefile')).toBe(false)
    expect(isImageFile('LICENSE')).toBe(false)
  })

  it('handles nested paths', () => {
    expect(isImageFile('src/assets/logo.png')).toBe(true)
    expect(isImageFile('docs/images/screenshot.jpg')).toBe(true)
    expect(isImageFile('src/components/App.tsx')).toBe(false)
  })
})

describe('isMarkdownFile', () => {
  it('returns true when language is markdown', () => {
    expect(isMarkdownFile('README.md', 'markdown')).toBe(true)
    expect(isMarkdownFile('notes.txt', 'markdown')).toBe(true)
  })

  it('returns true for markdown extensions even when language is null', () => {
    expect(isMarkdownFile('README.md', null)).toBe(true)
    expect(isMarkdownFile('docs/guide.markdown', null)).toBe(true)
    expect(isMarkdownFile('CHANGELOG.mdown', null)).toBe(true)
    expect(isMarkdownFile('notes.mkd', null)).toBe(true)
  })

  it('is case-insensitive for extensions', () => {
    expect(isMarkdownFile('README.MD', null)).toBe(true)
    expect(isMarkdownFile('file.Markdown', null)).toBe(true)
  })

  it('returns false for non-markdown files', () => {
    expect(isMarkdownFile('script.py', null)).toBe(false)
    expect(isMarkdownFile('style.css', null)).toBe(false)
    expect(isMarkdownFile('Dockerfile', null)).toBe(false)
  })
})

describe('detectLanguage', () => {
  it('returns API language when provided', () => {
    expect(detectLanguage('README.md', 'markdown')).toBe('markdown')
    expect(detectLanguage('script.py', 'python')).toBe('python')
  })

  it('detects language from extension when API returns null', () => {
    expect(detectLanguage('script.py', null)).toBe('python')
    expect(detectLanguage('app.ts', null)).toBe('typescript')
    expect(detectLanguage('config.toml', null)).toBe('toml')
    expect(detectLanguage('settings.ini', null)).toBe('ini')
    expect(detectLanguage('style.css', null)).toBe('css')
    expect(detectLanguage('query.sql', null)).toBe('sql')
  })

  it('detects language from filename for special files', () => {
    expect(detectLanguage('Dockerfile', null)).toBe('dockerfile')
    expect(detectLanguage('Dockerfile.dev', null)).toBe('dockerfile')
    expect(detectLanguage('Makefile', null)).toBe('makefile')
  })

  it('handles nested paths', () => {
    expect(detectLanguage('src/main.py', null)).toBe('python')
    expect(detectLanguage('qa-agent/Dockerfile', null)).toBe('dockerfile')
  })

  it('returns null for unknown file types', () => {
    expect(detectLanguage('LICENSE', null)).toBe(null)
    expect(detectLanguage('file.unknown', null)).toBe(null)
  })
})
