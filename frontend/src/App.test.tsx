import { describe, it, expect } from 'vitest'
import { render, screen } from '@/test/utils'
import App from './App'

describe('App', () => {
  it('should render home page by default', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /INXR2/i, level: 1 })).toBeInTheDocument()
  })

  it('should render with MUI theme and CssBaseline', () => {
    const { container } = render(<App />)

    // CssBaseline adds styles to the body
    expect(container).toBeInTheDocument()
  })
})
