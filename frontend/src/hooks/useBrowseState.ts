/**
 * Custom hook for managing Browse page state.
 *
 * This is a thin orchestrator that delegates to focused sub-hooks:
 * - useBrowseUrlState: URL parsing, setters, navigation actions
 * - useBrowseDiffState: Diff data + diff mode actions
 * - useBrowseData: Data fetching & loading effects
 * - useBrowseRefsState: References panel state, actions, click handlers
 *
 * Cross-hook dependencies are resolved via React refs that are updated
 * after all hooks return. Refs are only read inside callbacks (never
 * during render), so this is safe.
 */

import { useRef, useMemo } from 'react'
import type {
  FileContent,
  FileReference,
  FileSymbol,
  FileVersion,
  RawFileContent,
  Repository,
  Symbol,
  TreeNode,
} from '@/lib/api'
import { useBrowseUrlState } from './useBrowseUrlState'
import { useBrowseDiffState } from './useBrowseDiffState'
import { useBrowseData } from './useBrowseData'
import { useBrowseRefsState } from './useBrowseRefsState'

// ============================================================================
// Types
// ============================================================================

/**
 * State derived from URL parameters for bookmarkability.
 *
 * URL params: line, commit, diff, q, drawer, refs, tp, rp, ap, branch, diffBranch, view
 *
 * Note: We use `q` (search query) for refs panel state instead of symbol IDs
 * because symbol IDs can change between indexing runs, making name-based
 * search more robust for bookmarks.
 */
export interface BrowseUrlState {
  repoName: string | undefined
  filePath: string | null
  highlightLine: number | undefined
  selectedCommit: string | null
  diffCommit: string | null
  diffMode: boolean
  // Branch state (branch, diffBranch params)
  selectedBranch: string | null // branch param - primary branch for browsing
  diffBranch: string | null // diffBranch param - branch for diff comparison
  // URL-persisted UI state (q, drawer, refs, tp, rp, ap, co, view)
  searchQuery: string // q param - used for both search and refs panel restoration
  drawerOpen: boolean // drawer param (0 = closed, absent = open)
  refsPanelOpen: boolean // refs param (1 = open, absent = closed)
  treePanel: 'left' | 'right' // tp param (r = right, absent = left)
  refPanel: 'left' | 'right' // rp param (r = right, absent = left)
  activePanel: 'left' | 'right' // ap param (r = right, absent = left)
  changedOnly: boolean // co param (1 = show only files changed in commit, absent = full tree)
  viewMode: 'rendered' | 'raw' | null // view param (raw = raw source, absent = default per file type)
}

export interface BrowseDataState {
  allRepositories: Repository[]
  repository: Repository | null
  treeNodes: TreeNode[]
  fileContent: FileContent | null
  fileSymbols: FileSymbol[]
  fileReferences: FileReference[]
  fileVersions: FileVersion[]
  rawContent: RawFileContent | null
}

export interface BrowseDiffState {
  diffContent: FileContent | null
  diffSymbols: FileSymbol[]
  diffReferences: FileReference[]
  activePanel: 'left' | 'right'
  treePanel: 'left' | 'right'
  refPanel: 'left' | 'right'
}

export interface BrowseUIState {
  drawerOpen: boolean
  refsPanelOpen: boolean
  loading: boolean
  fileLoading: boolean
  diffLoading: boolean
  error: string | null
  searchQuery: string
}

export interface BrowseRefsState {
  selectedSymbol: Symbol | null
  isDirectDefinition: boolean
  searchByName: { name: string; repositoryId: number } | null
}

export interface BrowseActions {
  // Navigation
  navigateToRepository: (repoName: string) => void
  navigateToFile: (path: string) => void
  navigateToSymbol: (symbol: Symbol) => void
  navigateToLine: (line: number) => void
  resetToFileTree: () => void

  // Diff mode
  enterDiffMode: () => void
  exitDiffMode: () => void
  closePanel: (panel: 'left' | 'right') => void
  setActivePanel: (panel: 'left' | 'right') => void
  setTreePanel: (panel: 'left' | 'right') => void

  // Branch changes
  changeBranch: (branchName: string | null) => void
  changeDiffBranch: (branchName: string | null) => void

  // Version changes
  changeVersion: (commitHash: string | null) => void
  changeDiffVersion: (commitHash: string | null) => void

