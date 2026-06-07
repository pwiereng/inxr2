import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useBrowseRefsState, type UseBrowseRefsStateParams } from './useBrowseRefsState'
import type { BrowseUrlState } from './useBrowseTypes'
import type { NavigateFunction } from 'react-router-dom'
import * as api from '@/lib/api'
import type { Symbol, FileSymbol, FileReference, Repository } from '@/lib/api'

/** Extract the URL string passed to the first navigate() call. */
function navUrl(navigate: NavigateFunction): string {
  return String(vi.mocked(navigate).mock.calls[0]?.[0])
}

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof api>()
  return { ...actual, getSymbol: vi.fn() }
})
const mockGetSymbol = vi.mocked(api.getSymbol)

function makeUrlState(overrides: Partial<BrowseUrlState> = {}): BrowseUrlState {
  return {
    repoName: 'myrepo',
    filePath: 'src/app.py',
    directoryPath: null,
    highlightLine: undefined,
    selectedCommit: null,
    diffCommit: null,
    diffMode: false,
    selectedBranch: null,
    diffBranch: null,
    searchQuery: '',
    drawerOpen: true,
    refsPanelOpen: false,
    treePanel: 'left',
    refPanel: 'left',
    activePanel: 'left',
    changedOnly: false,
    viewMode: null,
    ...overrides,
  }
}

const repository: Repository = {
  id: 7,
  name: 'myrepo',
  url: 'https://github.com/test/myrepo',
  description: 'test repo',
  default_branch: 'main',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

function makeSymbol(overrides: Partial<Symbol> = {}): Symbol {
  return {
    id: 1,
    name: 'doThing',
    kind: 'function',
    file_path: 'src/app.py',
    start_line: 10,
    end_line: 20,
    repository_id: 7,
    ...overrides,
  } as Symbol
}

function makeParams(overrides: Partial<UseBrowseRefsStateParams> = {}): UseBrowseRefsStateParams {
  return {
    urlState: makeUrlState(),
    repository,
    updateUrlParams: vi.fn(),
    navigate: vi.fn(),
    setRefPanel: vi.fn(),
    comparisonCommit: null,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useBrowseRefsState — URL restore effect', () => {
  it('restores searchByName when refs panel open, query present, repo loaded', () => {
    const { result } = renderHook(() =>
      useBrowseRefsState(
        makeParams({ urlState: makeUrlState({ refsPanelOpen: true, searchQuery: 'needle' }) })
      )
    )
    expect(result.current.searchByName).toEqual({ name: 'needle', repositoryId: 7 })
  })

  it('does not restore when the refs panel is closed', () => {
    const { result } = renderHook(() =>
      useBrowseRefsState(makeParams({ urlState: makeUrlState({ searchQuery: 'needle' }) }))
    )
    expect(result.current.searchByName).toBeNull()
  })

  it('does not restore without a search query', () => {
    const { result } = renderHook(() =>
      useBrowseRefsState(makeParams({ urlState: makeUrlState({ refsPanelOpen: true }) }))
    )
    expect(result.current.searchByName).toBeNull()
  })

  it('does not restore without a repository id', () => {
    const { result } = renderHook(() =>
      useBrowseRefsState(
        makeParams({
          repository: null,
          urlState: makeUrlState({ refsPanelOpen: true, searchQuery: 'needle' }),
        })
      )
    )
    expect(result.current.searchByName).toBeNull()
  })

  it('does not override an already-selected symbol', async () => {
    const sym = makeSymbol()
    const { result } = renderHook(() =>
      useBrowseRefsState(
        makeParams({ urlState: makeUrlState({ refsPanelOpen: true, searchQuery: 'needle' }) })
      )
    )
    act(() => result.current.openRefsPanel(sym, true))
    expect(result.current.selectedSymbol).toEqual(sym)
    // re-render: effect must not clobber the selected symbol with searchByName
    expect(result.current.searchByName).toBeNull()
  })
})

describe('useBrowseRefsState — panel open/close actions', () => {
  it('openRefsPanel sets the symbol and updates refs + q', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    const sym = makeSymbol({ name: 'foo' })
    act(() => result.current.openRefsPanel(sym, true))
    expect(result.current.selectedSymbol).toEqual(sym)
    expect(result.current.isDirectDefinition).toBe(true)
    expect(params.updateUrlParams).toHaveBeenCalledWith({ refs: '1', q: 'foo' })
  })

  it('openRefsPanelByName sets searchByName and updates refs + q', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.openRefsPanelByName('bar', 7))
    expect(result.current.searchByName).toEqual({ name: 'bar', repositoryId: 7 })
    expect(params.updateUrlParams).toHaveBeenCalledWith({ refs: '1', q: 'bar' })
  })

  it('closeRefsPanel clears state and removes refs param', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.openRefsPanel(makeSymbol(), true))
    act(() => result.current.closeRefsPanel())
    expect(result.current.selectedSymbol).toBeNull()
    expect(params.updateUrlParams).toHaveBeenLastCalledWith({ refs: null })
  })

  it('resetRefsPanel clears all three pieces of state', () => {
    const { result } = renderHook(() => useBrowseRefsState(makeParams()))
    act(() => result.current.openRefsPanel(makeSymbol(), true))
    act(() => result.current.resetRefsPanel())
    expect(result.current.selectedSymbol).toBeNull()
    expect(result.current.searchByName).toBeNull()
    expect(result.current.isDirectDefinition).toBe(false)
  })
})

