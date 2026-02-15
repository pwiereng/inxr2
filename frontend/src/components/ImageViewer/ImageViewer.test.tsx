import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ImageViewer } from './ImageViewer'
import type { RawFileContent } from '@/lib/api'

describe('ImageViewer', () => {
  it('renders base64 PNG image with correct data URI', () => {
    const rawContent: RawFileContent = {
      path: 'assets/logo.png',
      language: null,
      content_type: 'image/png',
      encoding: 'base64',
      data: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
      size_bytes: 68,
    }

    render(<ImageViewer rawContent={rawContent} />)

    const img = screen.getByRole('img')
    expect(img).toHaveAttribute('src', `data:image/png;base64,${rawContent.data}`)
    expect(img).toHaveAttribute('alt', 'assets/logo.png')
  })

  it('renders SVG with UTF-8 encoding using encoded data URI', () => {
    const svgData = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
    const rawContent: RawFileContent = {
      path: 'icon.svg',
      language: 'svg',
      content_type: 'image/svg+xml',
      encoding: 'utf-8',
      data: svgData,
      size_bytes: svgData.length,
    }

    render(<ImageViewer rawContent={rawContent} />)

    const img = screen.getByRole('img')
    expect(img.getAttribute('src')).toContain('data:image/svg+xml;charset=utf-8,')
    expect(img).toHaveAttribute('alt', 'icon.svg')
  })

  it('displays file type and size', () => {
    const rawContent: RawFileContent = {
      path: 'photo.jpg',
      language: null,
      content_type: 'image/jpeg',
      encoding: 'base64',
      data: '/9j/4AAQ',
      size_bytes: 15360,
    }

    render(<ImageViewer rawContent={rawContent} />)

    // Should show file type and size
    expect(screen.getByText(/JPEG/)).toBeInTheDocument()
    expect(screen.getByText(/15\.0 KB/)).toBeInTheDocument()
  })
})