  // UI toggles
  toggleDrawer: () => void
  setDrawerOpen: (open: boolean) => void
  toggleChangedOnly: () => void
  setChangedOnly: (value: boolean) => void

  // References panel
  openRefsPanel: (symbol: Symbol, isDirect: boolean) => void
  openRefsPanelByName: (name: string, repositoryId: number) => void
  closeRefsPanel: () => void
  setRefPanel: (panel: 'left' | 'right') => void
  handleRefPanelChange: (panel: 'left' | 'right') => void

  // View mode
  setViewMode: (mode: 'rendered' | 'raw' | null) => void

  // Search
  setSearchQuery: (query: string) => void

  // Symbol/Reference clicks
  handleSymbolClick: (fileSymbol: FileSymbol) => Promise<void>
  handleDiffSymbolClick: (fileSymbol: FileSymbol, panel: 'left' | 'right') => Promise<void>
  handleCodeReferenceClick: (ref: FileReference) => Promise<void>
  handleDiffReferenceClick: (ref: FileReference, panel: 'left' | 'right') => Promise<void>
  handleRefPanelClick: (reference: { source_file_path: string | null; source_line: number }) => void
  handleDefinitionClick: (sym: Symbol) => void
  handleDiffLineClick: (line: number, panel: 'left' | 'right') => void
}

export interface BrowseComputedState {
  leftCommit: string | undefined
  rightCommit: string | null
  treeCommit: string | null | undefined
  refCommit: string | null | undefined
  currentCommitHash: string | undefined
  /** True if file was changed at the selected commit (appears in file versions) */
  fileChangedInCommit: boolean
}

// ============================================================================
// Hook Implementation
// ============================================================================

interface UseBrowseStateResult {
  urlState: BrowseUrlState
  dataState: BrowseDataState
  diffState: BrowseDiffState
  uiState: BrowseUIState
  refsState: BrowseRefsState
  computedState: BrowseComputedState
  actions: BrowseActions
}

