import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { useBrowseUrlState, encodeFilePath, type UseBrowseUrlStateRefs } from './useBrowseUrlState'

// ---------------------------------------------------------------------------
// Location probe — records the live router location so navigation handlers can
// be asserted against the FULL destination URL (Convention #4), not a prefix.
// ---------------------------------------------------------------------------
let lastLocation = { pathname: '', search: '' }

function LocationProbe() {
  const loc = useLocation()
  lastLocation = { pathname: loc.pathname, search: loc.search }
  return null
}

function makeRefs(): UseBrowseUrlStateRefs {
  return {
    resetRefsPanelRef: { current: vi.fn() },
    setErrorRef: { current: vi.fn() },
  }
}

/**
 * Render useBrowseUrlState inside a MemoryRouter at `entry`. The hook is mounted
 * under a `/browse/:repoName/*` route so useParams resolves repoName + splat;
 * a catch-all route handles repoName-less cases (early-return guards).
 */
function renderUrlState(entry: string, repoNameProp?: string) {
  const refs = makeRefs()
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(
      MemoryRouter,
      { initialEntries: [entry] },
      createElement(
        Routes,
        null,
        createElement(Route, {
          path: '/browse/:repoName/*',
          element: createElement('div', null, children as ReactNode, createElement(LocationProbe)),
        }),
        createElement(Route, {
          path: '*',
          element: createElement('div', null, children as ReactNode, createElement(LocationProbe)),
        })
      )
    )
  const { result } = renderHook(() => useBrowseUrlState(repoNameProp, refs), { wrapper })
  return { result, refs }
}

function loc() {
  return lastLocation.pathname + lastLocation.search
}

// A URL that has EVERY optional param set, so navigation handlers exercise the
// "truthy" side of every preservation branch in one shot.
const FULL =
  '/browse/myrepo/src/app.py?commit=abc123&diff=def456&line=42&branch=main&diffBranch=dev' +
  '&drawer=0&refs=1&q=needle&tp=r&rp=r&ap=r&co=1'

describe('encodeFilePath', () => {
  it('encodes each segment but preserves slashes', () => {
    expect(encodeFilePath('src/my file.py')).toBe('src/my%20file.py')
    expect(encodeFilePath('a/b#c?d/e')).toBe('a/b%23c%3Fd/e')
  })
})