describe('useBrowseRefsState — handleRefPanelChange', () => {
  it('converts the selected symbol to a name search when one exists (lines 110-111)', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.openRefsPanel(makeSymbol({ name: 'foo' }), true))
    act(() => result.current.handleRefPanelChange('right'))
    expect(result.current.searchByName).toEqual({ name: 'foo', repositoryId: 7 })
    expect(result.current.selectedSymbol).toBeNull()
    expect(params.setRefPanel).toHaveBeenCalledWith('right')
  })

  it('falls back to searchByName.name when no symbol is selected', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.openRefsPanelByName('bar', 7))
    act(() => result.current.handleRefPanelChange('left'))
    expect(result.current.searchByName).toEqual({ name: 'bar', repositoryId: 7 })
    expect(params.setRefPanel).toHaveBeenCalledWith('left')
  })

  it('only moves the panel when there is no symbol name', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.handleRefPanelChange('right'))
    expect(result.current.searchByName).toBeNull()
    expect(params.setRefPanel).toHaveBeenCalledWith('right')
  })

  it('does not convert when repository is missing', () => {
    const params = makeParams({ repository: null })
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.openRefsPanel(makeSymbol({ name: 'foo' }), true))
    act(() => result.current.handleRefPanelChange('right'))
    expect(result.current.searchByName).toBeNull()
    expect(params.setRefPanel).toHaveBeenCalledWith('right')
  })
})

describe('useBrowseRefsState — symbol click handlers', () => {
  it('handleSymbolClick fetches and opens the refs panel', async () => {
    const sym = makeSymbol({ name: 'clicked' })
    mockGetSymbol.mockResolvedValue(sym)
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleSymbolClick({ id: 5 } as FileSymbol)
    })
    expect(mockGetSymbol).toHaveBeenCalledWith(5)
    expect(result.current.selectedSymbol).toEqual(sym)
  })

  it('handleSymbolClick swallows fetch errors', async () => {
    mockGetSymbol.mockRejectedValue(new Error('boom'))
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { result } = renderHook(() => useBrowseRefsState(makeParams()))
    await act(async () => {
      await result.current.handleSymbolClick({ id: 5 } as FileSymbol)
    })
    expect(result.current.selectedSymbol).toBeNull()
    spy.mockRestore()
  })

  it('handleDiffSymbolClick on the right panel writes ap=r and rp=r (lines 146-147)', async () => {
    const sym = makeSymbol({ name: 'd' })
    mockGetSymbol.mockResolvedValue(sym)
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleDiffSymbolClick({ id: 9 } as FileSymbol, 'right')
    })
    expect(params.updateUrlParams).toHaveBeenCalledWith({ refs: '1', q: 'd', ap: 'r', rp: 'r' })
  })

  it('handleDiffSymbolClick on the left panel nulls ap and rp', async () => {
    mockGetSymbol.mockResolvedValue(makeSymbol({ name: 'd' }))
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleDiffSymbolClick({ id: 9 } as FileSymbol, 'left')
    })
    expect(params.updateUrlParams).toHaveBeenCalledWith({ refs: '1', q: 'd', ap: null, rp: null })
  })

  it('handleDiffSymbolClick swallows errors', async () => {
    mockGetSymbol.mockRejectedValue(new Error('boom'))
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleDiffSymbolClick({ id: 9 } as FileSymbol, 'right')
    })
    expect(params.updateUrlParams).not.toHaveBeenCalled()
    spy.mockRestore()
  })
})

