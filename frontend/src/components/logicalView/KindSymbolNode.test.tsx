import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { KindSymbolNode, type KindSymbolNodeProps } from './KindSymbolNode'
import type { Symbol as ApiSymbol, SymbolTreeSymbol } from '@/lib/api'

function makeApiSymbol(overrides: Partial<ApiSymbol> = {}): ApiSymbol {
  return {
    id: 1,
    name: 'handler',
    qualified_name: 'handler',
    kind: 'function',
    file_id: 1,
    file_path: 'src/api/routes.py',
    repository_id: 1,
    commit_id: 1,
    start_line: 12,
    start_column: 0,
    end_line: 20,
    end_column: 0,
    signature: null,
    docstring: null,
    ...overrides,
  }
}

function makeChild(overrides: Partial<SymbolTreeSymbol> = {}): SymbolTreeSymbol {
  return {
    id: 50,
    name: 'innerMethod',
    kind: 'method',
    start_line: 1,
    end_line: 2,
    file_path: 'src/api/routes.py',
    has_children: false,
    signature: null,
    inheritance: [],
    ...overrides,
  }
}

function renderNode(props: Partial<KindSymbolNodeProps> = {}) {
  const defaults: KindSymbolNodeProps = {
    symbol: makeApiSymbol(),
    isExpanded: false,
    isExpanding: false,
    children: undefined,
    symbolChildren: {},
    expandedSymbols: new Set<number>(),
    expandingSymbol: null,
    onToggle: vi.fn(),
    onSymbolClick: vi.fn(),
    onInheritanceClick: vi.fn(),
    onSymbolContextMenu: vi.fn(),
    onSwitchToOutline: vi.fn(),
  }
  const merged = { ...defaults, ...props }
  return { ...render(<KindSymbolNode {...merged} />), props: merged }
}

describe('KindSymbolNode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a callable leaf symbol with parentheses and its file path', () => {
    renderNode({ symbol: makeApiSymbol({ name: 'handler', kind: 'function' }) })
    expect(screen.getByText('handler()')).toBeInTheDocument()
    // Directory and file name are rendered separately.
    expect(screen.getByText('src/api/')).toBeInTheDocument()
    expect(screen.getByText('routes.py')).toBeInTheDocument()
  })

  it('navigates via onSymbolClick (as a tree symbol) when the go-to-line button is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderNode({ symbol: makeApiSymbol({ id: 9, start_line: 12 }) })
    await user.click(screen.getByRole('button', { name: 'Go to line 12' }))
    expect(props.onSymbolClick).toHaveBeenCalledTimes(1)
    expect(vi.mocked(props.onSymbolClick).mock.calls[0]![0]).toMatchObject({
      id: 9,
      has_children: false,
    })
  })

  it('fires onSwitchToOutline with the file path when the path link is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderNode({ symbol: makeApiSymbol({ file_path: 'src/api/routes.py' }) })
    await user.click(screen.getByText('routes.py'))
    expect(props.onSwitchToOutline).toHaveBeenCalledWith('src/api/routes.py')
  })

  it('does not render the file-path link when file_path is null', () => {
    renderNode({ symbol: makeApiSymbol({ name: 'lonely', file_path: null }) })
    expect(screen.getByText('lonely()')).toBeInTheDocument()
    expect(screen.queryByText('routes.py')).not.toBeInTheDocument()
  })

  it('toggles a container kind when its row is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderNode({
      symbol: makeApiSymbol({ id: 3, name: 'MyClass', kind: 'class' }),
    })
    await user.click(screen.getByText('MyClass'))
    expect(props.onToggle).toHaveBeenCalledWith(3)
  })

  it('shows a spinner while a container is expanding', () => {
    renderNode({
      symbol: makeApiSymbol({ id: 3, name: 'MyClass', kind: 'class' }),
      isExpanding: true,
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('renders children via SymbolNode when an expanded container has them', () => {
    renderNode({
      symbol: makeApiSymbol({ id: 3, name: 'MyClass', kind: 'class' }),
      isExpanded: true,
      children: [makeChild({ name: 'innerMethod' })],
    })
    expect(screen.getByText('innerMethod()')).toBeInTheDocument()
  })

  it('invokes the context-menu handler on right-click of a leaf row', () => {
    const { props } = renderNode({ symbol: makeApiSymbol({ id: 8, name: 'ctxFn' }) })
    fireContextMenu(screen.getByText('ctxFn()'))
    expect(props.onSymbolContextMenu).toHaveBeenCalled()
    expect(vi.mocked(props.onSymbolContextMenu).mock.calls[0]![0]).toMatchObject({ id: 8 })
  })

  it('invokes the context-menu handler on right-click of a container row', () => {
    const { props } = renderNode({
      symbol: makeApiSymbol({ id: 12, name: 'CtxClass', kind: 'class' }),
    })
    fireContextMenu(screen.getByText('CtxClass'))
    expect(props.onSymbolContextMenu).toHaveBeenCalled()
    expect(vi.mocked(props.onSymbolContextMenu).mock.calls[0]![0]).toMatchObject({
      id: 12,
      has_children: true,
    })
  })
})

function fireContextMenu(el: Element) {
  el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }))
}
