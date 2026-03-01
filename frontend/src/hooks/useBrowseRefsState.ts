import { useState, useEffect, useCallback } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import {
  getSymbol,
  type FileSymbol,
  type FileReference,
  type Symbol,
  type Repository,
} from '@/lib/api'
import type { BrowseUrlState } from './useBrowseTypes'
import { encodeFilePath } from './useBrowseUrlState'

export interface UseBrowseRefsStateParams {
  urlState: BrowseUrlState
  repository: Repository | null
  updateUrlParams: (updates: Record<string, string | null>, options?: { replace?: boolean }) => void
  navigate: NavigateFunction
  setRefPanel: (panel: 'left' | 'right') => void
  rightCommit: string | null
}

export interface UseBrowseRefsStateResult {
  selectedSymbol: Symbol | null
  isDirectDefinition: boolean
  searchByName: { name: string; repositoryId: number } | null
  resetRefsPanel: () => void
  openRefsPanel: (symbol: Symbol, isDirect: boolean) => void
  openRefsPanelByName: (name: string, repositoryId: number) => void
  closeRefsPanel: () => void
  handleRefPanelChange: (panel: 'left' | 'right') => void
  handleSymbolClick: (fileSymbol: FileSymbol) => Promise<void>
  handleDiffSymbolClick: (fileSymbol: FileSymbol, panel: 'left' | 'right') => Promise<void>
  handleCodeReferenceClick: (ref: FileReference) => Promise<void>
  handleDiffReferenceClick: (ref: FileReference, panel: 'left' | 'right') => Promise<void>
  handleRefPanelClick: (reference: { source_file_path: string | null; source_line: number }) => void
  handleDefinitionClick: (sym: Symbol) => void
  navigateToSymbol: (symbol: Symbol) => void
}