describe('useBrowseRefsState — reference click handlers', () => {
  it('handleCodeReferenceClick with no target searches by name (lines 158-159)', async () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleCodeReferenceClick({
        target_symbol_id: null,
        reference_text: 'lookup',
      } as FileReference)
    })
    expect(params.updateUrlParams).toHaveBeenCalledWith({ refs: '1', q: 'lookup' })
    expect(mockGetSymbol).not.toHaveBeenCalled()
  })

  it('handleCodeReferenceClick with no target and no repo does nothing', async () => {
    const params = makeParams({ repository: null })
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleCodeReferenceClick({
        target_symbol_id: null,
        reference_text: 'lookup',
      } as FileReference)
    })
    expect(params.updateUrlParams).not.toHaveBeenCalled()
  })

  it('handleCodeReferenceClick with a target fetches the symbol', async () => {
    const sym = makeSymbol({ name: 'target' })
    mockGetSymbol.mockResolvedValue(sym)
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleCodeReferenceClick({
        target_symbol_id: 42,
        reference_text: 'x',
      } as FileReference)
    })
    expect(mockGetSymbol).toHaveBeenCalledWith(42)
    expect(result.current.selectedSymbol).toEqual(sym)
    expect(result.current.isDirectDefinition).toBe(false)
  })

  it('handleCodeReferenceClick swallows fetch errors', async () => {
    mockGetSymbol.mockRejectedValue(new Error('boom'))
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { result } = renderHook(() => useBrowseRefsState(makeParams()))
    await act(async () => {
      await result.current.handleCodeReferenceClick({
        target_symbol_id: 42,
        reference_text: 'x',
      } as FileReference)
    })
    expect(result.current.selectedSymbol).toBeNull()
    spy.mockRestore()
  })

  it('handleDiffReferenceClick with no target searches by name on the right panel (lines 176,185-186)', async () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleDiffReferenceClick(
        { target_symbol_id: null, reference_text: 'unr' } as FileReference,
        'right'
      )
    })
    expect(result.current.searchByName).toEqual({ name: 'unr', repositoryId: 7 })
    expect(params.updateUrlParams).toHaveBeenCalledWith({
      refs: '1',
      q: 'unr',
      ap: 'r',
      rp: 'r',
    })
  })

  it('handleDiffReferenceClick with no target and no repo is a no-op (line 178)', async () => {
    const params = makeParams({ repository: null })
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleDiffReferenceClick(
        { target_symbol_id: null, reference_text: 'unr' } as FileReference,
        'left'
      )
    })
    expect(params.updateUrlParams).not.toHaveBeenCalled()
  })

  it('handleDiffReferenceClick with a target fetches and writes left-panel params (lines 199-200)', async () => {
    const sym = makeSymbol({ name: 'resolved' })
    mockGetSymbol.mockResolvedValue(sym)
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleDiffReferenceClick(
        { target_symbol_id: 11, reference_text: 'x' } as FileReference,
        'left'
      )
    })
    expect(result.current.selectedSymbol).toEqual(sym)
    expect(params.updateUrlParams).toHaveBeenCalledWith({
      refs: '1',
      q: 'resolved',
      ap: null,
      rp: null,
    })
  })

  it('handleDiffReferenceClick swallows fetch errors', async () => {
    mockGetSymbol.mockRejectedValue(new Error('boom'))
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    await act(async () => {
      await result.current.handleDiffReferenceClick(
        { target_symbol_id: 11, reference_text: 'x' } as FileReference,
        'right'
      )
    })
    expect(params.updateUrlParams).not.toHaveBeenCalled()
    spy.mockRestore()
  })
})

