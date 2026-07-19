import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { isValidElement } from 'react'
import { KIND_ICONS, getKindIcon } from './kindIcons'

describe('getKindIcon', () => {
  it('returns the mapped icon element for a known kind', () => {
    const icon = getKindIcon('class')
    expect(icon).toBe(KIND_ICONS.class)
    expect(isValidElement(icon)).toBe(true)
  })

  it('maps the PHP trait kind to a dedicated (non-fallback) icon', () => {
    const icon = getKindIcon('trait')
    expect(icon).toBe(KIND_ICONS.trait)
    expect(isValidElement(icon)).toBe(true)
  })

  it('returns a fallback icon element for an unknown kind', () => {
    const icon = getKindIcon('totally_unknown')
    expect(isValidElement(icon)).toBe(true)
    // The fallback is a fresh element, not one of the mapped entries.
    expect(Object.values(KIND_ICONS)).not.toContain(icon)
  })

  it('renders an svg for both known and unknown kinds', () => {
    const known = render(<>{getKindIcon('function')}</>)
    expect(known.container.querySelector('svg')).toBeInTheDocument()
    const unknown = render(<>{getKindIcon('mystery')}</>)
    expect(unknown.container.querySelector('svg')).toBeInTheDocument()
  })
})