describe('useBrowseUrlState — urlState parsing', () => {
  beforeEach(() => {
    lastLocation = { pathname: '', search: '' }
  })

  it('parses a file path from the splat', () => {
    const { result } = renderUrlState('/browse/myrepo/src/app.py')
    expect(result.current.urlState.filePath).toBe('src/app.py')
    expect(result.current.urlState.directoryPath).toBeNull()
  })

  it('falls back to the ?file= param when there is no splat (line 73)', () => {
    const { result } = renderUrlState('/browse/myrepo?file=src/lib.py')
    expect(result.current.urlState.filePath).toBe('src/lib.py')
  })

  it('treats a trailing-slash path as a directory (lines 78-79)', () => {
    const { result } = renderUrlState('/browse/myrepo/src/sub/')
    expect(result.current.urlState.filePath).toBeNull()
    expect(result.current.urlState.directoryPath).toBe('src/sub')
  })

  it('treats the empty splat as the root directory', () => {
    const { result } = renderUrlState('/browse/myrepo')
    expect(result.current.urlState.filePath).toBeNull()
    expect(result.current.urlState.directoryPath).toBeNull()
  })

  it('parses highlightLine, commits, branches and diff mode', () => {
    const { result } = renderUrlState(FULL)
    const s = result.current.urlState
    expect(s.highlightLine).toBe(42)
    expect(s.selectedCommit).toBe('abc123')
    expect(s.diffCommit).toBe('def456')
    expect(s.selectedBranch).toBe('main')
    expect(s.diffBranch).toBe('dev')
    expect(s.diffMode).toBe(true)
  })

  it('enters diff mode from diffBranch alone (no diffCommit)', () => {
    const { result } = renderUrlState('/browse/myrepo/src/app.py?diffBranch=dev')
    expect(result.current.urlState.diffMode).toBe(true)
  })

  it('parses persisted UI state from query params (right panels, refs, co, raw view)', () => {
    const { result } = renderUrlState(FULL)
    const s = result.current.urlState
    expect(s.drawerOpen).toBe(false)
    expect(s.refsPanelOpen).toBe(true)
    expect(s.treePanel).toBe('right')
    expect(s.refPanel).toBe('right')
    expect(s.activePanel).toBe('right')
    expect(s.changedOnly).toBe(true)
    expect(s.searchQuery).toBe('needle')
  })

  it('defaults UI state when params are absent (left panels, drawer open, rendered/null view)', () => {
    const { result } = renderUrlState('/browse/myrepo/src/app.py?view=rendered')
    const s = result.current.urlState
    expect(s.drawerOpen).toBe(true)
    expect(s.refsPanelOpen).toBe(false)
    expect(s.treePanel).toBe('left')
    expect(s.refPanel).toBe('left')
    expect(s.activePanel).toBe('left')
    expect(s.changedOnly).toBe(false)
    expect(s.viewMode).toBe('rendered')
  })

  it('parses raw view mode and leaves an unknown view as null', () => {
    expect(renderUrlState('/browse/myrepo/x.py?view=raw').result.current.urlState.viewMode).toBe(
      'raw'
    )
    expect(
      renderUrlState('/browse/myrepo/x.py?view=zzz').result.current.urlState.viewMode
    ).toBeNull()
  })

  it('prefers repoNameProp over the URL param', () => {
    const { result } = renderUrlState('/browse/urlrepo/x.py', 'proprepo')
    expect(result.current.urlState.repoName).toBe('proprepo')
  })
})

describe('useBrowseUrlState — simple URL setters', () => {
  beforeEach(() => {
    lastLocation = { pathname: '', search: '' }
  })

  it('setSearchQuery sets q, and clears it when empty', () => {
    const { result } = renderUrlState('/browse/myrepo/x.py')
    act(() => result.current.setSearchQuery('hello'))
    expect(loc()).toContain('q=hello')
    act(() => result.current.setSearchQuery(''))
    expect(loc()).not.toContain('q=')
  })

  it('setDrawerOpen(false) writes drawer=0; (true) clears it (line 150)', () => {
    const { result } = renderUrlState('/browse/myrepo/x.py')
    act(() => result.current.setDrawerOpen(false))
    expect(loc()).toContain('drawer=0')
    act(() => result.current.setDrawerOpen(true))
    expect(loc()).not.toContain('drawer=0')
  })

  it('toggleDrawer flips drawer based on current state (line 155)', () => {
    const open = renderUrlState('/browse/myrepo/x.py')
    act(() => open.result.current.toggleDrawer())
    expect(loc()).toContain('drawer=0')

    lastLocation = { pathname: '', search: '' }
    const closed = renderUrlState('/browse/myrepo/x.py?drawer=0')
    act(() => closed.result.current.toggleDrawer())
    expect(loc()).not.toContain('drawer=0')
  })

  it('setTreePanel/setRefPanel/setActivePanel write r for right, clear for left (lines 160,165,170)', () => {
    const { result } = renderUrlState('/browse/myrepo/x.py')
    act(() => result.current.setTreePanel('right'))
    expect(loc()).toContain('tp=r')
    act(() => result.current.setTreePanel('left'))
    expect(loc()).not.toContain('tp=r')

    act(() => result.current.setRefPanel('right'))
    expect(loc()).toContain('rp=r')
    act(() => result.current.setRefPanel('left'))
    expect(loc()).not.toContain('rp=r')

    act(() => result.current.setActivePanel('right'))
    expect(loc()).toContain('ap=r')
    act(() => result.current.setActivePanel('left'))
    expect(loc()).not.toContain('ap=r')
  })

  it('setChangedOnly/toggleChangedOnly manage the co param', () => {
    const { result } = renderUrlState('/browse/myrepo/x.py')
    act(() => result.current.setChangedOnly(true))
    expect(loc()).toContain('co=1')
    act(() => result.current.setChangedOnly(false))
    expect(loc()).not.toContain('co=1')

    const on = renderUrlState('/browse/myrepo/x.py?co=1')
    act(() => on.result.current.toggleChangedOnly())
    expect(loc()).not.toContain('co=1')
  })

  it('setViewMode sets and clears the view param', () => {
    const { result } = renderUrlState('/browse/myrepo/x.py')
    act(() => result.current.setViewMode('raw'))
    expect(loc()).toContain('view=raw')
    act(() => result.current.setViewMode(null))
    expect(loc()).not.toContain('view=')
  })
})

