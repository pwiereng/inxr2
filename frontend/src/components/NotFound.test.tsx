import { describe, it, expect } from 'vitest'
import { render, screen } from '@/test/utils'
import { NotFound } from './NotFound'

describe('NotFound', () => {
  it('should render 404 message', () => {
    render(<NotFound />)

    expect(screen.getByRole('heading', { name: /404/i, level: 1 })).toBeInTheDocument()
    expect(screen.getByText(/Page Not Found/i)).toBeInTheDocument()
  })

  it('should display error message', () => {
    render(<NotFound />)

    expect(screen.getByText(/The page you are looking for does not exist/i)).toBeInTheDocument()
  })

  it('should have a link to go back home', () => {
    render(<NotFound />)

    const homeLink = screen.getByRole('link', { name: /Go Home/i })
    expect(homeLink).toBeInTheDocument()
    expect(homeLink).toHaveAttribute('href', '/')
  })
})
