import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BreadcrumbNav } from './BreadcrumbNav'

describe('BreadcrumbNav', () => {
  const defaultProps = {
    repoName: 'my-repo',
    currentPath: null as string | null,
    onDirectoryClick: vi.fn(),
    onRootClick: vi.fn(),
  }

  it('should show only repo name at root (no path)', () => {
    render(<BreadcrumbNav {...defaultProps} />)
    expect(screen.getByText('my-repo')).toBeInTheDocument()
  })

  it('should not show copy button at root (no path to copy)', () => {
    render(<BreadcrumbNav {...defaultProps} />)
    expect(screen.queryByLabelText('Copy path')).not.toBeInTheDocument()
  })

  it('should show clickable repo name and path segments for a file', () => {
    render(
      <BreadcrumbNav {...defaultProps} currentPath="src/inxr2/domain/entities/repository.py" />
    )
    // Repo name is clickable
    expect(screen.getByRole('button', { name: 'my-repo' })).toBeInTheDocument()
    // Directory segments are clickable links
    expect(screen.getByRole('button', { name: 'src' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'inxr2' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'domain' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'entities' })).toBeInTheDocument()
    // Last segment (file) is not a button
    expect(screen.getByText('repository.py')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'repository.py' })).not.toBeInTheDocument()
  })

  it('should call onDirectoryClick with cumulative path when directory segment clicked', () => {
    const onDirectoryClick = vi.fn()
    render(
      <BreadcrumbNav
        {...defaultProps}
        currentPath="src/inxr2/domain/entities/repository.py"
        onDirectoryClick={onDirectoryClick}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: 'domain' }))
    expect(onDirectoryClick).toHaveBeenCalledWith('src/inxr2/domain')
  })

  it('should call onRootClick when repo name clicked', () => {
    const onRootClick = vi.fn()
    render(<BreadcrumbNav {...defaultProps} currentPath="src/main.py" onRootClick={onRootClick} />)
    fireEvent.click(screen.getByRole('button', { name: 'my-repo' }))
    expect(onRootClick).toHaveBeenCalled()
  })

  it('should show directory path with last segment as non-clickable text', () => {
    render(<BreadcrumbNav {...defaultProps} currentPath="src/inxr2/domain" />)
    // Parent segments are clickable
    expect(screen.getByRole('button', { name: 'src' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'inxr2' })).toBeInTheDocument()
    // Last directory segment is text (already viewing it)
    expect(screen.getByText('domain')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'domain' })).not.toBeInTheDocument()
  })

  it('should handle single-segment file path', () => {
    render(<BreadcrumbNav {...defaultProps} currentPath="README.md" />)
    expect(screen.getByRole('button', { name: 'my-repo' })).toBeInTheDocument()
    expect(screen.getByText('README.md')).toBeInTheDocument()
  })

  it('should show copy button when path is set', () => {
    render(<BreadcrumbNav {...defaultProps} currentPath="src/main.py" />)
    expect(screen.getByLabelText('Copy path')).toBeInTheDocument()
  })
})