describe('useBrowseRefsState — handleRefPanelClick', () => {
  it('navigates to the current panel commit/branch with drawer/co preserved (lines 226,229)', () => {
    const params = makeParams({
      urlState: makeUrlState({
        selectedCommit: 'cur',
        selectedBranch: 'main',
        drawerOpen: false,
        changedOnly: true,
      }),
    })
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() =>
      result.current.handleRefPanelClick({ source_file_path: 'src/other.py', source_line: 5 })
    )
    const url = navUrl(params.navigate)
    expect(url).toContain('/browse/myrepo/src/other.py')
    expect(url).toContain('line=5')
    expect(url).toContain('commit=cur')
    expect(url).toContain('branch=main')
    expect(url).toContain('drawer=0')
    expect(url).toContain('co=1')
  })

  it('uses the diff commit/branch when on the left panel in diff mode (lines 217-222)', () => {
    const params = makeParams({
      comparisonCommit: 'cmp',
      urlState: makeUrlState({
        diffMode: true,
        refPanel: 'left',
        diffCommit: null,
        diffBranch: 'devbr',
        selectedBranch: 'main',
      }),
    })
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() =>
      result.current.handleRefPanelClick({ source_file_path: 'src/other.py', source_line: 9 })
    )
    const url = navUrl(params.navigate)
    expect(url).toContain('commit=cmp')
    expect(url).toContain('branch=devbr')
  })

  it('is a no-op when the reference has no source file path', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.handleRefPanelClick({ source_file_path: null, source_line: 5 }))
    expect(params.navigate).not.toHaveBeenCalled()
  })
})

describe('useBrowseRefsState — handleDefinitionClick', () => {
  it('navigates to the definition with current commit/branch (lines 255,258)', () => {
    const params = makeParams({
      urlState: makeUrlState({
        selectedCommit: 'cur',
        selectedBranch: 'main',
        drawerOpen: false,
        changedOnly: true,
      }),
    })
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() =>
      result.current.handleDefinitionClick(makeSymbol({ file_path: 'src/def.py', start_line: 33 }))
    )
    const url = navUrl(params.navigate)
    expect(url).toContain('/browse/myrepo/src/def.py')
    expect(url).toContain('line=33')
    expect(url).toContain('commit=cur')
    expect(url).toContain('branch=main')
    expect(url).toContain('drawer=0')
    expect(url).toContain('co=1')
  })

  it('uses diff commit/branch on the left panel in diff mode', () => {
    const params = makeParams({
      comparisonCommit: 'cmp',
      urlState: makeUrlState({ diffMode: true, refPanel: 'left', diffCommit: 'dc' }),
    })
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.handleDefinitionClick(makeSymbol({ file_path: 'src/def.py' })))
    const url = navUrl(params.navigate)
    expect(url).toContain('commit=dc')
  })

  it('is a no-op when the symbol has no file path', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.handleDefinitionClick(makeSymbol({ file_path: null })))
    expect(params.navigate).not.toHaveBeenCalled()
  })
})

describe('useBrowseRefsState — navigateToSymbol', () => {
  it('navigates to the symbol location and opens the refs panel (line 278 true)', () => {
    const params = makeParams({
      urlState: makeUrlState({ selectedCommit: 'cur', selectedBranch: 'main', drawerOpen: false }),
    })
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() =>
      result.current.navigateToSymbol(
        makeSymbol({ name: 'sym', file_path: 'src/s.py', start_line: 8 })
      )
    )
    const url = navUrl(params.navigate)
    expect(url).toContain('/browse/myrepo/src/s.py')
    expect(url).toContain('line=8')
    expect(url).toContain('commit=cur')
    expect(url).toContain('branch=main')
    expect(url).toContain('drawer=0')
    expect(url).toContain('refs=1')
    expect(url).toContain('q=sym')
    expect(result.current.selectedSymbol?.name).toBe('sym')
  })

  it('opens the refs panel without navigating when the symbol has no file path (line 296 else)', () => {
    const params = makeParams()
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.navigateToSymbol(makeSymbol({ name: 'sym', file_path: null })))
    expect(params.navigate).not.toHaveBeenCalled()
    expect(params.updateUrlParams).toHaveBeenCalledWith({ refs: '1', q: 'sym' })
  })

  it('is a no-op without a repoName (line 269 guard)', () => {
    const params = makeParams({ urlState: makeUrlState({ repoName: undefined }) })
    const { result } = renderHook(() => useBrowseRefsState(params))
    act(() => result.current.navigateToSymbol(makeSymbol()))
    expect(params.navigate).not.toHaveBeenCalled()
    expect(params.updateUrlParams).not.toHaveBeenCalled()
  })
})
