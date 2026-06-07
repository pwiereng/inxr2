import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FileNode, type FileNodeProps } from './FileNode'
import type { SymbolTreeFile, SymbolTreeSymbol } from '@/lib/api'

function makeFile(overrides: Partial<SymbolTreeFile> = {}): SymbolTreeFile {
  return {
    file_id: 1,
    path: 'src/lib/app.py',
    language: 'python',
    symbol_count: 4,
    kind_counts: {},
    all_kind_counts: { class: 2, function: 3 },
    ...overrides,
  }
}

function makeSymbol(overrides: Partial<SymbolTreeSymbol> = {}): SymbolTreeSymbol {
  return {
    id: 10,
    name: 'topLevelFn',
    kind: 'function',
    start_line: 1,
    end_line: 2,
    file_path: 'src/lib/app.py',
    has_children: false,
    signature: null,
    inheritance: [],
    ...overrides,
  }
}

function renderNode(props: Partial<FileNodeProps> = {}) {
  const defaults: FileNodeProps = {
    file: makeFile(),
    isExpanded: false,
    isExpanding: false,
    symbols: undefined,
    showKindCounts: false,
    highlightedSymbolIds: new Set<number>(),
    symbolChildren: {},
    expandedSymbols: new Set<number>(),
    expandingSymbol: null,
    onToggle: vi.fn(),
    onToggleSymbol: vi.fn(),
    onSymbolClick: vi.fn(),
    onInheritanceClick: vi.fn(),
    onSymbolContextMenu: vi.fn(),
  }
  const merged = { ...defaults, ...props }
  return { ...render(<FileNode {...merged} />), props: merged }
}

describe('FileNode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('splits the path into directory and file name, and shows the symbol count', () => {
    renderNode({ file: makeFile({ path: 'src/lib/app.py', symbol_count: 4 }) })
    expect(screen.getByText('src/lib/')).toBeInTheDocument()
    expect(screen.getByText('app.py')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
  })

  it('fires onToggle with the file id when the row is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderNode({ file: makeFile({ file_id: 7 }) })
    await user.click(screen.getByText('app.py'))
    expect(props.onToggle).toHaveBeenCalledWith(7)
  })

  it('shows a spinner while the file is expanding', () => {
    renderNode({ isExpanding: true })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('keeps symbols hidden (not visible) when collapsed', () => {
    // MUI Collapse keeps children mounted but visually hidden when closed.
    renderNode({
      symbols: [makeSymbol({ name: 'hiddenFn' })],
      isExpanded: false,
    })
    expect(screen.getByText('hiddenFn()')).not.toBeVisible()
  })

  it('renders top-level symbols via SymbolNode when expanded', () => {
    renderNode({
      symbols: [makeSymbol({ name: 'visibleFn' })],
      isExpanded: true,
    })
    expect(screen.getByText('visibleFn()')).toBeInTheDocument()
  })

  it('renders per-kind count chips only when showKindCounts is true', () => {
    const { rerender } = renderNode({ showKindCounts: false })
    expect(screen.queryByText('2 classes')).not.toBeInTheDocument()

    rerender(
      <FileNode
        file={makeFile()}
        isExpanded={false}
        isExpanding={false}
        symbols={undefined}
        showKindCounts={true}
        highlightedSymbolIds={new Set()}
        symbolChildren={{}}
        expandedSymbols={new Set()}
        expandingSymbol={null}
        onToggle={vi.fn()}
        onToggleSymbol={vi.fn()}
        onSymbolClick={vi.fn()}
        onInheritanceClick={vi.fn()}
        onSymbolContextMenu={vi.fn()}
      />
    )
    expect(screen.getByText('2 classes')).toBeInTheDocument()
    expect(screen.getByText('3 functions')).toBeInTheDocument()
  })
})
