import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SymbolNode, type SymbolNodeProps } from './SymbolNode'
import type { SymbolTreeSymbol } from '@/lib/api'

function makeSymbol(overrides: Partial<SymbolTreeSymbol> = {}): SymbolTreeSymbol {
  return {
    id: 1,
    name: 'doThing',
    kind: 'function',
    start_line: 42,
    end_line: 50,
    file_path: 'src/app.py',
    has_children: false,
    signature: null,
    inheritance: [],
    ...overrides,
  }
}

function renderNode(props: Partial<SymbolNodeProps> = {}) {
  const defaults: SymbolNodeProps = {
    symbol: makeSymbol(),
    level: 1,
    children: undefined,
    expandedSymbols: new Set<number>(),
    expandingSymbol: null,
    symbolChildren: {},
    highlightedSymbolIds: new Set<number>(),
    onToggle: vi.fn(),
    onClick: vi.fn(),
    onInheritanceClick: vi.fn(),
    onContextMenuAction: vi.fn(),
  }
  const merged = { ...defaults, ...props }
  return { ...render(<SymbolNode {...merged} />), props: merged }
}

describe('SymbolNode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a callable symbol name with parentheses and its kind label', () => {
    renderNode({ symbol: makeSymbol({ name: 'doThing', kind: 'function' }) })
    expect(screen.getByText('doThing()')).toBeInTheDocument()
    expect(screen.getByText('function')).toBeInTheDocument()
  })

  it('renders a non-callable symbol name without parentheses', () => {
    renderNode({ symbol: makeSymbol({ name: 'MAX', kind: 'constant' }) })
    expect(screen.getByText('MAX')).toBeInTheDocument()
    expect(screen.queryByText('MAX()')).not.toBeInTheDocument()
  })

  it('fires onClick with the symbol when the go-to-line button is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderNode()
    await user.click(screen.getByRole('button', { name: 'Go to line 42' }))
    expect(props.onClick).toHaveBeenCalledWith(props.symbol)
  })

  it('shows an expand chevron and toggles when a parent symbol is clicked', async () => {
    const user = userEvent.setup()
    const symbol = makeSymbol({ id: 5, name: 'MyClass', kind: 'class', has_children: true })
    const { props } = renderNode({ symbol })
    // The row itself is a button for parent symbols; click its name to toggle.
    await user.click(screen.getByText('MyClass'))
    expect(props.onToggle).toHaveBeenCalledWith(5)
  })

  it('renders children when expanded and recurses into SymbolNode', () => {
    const parent = makeSymbol({ id: 5, name: 'MyClass', kind: 'class', has_children: true })
    const child = makeSymbol({ id: 6, name: 'childMethod', kind: 'method' })
    renderNode({
      symbol: parent,
      children: [child],
      expandedSymbols: new Set([5]),
    })
    expect(screen.getByText('childMethod()')).toBeInTheDocument()
  })

  it('shows a spinner while the symbol is expanding', () => {
    const symbol = makeSymbol({ id: 5, kind: 'class', has_children: true })
    renderNode({ symbol, expandingSymbol: 5 })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('invokes the context menu handler on right-click', () => {
    const symbol = makeSymbol({ id: 7, name: 'rightClickMe', kind: 'variable' })
    const { props } = renderNode({ symbol })
    fireContextMenu(screen.getByText('rightClickMe'))
    expect(props.onContextMenuAction).toHaveBeenCalled()
    expect(vi.mocked(props.onContextMenuAction).mock.calls[0]![0]).toBe(symbol)
  })

  it('invokes the context menu handler on right-click of a parent (button) row', () => {
    const symbol = makeSymbol({ id: 11, name: 'ParentCls', kind: 'class', has_children: true })
    const { props } = renderNode({ symbol })
    fireContextMenu(screen.getByText('ParentCls'))
    expect(props.onContextMenuAction).toHaveBeenCalled()
    expect(vi.mocked(props.onContextMenuAction).mock.calls[0]![0]).toBe(symbol)
  })

  it('renders inheritance chips and fires onInheritanceClick on click', async () => {
    const user = userEvent.setup()
    const symbol = makeSymbol({
      name: 'Derived',
      kind: 'class',
      inheritance: [
        {
          reference_text: 'Base',
          target_symbol_id: 99,
          target_file_id: 3,
          target_file_path: 'src/base.py',
          target_line: 10,
        },
      ],
    })
    const { props } = renderNode({ symbol })
    await user.click(screen.getByText('extends Base'))
    expect(props.onInheritanceClick).toHaveBeenCalled()
  })

  it('does not wire a click handler for inheritance with no target file', async () => {
    const user = userEvent.setup()
    const symbol = makeSymbol({
      kind: 'class',
      inheritance: [
        {
          reference_text: 'Unknown',
          target_symbol_id: null,
          target_file_id: null,
          target_file_path: null,
          target_line: null,
        },
      ],
    })
    const { props } = renderNode({ symbol })
    await user.click(screen.getByText('extends Unknown'))
    expect(props.onInheritanceClick).not.toHaveBeenCalled()
  })

  it('applies highlight styling when the symbol id is in the highlighted set', () => {
    renderNode({
      symbol: makeSymbol({ id: 3, name: 'hit' }),
      highlightedSymbolIds: new Set([3]),
    })
    expect(screen.getByText('hit()')).toBeInTheDocument()
  })
})

function fireContextMenu(el: Element) {
  el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }))
}
