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

import { useRef, useMemo, useEffect } from 'react'
import type { FileVersion } from '@/lib/api'
import { useBrowseUrlState } from './useBrowseUrlState'
import { useBrowseDiffState } from './useBrowseDiffState'
import { useBrowseData } from './useBrowseData'
import { useBrowseRefsState } from './useBrowseRefsState'
import { computeTreeCommit } from './useBrowseTypes'
import type {
  BrowseActions,
  BrowseComputedState,
  BrowseDataState,
  BrowseDiffState,
  BrowseRefsState,
  BrowseUIState,
  BrowseUrlState,
} from './useBrowseTypes'

// Re-export all types so existing consumers can still import from useBrowseState
export type {
  BrowseUrlState,
  BrowseDataState,
  BrowseDiffState,
  BrowseUIState,
  BrowseRefsState,
  BrowseActions,
  BrowseComputedState,
} from './useBrowseTypes'

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

  // ========== 1. URL State ==========
  const urlResult = useBrowseUrlState(repoNameProp, { resetRefsPanelRef, setErrorRef })

  // ========== 2. Diff State ==========
  const diffResult = useBrowseDiffState({
    urlState: urlResult.urlState,
    navigate: urlResult.navigate,
    refs: { fileVersionsRef },
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
    // comparisonCommit = LEFT visual panel (from `diff` URL param)
    const comparisonCommit =
      urlResult.urlState.diffCommit || diffResult.diffFileVersions[0]?.commit_hash || null
    // globalReferenceCommit = RIGHT visual panel (from `commit` URL param / top picker)
    const globalReferenceCommit =
      urlResult.urlState.selectedCommit ||
      dataResult.latestBranchCommit ||
      dataResult.fileVersions[0]?.commit_hash
    const treeCommit = computeTreeCommit(
      urlResult.urlState,
      dataResult.fileVersions,
      diffResult.diffFileVersions,
      dataResult.latestBranchCommit
    )
    // Visual layout: left panel = comparison, right panel = global reference
    const refCommit = urlResult.urlState.diffMode
      ? urlResult.urlState.refPanel === 'left'
        ? comparisonCommit
        : globalReferenceCommit
      : urlResult.urlState.selectedCommit
    const currentCommitHash =
      urlResult.urlState.selectedCommit || dataResult.fileVersions[0]?.commit_hash

    const fileChangedInCommit = urlResult.urlState.changedOnly
      ? true
      : urlResult.urlState.selectedCommit
        ? dataResult.fileVersions.some((v) => v.commit_hash === urlResult.urlState.selectedCommit)
        : true

    // Determine temporal ordering of comparison vs reference commits by comparing dates.
    // Look up each commit hash in file versions first, then fall back to
    // commitDateMap (from getCommits) for commits that didn't modify the file.
    let referenceIsNewer = false
    let temporalOrderKnown = false
    if (globalReferenceCommit && comparisonCommit) {
      const referenceDate =
        dataResult.fileVersions.find((v) => v.commit_hash === globalReferenceCommit)?.commit_date ??
        dataResult.commitDateMap.get(globalReferenceCommit)
      const comparisonDate =
        diffResult.diffFileVersions.find((v) => v.commit_hash === comparisonCommit)?.commit_date ??
        dataResult.fileVersions.find((v) => v.commit_hash === comparisonCommit)?.commit_date ??
        dataResult.commitDateMap.get(comparisonCommit)
      if (referenceDate && comparisonDate) {
        const refDate = new Date(referenceDate)
        const compDate = new Date(comparisonDate)
        if (refDate > compDate) {
          referenceIsNewer = true
          temporalOrderKnown = true
        } else if (refDate < compDate) {
          temporalOrderKnown = true
        }
      }
    }

    return {
      comparisonCommit,
      globalReferenceCommit,
      treeCommit,
      refCommit,
      currentCommitHash,
      fileChangedInCommit,
      referenceIsNewer,
      temporalOrderKnown,
    }
  }, [
    urlResult.urlState,
    dataResult.fileVersions,
    diffResult.diffFileVersions,
    dataResult.latestBranchCommit,
    dataResult.commitDateMap,
  ])

  // ========== 4b. Sync resolved HEAD commit to URL for proper permalinks ==========
  const { selectedCommit } = urlResult.urlState
  const { updateUrlParams } = urlResult
  const { latestBranchCommit } = dataResult
  useEffect(() => {
    // When the URL has no commit param and we've resolved the branch HEAD,
    // write it to the URL so the page is a proper permalink.
    if (!selectedCommit && typeof latestBranchCommit === 'string') {
      updateUrlParams({ commit: latestBranchCommit }, { replace: true })
    }
  }, [selectedCommit, latestBranchCommit, updateUrlParams])

  // ========== 5. Refs State ==========
  const refsResult = useBrowseRefsState({
    urlState: urlResult.urlState,
    repository: dataResult.repository,
    updateUrlParams: urlResult.updateUrlParams,
    navigate: urlResult.navigate,
    setRefPanel: urlResult.setRefPanel,
    comparisonCommit: computedState.comparisonCommit,
  })

  // ========== 6. Update refs with actual values ==========
  resetRefsPanelRef.current = refsResult.resetRefsPanel
  setErrorRef.current = dataResult.setError
  fileVersionsRef.current = dataResult.fileVersions

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
    treeLoading: dataResult.treeLoading,
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
    navigateToDirectory: urlResult.navigateToDirectory,
    navigateToSymbol: refsResult.navigateToSymbol,
    navigateToLine: urlResult.navigateToLine,
    resetToFileTree: urlResult.resetToFileTree,

    // Diff mode
    enterDiffMode: diffResult.enterDiffMode,
    exitDiffMode: diffResult.exitDiffMode,
    closePanel: diffResult.closePanel,
    swapDiffPanels: diffResult.swapDiffPanels,
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