export function useBrowseRefsState({
  urlState,
  repository,
  updateUrlParams,
  navigate,
  setRefPanel,
  rightCommit,
}: UseBrowseRefsStateParams): UseBrowseRefsStateResult {
  // ========== References state ==========
  const [selectedSymbol, setSelectedSymbol] = useState<Symbol | null>(null)
  const [isDirectDefinition, setIsDirectDefinition] = useState(false)
  const [searchByName, setSearchByName] = useState<{
    name: string
    repositoryId: number
  } | null>(null)

  // ========== Restore refs panel search state from URL ==========
  useEffect(() => {
    if (!urlState.refsPanelOpen || !urlState.searchQuery || !repository?.id) {
      return
    }
    // Only restore if we don't already have a symbol or search set (prevents
    // overriding user actions like symbol clicks)
    if (selectedSymbol || searchByName) {
      return
    }
    setSearchByName({ name: urlState.searchQuery, repositoryId: repository.id })
  }, [urlState.refsPanelOpen, urlState.searchQuery, repository?.id, selectedSymbol, searchByName])

  // ========== Helper: Reset refs panel state ==========
  const resetRefsPanel = useCallback(() => {
    setSelectedSymbol(null)
    setSearchByName(null)
    setIsDirectDefinition(false)
  }, [])

  // ========== References Panel Actions ==========

  const openRefsPanel = useCallback(
    (symbol: Symbol, isDirect: boolean) => {
      setSelectedSymbol(symbol)
      setSearchByName(null)
      setIsDirectDefinition(isDirect)
      // Update both refs and search query in a single URL update to avoid race conditions
      updateUrlParams({ refs: '1', q: symbol.name })
    },
    [updateUrlParams]
  )

  const openRefsPanelByName = useCallback(
    (name: string, repositoryId: number) => {
      setSelectedSymbol(null)
      setSearchByName({ name, repositoryId })
      setIsDirectDefinition(false)
      // Update both refs and search query in a single URL update to avoid race conditions
      updateUrlParams({ refs: '1', q: name })
    },
    [updateUrlParams]
  )

  const closeRefsPanel = useCallback(() => {
    setSelectedSymbol(null)
    setSearchByName(null)
    setIsDirectDefinition(false)
    // Close refs panel but preserve search query (search is independent of refs panel)
    updateUrlParams({ refs: null })
  }, [updateUrlParams])

  const handleRefPanelChange = useCallback(
    (panel: 'left' | 'right') => {
      const symbolName = selectedSymbol?.name || searchByName?.name
      if (symbolName && repository?.id) {
        setSelectedSymbol(null)
        setSearchByName({ name: symbolName, repositoryId: repository.id })
        setIsDirectDefinition(false)
      }
      setRefPanel(panel)
    },
    [selectedSymbol, searchByName, repository, setRefPanel]
  )

  // ========== Click Handlers ==========

  const handleSymbolClick = useCallback(
    async (fileSymbol: FileSymbol) => {
      try {
        const symbol = await getSymbol(fileSymbol.id)
        openRefsPanel(symbol, true)
      } catch (err) {
        console.error('Failed to get symbol:', err)
      }
    },
    [openRefsPanel]
  )

  const handleDiffSymbolClick = useCallback(
    async (fileSymbol: FileSymbol, panel: 'left' | 'right') => {
      try {
        const symbol = await getSymbol(fileSymbol.id)
        setSelectedSymbol(symbol)
        setSearchByName(null)
        setIsDirectDefinition(true)
        // Update all URL params in a single call to avoid race conditions
        updateUrlParams({
          refs: '1',
          q: symbol.name,
          ap: panel === 'right' ? 'r' : null,
          rp: panel === 'right' ? 'r' : null,
        })
      } catch (err) {
        console.error('Failed to get symbol:', err)
      }
    },
    [updateUrlParams]
  )

  const handleCodeReferenceClick = useCallback(
    async (ref: FileReference) => {
      if (!ref.target_symbol_id) {
        if (repository?.id) {
          openRefsPanelByName(ref.reference_text, repository.id)
        }
        return
      }
      try {
        const symbol = await getSymbol(ref.target_symbol_id)
        openRefsPanel(symbol, false)
      } catch (err) {
        console.error('Failed to get symbol for reference:', err)
      }
    },
    [repository, openRefsPanel, openRefsPanelByName]
  )

  const handleDiffReferenceClick = useCallback(
    async (ref: FileReference, panel: 'left' | 'right') => {
      if (!ref.target_symbol_id) {
        // Unresolved reference - search by name
        if (repository?.id) {
          setSelectedSymbol(null)
          setSearchByName({ name: ref.reference_text, repositoryId: repository.id })
          setIsDirectDefinition(false)
          updateUrlParams({
            refs: '1',
            q: ref.reference_text,
            ap: panel === 'right' ? 'r' : null,
            rp: panel === 'right' ? 'r' : null,
          })
        }
        return
      }
      try {
        const symbol = await getSymbol(ref.target_symbol_id)
        setSelectedSymbol(symbol)
        setSearchByName(null)
        setIsDirectDefinition(false)
        updateUrlParams({
          refs: '1',
          q: symbol.name,
          ap: panel === 'right' ? 'r' : null,
          rp: panel === 'right' ? 'r' : null,
        })
      } catch (err) {
        console.error('Failed to get symbol for reference:', err)
      }
    },
    [repository, updateUrlParams]
  )

  const handleRefPanelClick = useCallback(
    (reference: { source_file_path: string | null; source_line: number }) => {
      if (reference.source_file_path) {
        const params = new URLSearchParams()
        params.set('line', reference.source_line.toString())
        // Use refPanel (which side the ReferencesPanel is showing) not activePanel
        // (which code panel was last clicked) to determine commit and branch
        const isRightPanel = urlState.diffMode && urlState.refPanel === 'right'
        // In cross-branch diff mode, diffCommit may be null - fall back to rightCommit
        const commitToUse = isRightPanel
          ? urlState.diffCommit || rightCommit
          : urlState.selectedCommit
        // Fall back to selectedBranch for same-branch diff mode where diffBranch is unset
        const branchToUse = isRightPanel
          ? (urlState.diffBranch ?? urlState.selectedBranch)
          : urlState.selectedBranch
        if (commitToUse) params.set('commit', commitToUse)
        if (branchToUse) params.set('branch', branchToUse)
        // Preserve drawer state only - navigating to reference clears search context
        if (!urlState.drawerOpen) params.set('drawer', '0')
        // Don't preserve refs, searchQuery - navigating to a different file is a context change
        // Preserve changedOnly state
        if (urlState.changedOnly) params.set('co', '1')
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(reference.source_file_path)}?${params}`
        )
      }
    },
    [navigate, urlState, rightCommit]
  )

  const handleDefinitionClick = useCallback(
    (sym: Symbol) => {
      if (sym.file_path) {
        const params = new URLSearchParams()
        params.set('line', sym.start_line.toString())
        // Use refPanel (which side the ReferencesPanel is showing) not activePanel
        // (which code panel was last clicked) to determine commit and branch
        const isRightPanel = urlState.diffMode && urlState.refPanel === 'right'
        // In cross-branch diff mode, diffCommit may be null - fall back to rightCommit
        const commitToUse = isRightPanel
          ? urlState.diffCommit || rightCommit
          : urlState.selectedCommit
        // Fall back to selectedBranch for same-branch diff mode where diffBranch is unset
        const branchToUse = isRightPanel
          ? (urlState.diffBranch ?? urlState.selectedBranch)
          : urlState.selectedBranch
        if (commitToUse) params.set('commit', commitToUse)
        if (branchToUse) params.set('branch', branchToUse)
        // Preserve drawer state only - navigating to definition clears search context
        if (!urlState.drawerOpen) params.set('drawer', '0')
        // Don't preserve refs, searchQuery - navigating to a definition is a context change
        // Preserve changedOnly state
        if (urlState.changedOnly) params.set('co', '1')
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(sym.file_path)}?${params}`
        )
      }
    },
    [navigate, urlState, rightCommit]
  )

  const navigateToSymbol = useCallback(
    (symbol: Symbol) => {
      if (!urlState.repoName) {
        return
      }

      // Set up refs panel state for the selected symbol
      setSelectedSymbol(symbol)
      setSearchByName(null)
      setIsDirectDefinition(true)

      if (symbol.file_path) {
        // Navigate to the symbol's location AND open refs panel
        const params = new URLSearchParams()
        params.set('line', symbol.start_line.toString())
        // Preserve branch and commit - symbol search is scoped to both
        if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
        if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
        // Exit diff mode when navigating to a symbol (don't preserve diff, tp, rp, ap params)
        // Preserve drawer state
        if (!urlState.drawerOpen) params.set('drawer', '0')
        // Open refs panel with the symbol name
        params.set('refs', '1')
        params.set('q', symbol.name)
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName)}/${encodeFilePath(symbol.file_path)}?${params}`
        )
      } else {
        // Symbol has no file_path - just open refs panel to show references
        updateUrlParams({ refs: '1', q: symbol.name })
      }
    },
    [navigate, urlState, updateUrlParams]
  )

  return {
    selectedSymbol,
    isDirectDefinition,
    searchByName,
    resetRefsPanel,
    openRefsPanel,
    openRefsPanelByName,
    closeRefsPanel,
    handleRefPanelChange,
    handleSymbolClick,
    handleDiffSymbolClick,
    handleCodeReferenceClick,
    handleDiffReferenceClick,
    handleRefPanelClick,
    handleDefinitionClick,
    navigateToSymbol,
  }
}
