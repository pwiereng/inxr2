import { useCallback, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import type { MutableRefObject } from 'react'
import type { BrowseUrlState } from './useBrowseState'

/**
 * Encode a file path for use in URLs, preserving directory separators.
 * Each path segment is encoded individually to handle special characters
 * (spaces, #, ?, %, etc.) while keeping slashes as path separators.
 */
export function encodeFilePath(path: string): string {
  return path
    .split('/')
    .map((segment) => encodeURIComponent(segment))
    .join('/')
}

export interface UseBrowseUrlStateRefs {
  resetRefsPanelRef: MutableRefObject<() => void>
  setErrorRef: MutableRefObject<(error: string | null) => void>
}

export interface UseBrowseUrlStateResult {
  urlState: BrowseUrlState
  searchParams: URLSearchParams
  navigate: ReturnType<typeof useNavigate>
  updateUrlParams: (updates: Record<string, string | null>, options?: { replace?: boolean }) => void
  setSearchQuery: (query: string) => void
  setDrawerOpen: (open: boolean) => void
  toggleDrawer: () => void
  setTreePanel: (panel: 'left' | 'right') => void
  setRefPanel: (panel: 'left' | 'right') => void
  setActivePanel: (panel: 'left' | 'right') => void
  setChangedOnly: (value: boolean) => void
  toggleChangedOnly: () => void
  setViewMode: (mode: 'rendered' | 'raw' | null) => void
  navigateToRepository: (repoName: string) => void
  navigateToFile: (path: string) => void
  navigateToLine: (line: number) => void
  handleDiffLineClick: (line: number, panel: 'left' | 'right') => void
  changeVersion: (commitHash: string | null) => void
  changeDiffVersion: (commitHash: string | null) => void
  changeBranch: (branchName: string | null) => void
  changeDiffBranch: (branchName: string | null) => void
  resetToFileTree: () => void
}

export function useBrowseUrlState(
  repoNameProp: string | undefined,
  refs: UseBrowseUrlStateRefs
): UseBrowseUrlStateResult {
  const { repoName: repoNameParam, '*': splatPath } = useParams<{ repoName: string; '*': string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  // Use prop if provided, otherwise use URL param
  const repoName = repoNameProp || repoNameParam

  // ========== URL-derived state ==========
  const urlState = useMemo<BrowseUrlState>(() => {
    const filePath = splatPath || searchParams.get('file') || null
    const highlightLine = searchParams.get('line')
      ? parseInt(searchParams.get('line')!, 10)
      : undefined
    const selectedCommit = searchParams.get('commit')
    const diffCommit = searchParams.get('diff')

    // Parse branch state
    const selectedBranch = searchParams.get('branch')
    const diffBranch = searchParams.get('diffBranch')

    // Parse URL-persisted UI state
    const searchQuery = searchParams.get('q') || ''
    const drawerOpen = searchParams.get('drawer') !== '0' // default true
    const refsPanelOpen = searchParams.get('refs') === '1' // default false
    const treePanel = searchParams.get('tp') === 'r' ? 'right' : 'left'
    const refPanel = searchParams.get('rp') === 'r' ? 'right' : 'left'
    const activePanel = searchParams.get('ap') === 'r' ? 'right' : 'left'
    const changedOnly = searchParams.get('co') === '1' // default false (show full tree)
    const viewParam = searchParams.get('view')
    const viewMode = viewParam === 'raw' ? 'raw' : viewParam === 'rendered' ? 'rendered' : null

    return {
      repoName,
      filePath,
      highlightLine,
      selectedCommit,
      diffCommit,
      diffMode: !!diffCommit || !!diffBranch,
      selectedBranch,
      diffBranch,
      searchQuery,
      drawerOpen,
      refsPanelOpen,
      treePanel,
      refPanel,
      activePanel,
      changedOnly,
      viewMode,
    }
  }, [repoName, splatPath, searchParams])

  // ========== URL Update Helper ==========
  const updateUrlParams = useCallback(
    (updates: Record<string, string | null>, options?: { replace?: boolean }) => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev)
          for (const [key, value] of Object.entries(updates)) {
            if (value === null || value === '') {
              params.delete(key)
            } else {
              params.set(key, value)
            }
          }
          return params
        },
        { replace: options?.replace ?? true }
      )
    },
    [setSearchParams]
  )

  // ========== URL-synced setters ==========
  const setSearchQuery = useCallback(
    (query: string) => updateUrlParams({ q: query || null }),
    [updateUrlParams]
  )

  const setDrawerOpen = useCallback(
    (open: boolean) => updateUrlParams({ drawer: open ? null : '0' }),
    [updateUrlParams]
  )

  const toggleDrawer = useCallback(
    () => updateUrlParams({ drawer: urlState.drawerOpen ? '0' : null }),
    [updateUrlParams, urlState.drawerOpen]
  )

  const setTreePanel = useCallback(
    (panel: 'left' | 'right') => updateUrlParams({ tp: panel === 'right' ? 'r' : null }),
    [updateUrlParams]
  )

  const setRefPanel = useCallback(
    (panel: 'left' | 'right') => updateUrlParams({ rp: panel === 'right' ? 'r' : null }),
    [updateUrlParams]
  )

  const setActivePanel = useCallback(
    (panel: 'left' | 'right') => updateUrlParams({ ap: panel === 'right' ? 'r' : null }),
    [updateUrlParams]
  )

  const setChangedOnly = useCallback(
    (value: boolean) => updateUrlParams({ co: value ? '1' : null }),
    [updateUrlParams]
  )

  const toggleChangedOnly = useCallback(
    () => updateUrlParams({ co: urlState.changedOnly ? null : '1' }),
    [updateUrlParams, urlState.changedOnly]
  )

  const setViewMode = useCallback(
    (mode: 'rendered' | 'raw' | null) => updateUrlParams({ view: mode }),
    [updateUrlParams]
  )

  // ========== Navigation Actions ==========

  const navigateToRepository = useCallback(
    (newRepoName: string) => {
      navigate(`/browse/${encodeURIComponent(newRepoName)}`)
    },
    [navigate]
  )

  const navigateToFile = useCallback(
    (path: string) => {
      const params = new URLSearchParams()
      if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
      // Preserve drawer state only - new file means new context, so clear search and refs
      if (!urlState.drawerOpen) params.set('drawer', '0')
      // Don't preserve refs, searchQuery - new file means new context
      // Exit diff mode when navigating to a new file (don't preserve diff, tp, rp, ap params)
      // Preserve branch and changed-files-only state
      if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
      if (urlState.changedOnly) params.set('co', '1')
      const query = params.toString()
      navigate(
        `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(path)}${query ? `?${query}` : ''}`
      )
    },
    [navigate, urlState]
  )

  const navigateToLine = useCallback(
    (line: number) => {
      if (urlState.filePath) {
        const params = new URLSearchParams()
        params.set('line', line.toString())
        if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
        if (urlState.diffCommit) params.set('diff', urlState.diffCommit)
        // Preserve UI state (but close refs panel and clear search query)
        if (!urlState.drawerOpen) params.set('drawer', '0')
        // Note: We intentionally do NOT preserve refsPanelOpen or searchQuery
        // when clicking a line number - the user wants to focus on that line
        // Preserve diff mode panel states
        if (urlState.treePanel === 'right') params.set('tp', 'r')
        if (urlState.refPanel === 'right') params.set('rp', 'r')
        if (urlState.activePanel === 'right') params.set('ap', 'r')
        // Preserve branch state
        if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
        if (urlState.diffBranch) params.set('diffBranch', urlState.diffBranch)
        // Preserve changedOnly state
        if (urlState.changedOnly) params.set('co', '1')
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`,
          {
            replace: true,
          }
        )
      }
    },
    [navigate, urlState]
  )

  const handleDiffLineClick = useCallback(
    (line: number, panel: 'left' | 'right') => {
      if (urlState.filePath) {
        const params = new URLSearchParams()
        params.set('line', line.toString())
        if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
        if (urlState.diffCommit) params.set('diff', urlState.diffCommit)
        // Preserve UI state
        if (!urlState.drawerOpen) params.set('drawer', '0')
        if (urlState.refsPanelOpen) params.set('refs', '1')
        if (urlState.searchQuery) params.set('q', urlState.searchQuery)
        // Set diff mode panel states including the clicked panel
        if (urlState.treePanel === 'right') params.set('tp', 'r')
        if (urlState.refPanel === 'right') params.set('rp', 'r')
        // Explicitly handle active panel:
        // - right panel: set 'ap=r'
        // - left panel: ensure 'ap' is not present (left is default)
        if (panel === 'right') {
          params.set('ap', 'r')
        } else {
          params.delete('ap')
        }
        // Preserve branch state
        if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
        if (urlState.diffBranch) params.set('diffBranch', urlState.diffBranch)
        // Preserve changedOnly state
        if (urlState.changedOnly) params.set('co', '1')
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`,
          { replace: true }
        )
      }
    },
    [navigate, urlState]
  )

  // ========== Version Change Actions ==========

  const changeVersion = useCallback(
    (commitHash: string | null) => {
      if (!urlState.repoName) return
      refs.resetRefsPanelRef.current()
      const params = new URLSearchParams()
      if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
      if (commitHash) params.set('commit', commitHash)
      if (urlState.diffCommit) params.set('diff', urlState.diffCommit)
      // Preserve drawer state only - version change means new context, clear search and refs
      if (!urlState.drawerOpen) params.set('drawer', '0')
      // Don't preserve searchQuery - version change invalidates search context
      // Preserve diff mode panel states
      if (urlState.treePanel === 'right') params.set('tp', 'r')
      if (urlState.refPanel === 'right') params.set('rp', 'r')
      if (urlState.activePanel === 'right') params.set('ap', 'r')
      // Preserve branch state
      if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
      if (urlState.diffBranch) params.set('diffBranch', urlState.diffBranch)
      // Preserve changedOnly state
      if (urlState.changedOnly) params.set('co', '1')
      const basePath = urlState.filePath
        ? `/browse/${encodeURIComponent(urlState.repoName)}/${encodeFilePath(urlState.filePath)}`
        : `/browse/${encodeURIComponent(urlState.repoName)}`
      const query = params.toString()
      navigate(`${basePath}${query ? `?${query}` : ''}`)
    },
    [navigate, urlState, refs.resetRefsPanelRef]
  )

  const changeDiffVersion = useCallback(
    (commitHash: string | null) => {
      if (!urlState.filePath) return
      refs.resetRefsPanelRef.current()
      const params = new URLSearchParams()
      if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
      if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
      if (commitHash) params.set('diff', commitHash)
      // Preserve drawer state only - version change means new context, clear search and refs
      if (!urlState.drawerOpen) params.set('drawer', '0')
      // Don't preserve searchQuery - version change invalidates search context
      // Preserve diff mode panel states
      if (urlState.treePanel === 'right') params.set('tp', 'r')
      if (urlState.refPanel === 'right') params.set('rp', 'r')
      if (urlState.activePanel === 'right') params.set('ap', 'r')
      // Preserve branch state
      if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
      if (urlState.diffBranch) params.set('diffBranch', urlState.diffBranch)
      // Preserve changedOnly state
      if (urlState.changedOnly) params.set('co', '1')
      navigate(
        `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
      )
    },
    [navigate, urlState, refs.resetRefsPanelRef]
  )

  // ========== Branch Change Actions ==========

  const changeBranch = useCallback(
    (branchName: string | null) => {
      refs.resetRefsPanelRef.current()
      const params = new URLSearchParams()
      // Clear commit when changing branch (will resolve to branch's latest commit)
      if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
      if (branchName) params.set('branch', branchName)
      // Don't preserve commit - branch change means new commit context
      // Preserve diff state
      if (urlState.diffCommit) params.set('diff', urlState.diffCommit)
      if (urlState.diffBranch) params.set('diffBranch', urlState.diffBranch)
      // Preserve drawer state
      if (!urlState.drawerOpen) params.set('drawer', '0')
      // Preserve diff mode panel states
      if (urlState.treePanel === 'right') params.set('tp', 'r')
      if (urlState.refPanel === 'right') params.set('rp', 'r')
      if (urlState.activePanel === 'right') params.set('ap', 'r')

      if (urlState.filePath) {
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
        )
      } else {
        navigate(`/browse/${encodeURIComponent(urlState.repoName!)}?${params}`)
      }
    },
    [navigate, urlState, refs.resetRefsPanelRef]
  )

  const changeDiffBranch = useCallback(
    (branchName: string | null) => {
      if (!urlState.filePath) return
      refs.resetRefsPanelRef.current()
      const params = new URLSearchParams()
      if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
      if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
      if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
      // Set diff branch or preserve existing diff commit to stay in diff mode
      if (branchName) {
        params.set('diffBranch', branchName)
        // Clear diffCommit - will resolve to branch's latest
      } else if (urlState.diffCommit) {
        // Switching back to same branch - preserve diff commit
        params.set('diff', urlState.diffCommit)
      }
      // Preserve drawer state
      if (!urlState.drawerOpen) params.set('drawer', '0')
      // Preserve diff mode panel states
      if (urlState.treePanel === 'right') params.set('tp', 'r')
      if (urlState.refPanel === 'right') params.set('rp', 'r')
      if (urlState.activePanel === 'right') params.set('ap', 'r')
      // Preserve changedOnly state
      if (urlState.changedOnly) params.set('co', '1')
      navigate(
        `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
      )
    },
    [navigate, urlState, refs.resetRefsPanelRef]
  )

  const resetToFileTree = useCallback(() => {
    if (!urlState.repoName) return
    refs.resetRefsPanelRef.current()
    refs.setErrorRef.current(null)
    const params = new URLSearchParams()
    // Preserve only branch, drawer, and changedOnly
    if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
    if (!urlState.drawerOpen) params.set('drawer', '0')
    if (urlState.changedOnly) params.set('co', '1')
    const query = params.toString()
    navigate(`/browse/${encodeURIComponent(urlState.repoName)}${query ? `?${query}` : ''}`)
  }, [navigate, urlState, refs.resetRefsPanelRef, refs.setErrorRef])

  return {
    urlState,
    searchParams,
    navigate,
    updateUrlParams,
    setSearchQuery,
    setDrawerOpen,
    toggleDrawer,
    setTreePanel,
    setRefPanel,
    setActivePanel,
    setChangedOnly,
    toggleChangedOnly,
    setViewMode,
    navigateToRepository,
    navigateToFile,
    navigateToLine,
    handleDiffLineClick,
    changeVersion,
    changeDiffVersion,
    changeBranch,
    changeDiffBranch,
    resetToFileTree,
  }
}