describe('useBrowseUrlState — navigation actions', () => {
  beforeEach(() => {
    lastLocation = { pathname: '', search: '' }
  })

  it('navigateToRepository goes to the repo root', () => {
    const { result } = renderUrlState('/browse/myrepo/x.py')
    act(() => result.current.navigateToRepository('other repo'))
    expect(lastLocation.pathname).toBe('/browse/other%20repo')
  })

  it('navigateToFile preserves commit, drawer, branch and co (lines 203,221-224)', () => {
    const { result } = renderUrlState(FULL)
    act(() => result.current.navigateToFile('src/next.py'))
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/next.py')
    expect(loc()).toContain('commit=abc123')
    expect(loc()).toContain('drawer=0')
    expect(loc()).toContain('branch=main')
    expect(loc()).toContain('co=1')
    // new file = new context: diff/refs/q/line are dropped
    expect(loc()).not.toContain('diff=')
    expect(loc()).not.toContain('refs=1')
    expect(loc()).not.toContain('q=')
  })

  it('navigateToFile from minimal state preserves nothing extra', () => {
    const { result } = renderUrlState('/browse/myrepo/x.py')
    act(() => result.current.navigateToFile('y.py'))
    expect(lastLocation.pathname).toBe('/browse/myrepo/y.py')
    expect(lastLocation.search).toBe('')
  })

  it('navigateToDirectory clears the error, adds a trailing slash and preserves context', () => {
    const { result, refs } = renderUrlState(FULL)
    act(() => result.current.navigateToDirectory('src/sub'))
    expect(refs.setErrorRef.current).toHaveBeenCalledWith(null)
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/sub/')
    expect(loc()).toContain('commit=abc123')
    expect(loc()).toContain('drawer=0')
    expect(loc()).toContain('branch=main')
    expect(loc()).toContain('co=1')
  })

  it('navigateToLine preserves line/commit/diff/panels/branches/co when on a file (lines 240-251)', () => {
    const { result } = renderUrlState(FULL)
    act(() => result.current.navigateToLine(99))
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/app.py')
    expect(loc()).toContain('line=99')
    expect(loc()).toContain('commit=abc123')
    expect(loc()).toContain('diff=def456')
    expect(loc()).toContain('drawer=0')
    expect(loc()).toContain('tp=r')
    expect(loc()).toContain('rp=r')
    expect(loc()).toContain('ap=r')
    expect(loc()).toContain('branch=main')
    expect(loc()).toContain('diffBranch=dev')
    expect(loc()).toContain('co=1')
    // refs/q intentionally dropped
    expect(loc()).not.toContain('refs=1')
    expect(loc()).not.toContain('q=')
  })

  it('navigateToLine is a no-op when there is no file (directory mode)', () => {
    const { result } = renderUrlState('/browse/myrepo/src/sub/')
    act(() => result.current.navigateToLine(5))
    // location unchanged from the directory entry
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/sub/')
    expect(loc()).not.toContain('line=')
  })

  it('handleDiffLineClick on the right panel sets ap=r and preserves refs/q (lines 273-284,289)', () => {
    const { result } = renderUrlState(FULL)
    act(() => result.current.handleDiffLineClick(7, 'right'))
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/app.py')
    expect(loc()).toContain('line=7')
    expect(loc()).toContain('ap=r')
    expect(loc()).toContain('refs=1')
    expect(loc()).toContain('q=needle')
    expect(loc()).toContain('tp=r')
    expect(loc()).toContain('rp=r')
    expect(loc()).toContain('diffBranch=dev')
  })

  it('handleDiffLineClick on the left panel removes ap (line 284-285 else branch)', () => {
    const { result } = renderUrlState(FULL)
    act(() => result.current.handleDiffLineClick(7, 'left'))
    expect(loc()).not.toContain('ap=r')
  })

  it('handleDiffLineClick is a no-op without a file', () => {
    const { result } = renderUrlState('/browse/myrepo/src/sub/')
    act(() => result.current.handleDiffLineClick(7, 'right'))
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/sub/')
  })
})

