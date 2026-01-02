import { describe, it, expect } from 'vitest'
import { render, screen } from '@/test/utils'
import { Home } from './Home'

describe('Home', () => {
  it('should render the home page with title', () => {
    render(<Home />)

    expect(screen.getByRole('heading', { name: /INXR2/i, level: 1 })).toBeInTheDocument()
    expect(screen.getByText(/Cross-Reference Code Browser/i)).toBeInTheDocument()
  })

  it('should display Phase 1.2 completion message', () => {
    render(<Home />)

    expect(screen.getByText(/Phase 1.2 - Project Setup Complete/i)).toBeInTheDocument()
  })

  it('should list the completed setup items', () => {
    render(<Home />)

    expect(screen.getByText(/TypeScript with strict mode/i)).toBeInTheDocument()
    expect(screen.getByText(/React Router for navigation/i)).toBeInTheDocument()
    expect(screen.getByText(/Material-UI component library/i)).toBeInTheDocument()
    expect(screen.getByText(/API client with dependency injection/i)).toBeInTheDocument()
  })
})