export function useBrowseState(repoNameProp?: string): UseBrowseStateResult {
  // ========== Refs for cross-hook communication ==========
  const resetRefsPanelRef = useRef<() => void>(() => {})
  const setErrorRef = useRef<(error: string | null) => void>(() => {})
  const fileVersionsRef = useRef<FileVersion[]>([])
  const repositoryRef = useRef<Repository | null>(null)
  const rightCommitRef = useRef<string | null>(null)

  // ========== 1. URL State ==========
  const urlResult = useBrowseUrlState(repoNameProp, { resetRefsPanelRef, setErrorRef })

  // ========== 2. Diff State ==========
  const diffResult = useBrowseDiffState({
    urlState: urlResult.urlState,
    navigate: urlResult.navigate,
    refs: { fileVersionsRef, repositoryRef, rightCommitRef },
  })

  // ========== 3. Data State ==========
  const dataResult = useBrowseData({
    urlState: urlResult.urlState,
    diffFileVersions: diffResult.diffFileVersions,
    navigate: urlResult.navigate,
    searchParams: urlResult.searchParams,
  })

  // ========== 4. Computed State ==========
  const computedState = useMemo<BrowseComputedState>(() => {
    const leftCommit =
      urlResult.urlState.selectedCommit ||
      dataResult.latestBranchCommit ||
      dataResult.fileVersions[0]?.commit_hash
    const rightCommit =
      urlResult.urlState.diffCommit || diffResult.diffFileVersions[0]?.commit_hash || null
    const treeCommit = urlResult.urlState.diffMode
      ? urlResult.urlState.treePanel === 'left'
        ? leftCommit
        : rightCommit
      : urlResult.urlState.selectedCommit || dataResult.latestBranchCommit
    const refCommit = urlResult.urlState.diffMode
      ? urlResult.urlState.refPanel === 'left'
        ? leftCommit
        : rightCommit
      : urlResult.urlState.selectedCommit
    const currentCommitHash =
      urlResult.urlState.selectedCommit || dataResult.fileVersions[0]?.commit_hash

    const fileChangedInCommit = urlResult.urlState.changedOnly
      ? true
      : urlResult.urlState.selectedCommit
        ? dataResult.fileVersions.some((v) => v.commit_hash === urlResult.urlState.selectedCommit)
        : true

    return {
      leftCommit,
      rightCommit,
      treeCommit,
      refCommit,
      currentCommitHash,
      fileChangedInCommit,
    }
  }, [
    urlResult.urlState,
    dataResult.fileVersions,
    diffResult.diffFileVersions,
    dataResult.latestBranchCommit,
  ])

  // ========== 5. Refs State ==========
  const refsResult = useBrowseRefsState({
    urlState: urlResult.urlState,
    repository: dataResult.repository,
    updateUrlParams: urlResult.updateUrlParams,
    navigate: urlResult.navigate,
    setRefPanel: urlResult.setRefPanel,
    rightCommit: computedState.rightCommit,
  })

  // ========== 6. Update refs with actual values ==========
  resetRefsPanelRef.current = refsResult.resetRefsPanel
  setErrorRef.current = dataResult.setError
  fileVersionsRef.current = dataResult.fileVersions
  repositoryRef.current = dataResult.repository
  rightCommitRef.current = computedState.rightCommit

  // ========== Assemble return value ==========

  const dataState: BrowseDataState = {
    allRepositories: dataResult.allRepositories,
    repository: dataResult.repository,
    treeNodes: dataResult.treeNodes,
    fileContent: dataResult.fileContent,
    fileSymbols: dataResult.fileSymbols,
    fileReferences: dataResult.fileReferences,
    fileVersions: dataResult.fileVersions,
    rawContent: dataResult.rawContent,
  }

  const diffState: BrowseDiffState = {
    diffContent: diffResult.diffContent,
    diffSymbols: diffResult.diffSymbols,
    diffReferences: diffResult.diffReferences,
    activePanel: urlResult.urlState.activePanel,
    treePanel: urlResult.urlState.treePanel,
    refPanel: urlResult.urlState.refPanel,
  }

  const uiState: BrowseUIState = {
    drawerOpen: urlResult.urlState.drawerOpen,
    refsPanelOpen: urlResult.urlState.refsPanelOpen,
    loading: dataResult.loading,
    fileLoading: dataResult.fileLoading,
    diffLoading: diffResult.diffLoading,
    error: dataResult.error,
    searchQuery: urlResult.urlState.searchQuery,
  }

  const refsState: BrowseRefsState = {
    selectedSymbol: refsResult.selectedSymbol,
    isDirectDefinition: refsResult.isDirectDefinition,
    searchByName: refsResult.searchByName,
  }

  const actions: BrowseActions = {
    // Navigation
    navigateToRepository: urlResult.navigateToRepository,
    navigateToFile: urlResult.navigateToFile,
    navigateToSymbol: refsResult.navigateToSymbol,
    navigateToLine: urlResult.navigateToLine,
    resetToFileTree: urlResult.resetToFileTree,

    // Diff mode
    enterDiffMode: diffResult.enterDiffMode,
    exitDiffMode: diffResult.exitDiffMode,
    closePanel: diffResult.closePanel,
    setActivePanel: urlResult.setActivePanel,
    setTreePanel: urlResult.setTreePanel,

    // Branch changes
    changeBranch: urlResult.changeBranch,
    changeDiffBranch: urlResult.changeDiffBranch,

    // Version changes
    changeVersion: urlResult.changeVersion,
    changeDiffVersion: urlResult.changeDiffVersion,

    // UI toggles
    toggleDrawer: urlResult.toggleDrawer,
    setDrawerOpen: urlResult.setDrawerOpen,
    toggleChangedOnly: urlResult.toggleChangedOnly,
    setChangedOnly: urlResult.setChangedOnly,
    setViewMode: urlResult.setViewMode,

    // References panel
    openRefsPanel: refsResult.openRefsPanel,
    openRefsPanelByName: refsResult.openRefsPanelByName,
    closeRefsPanel: refsResult.closeRefsPanel,
    setRefPanel: urlResult.setRefPanel,
    handleRefPanelChange: refsResult.handleRefPanelChange,

    // Search
    setSearchQuery: urlResult.setSearchQuery,

    // Click handlers
    handleSymbolClick: refsResult.handleSymbolClick,
    handleDiffSymbolClick: refsResult.handleDiffSymbolClick,
    handleCodeReferenceClick: refsResult.handleCodeReferenceClick,
    handleDiffReferenceClick: refsResult.handleDiffReferenceClick,
    handleRefPanelClick: refsResult.handleRefPanelClick,
    handleDefinitionClick: refsResult.handleDefinitionClick,
    handleDiffLineClick: urlResult.handleDiffLineClick,
  }

  return {
    urlState: urlResult.urlState,
    dataState,
    diffState,
    uiState,
    refsState,
    computedState,
    actions,
  }
}