describe('useBrowseUrlState — version and branch changes', () => {
  beforeEach(() => {
    lastLocation = { pathname: '', search: '' }
  })

  it('changeVersion preserves line/diff/panels/branches/co and resets refs (lines 308-322)', () => {
    const { result, refs } = renderUrlState(FULL)
    act(() => result.current.changeVersion('newsha'))
    expect(refs.resetRefsPanelRef.current).toHaveBeenCalled()
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/app.py')
    expect(loc()).toContain('commit=newsha')
    expect(loc()).toContain('line=42')
    expect(loc()).toContain('diff=def456')
    expect(loc()).toContain('drawer=0')
    expect(loc()).toContain('tp=r')
    expect(loc()).toContain('branch=main')
    expect(loc()).toContain('co=1')
  })

  it('changeVersion(null) drops the commit param', () => {
    const { result } = renderUrlState('/browse/myrepo/src/app.py?commit=abc123')
    act(() => result.current.changeVersion(null))
    expect(loc()).not.toContain('commit=')
  })

  it('changeVersion is a no-op without a repoName (line 305 guard)', () => {
    const { result, refs } = renderUrlState('/somewhere-else')
    act(() => result.current.changeVersion('x'))
    expect(refs.resetRefsPanelRef.current).not.toHaveBeenCalled()
  })

  it('changeVersion builds a directory base path when in directory mode (line 25)', () => {
    const { result } = renderUrlState('/browse/myrepo/src/sub/?branch=main')
    act(() => result.current.changeVersion('sha'))
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/sub/')
    expect(loc()).toContain('commit=sha')
  })

  it('changeVersion builds the repo root base path when no file/dir', () => {
    const { result } = renderUrlState('/browse/myrepo')
    act(() => result.current.changeVersion('sha'))
    expect(lastLocation.pathname).toBe('/browse/myrepo')
    expect(loc()).toContain('commit=sha')
  })

  it('changeDiffVersion preserves context and sets diff (lines 335-347)', () => {
    const { result, refs } = renderUrlState(FULL)
    act(() => result.current.changeDiffVersion('diffsha'))
    expect(refs.resetRefsPanelRef.current).toHaveBeenCalled()
    expect(lastLocation.pathname).toBe('/browse/myrepo/src/app.py')
    expect(loc()).toContain('diff=diffsha')
    expect(loc()).toContain('commit=abc123')
    expect(loc()).toContain('line=42')
    expect(loc()).toContain('tp=r')
    expect(loc()).toContain('branch=main')
    expect(loc()).toContain('co=1')
  })

  it('changeDiffVersion is a no-op without a file (line 332 guard)', () => {
    const { result, refs } = renderUrlState('/browse/myrepo/src/sub/')
    act(() => result.current.changeDiffVersion('x'))
    expect(refs.resetRefsPanelRef.current).not.toHaveBeenCalled()
  })

  it('changeBranch preserves line/commit/diff/panels/co (lines 363-375)', () => {
    const { result, refs } = renderUrlState(FULL)
    act(() => result.current.changeBranch('feature'))
    expect(refs.resetRefsPanelRef.current).toHaveBeenCalled()
    expect(loc()).toContain('branch=feature')
    expect(loc()).toContain('line=42')
    expect(loc()).toContain('commit=abc123')
    expect(loc()).toContain('diff=def456')
    expect(loc()).toContain('diffBranch=dev')
    expect(loc()).toContain('drawer=0')
    expect(loc()).toContain('tp=r')
    expect(loc()).toContain('co=1')
  })

  it('changeBranch(null) drops the branch param', () => {
    const { result } = renderUrlState('/browse/myrepo/src/app.py?branch=main')
    act(() => result.current.changeBranch(null))
    expect(loc()).not.toContain('branch=')
  })

  it('changeDiffBranch sets diffBranch and clears diff commit (lines 391-407)', () => {
    const { result, refs } = renderUrlState(FULL)
    act(() => result.current.changeDiffBranch('release'))
    expect(refs.resetRefsPanelRef.current).toHaveBeenCalled()
    expect(loc()).toContain('diffBranch=release')
    expect(loc()).not.toContain('diff=def456')
    expect(loc()).toContain('branch=main')
    expect(loc()).toContain('line=42')
    expect(loc()).toContain('commit=abc123')
    expect(loc()).toContain('tp=r')
    expect(loc()).toContain('co=1')
  })

  it('changeDiffBranch(null) preserves an existing diff commit (line 398 else branch)', () => {
    const { result } = renderUrlState('/browse/myrepo/src/app.py?diff=def456')
    act(() => result.current.changeDiffBranch(null))
    expect(loc()).toContain('diff=def456')
    expect(loc()).not.toContain('diffBranch=')
  })

  it('changeDiffBranch is a no-op without a file (line 388 guard)', () => {
    const { result, refs } = renderUrlState('/browse/myrepo/src/sub/')
    act(() => result.current.changeDiffBranch('x'))
    expect(refs.resetRefsPanelRef.current).not.toHaveBeenCalled()
  })
})

describe('useBrowseUrlState — resetToFileTree', () => {
  beforeEach(() => {
    lastLocation = { pathname: '', search: '' }
  })

  it('resets to the repo root preserving only branch/drawer/co (lines 422-425)', () => {
    const { result, refs } = renderUrlState(FULL)
    act(() => result.current.resetToFileTree())
    expect(refs.resetRefsPanelRef.current).toHaveBeenCalled()
    expect(refs.setErrorRef.current).toHaveBeenCalledWith(null)
    expect(lastLocation.pathname).toBe('/browse/myrepo')
    expect(loc()).toContain('branch=main')
    expect(loc()).toContain('drawer=0')
    expect(loc()).toContain('co=1')
    expect(loc()).not.toContain('commit=')
    expect(loc()).not.toContain('line=')
  })

  it('resetToFileTree from a clean state yields a bare repo URL', () => {
    const { result } = renderUrlState('/browse/myrepo/src/app.py')
    act(() => result.current.resetToFileTree())
    expect(lastLocation.pathname).toBe('/browse/myrepo')
    expect(lastLocation.search).toBe('')
  })

  it('resetToFileTree is a no-op without a repoName (line 418 guard)', () => {
    const { result, refs } = renderUrlState('/somewhere-else')
    act(() => result.current.resetToFileTree())
    expect(refs.resetRefsPanelRef.current).not.toHaveBeenCalled()
  })

  it('updateUrlParams can opt out of replace via options', () => {
    const { result } = renderUrlState('/browse/myrepo/x.py')
    act(() => result.current.updateUrlParams({ custom: 'v' }, { replace: false }))
    expect(loc()).toContain('custom=v')
  })
})
