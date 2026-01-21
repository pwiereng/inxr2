/**
 * Custom hook for managing Browse page state.
 *
 * This hook centralizes the state management for the Browse component,
 * providing a cleaner API and reducing the complexity of the main component.
 *
 * State is organized into logical groups:
 * - URL-derived state (from react-router params)
 * - Data state (repositories, files, symbols, references)
 * - Diff state (for side-by-side comparison)
 * - UI state (panels, loading states)
 * - References panel state
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  getRepositories,
  getRepositoryByName,
  getRepositoryTreeByName,
  getFileContentByPathAtCommit,
  getFileSymbolsByPath,
  getFileReferencesByPath,
  getSymbol,
  getFileHistory,
  type Repository,
  type TreeNode,
  type FileContent,
  type FileSymbol,
  type FileReference,
  type Symbol,
  type FileVersion,
} from '@/lib/api'

// ============================================================================
// Types
// ============================================================================

export interface BrowseUrlState {
  repoName: string | undefined
  filePath: string | null
  highlightLine: number | undefined
  selectedCommit: string | null
  diffCommit: string | null
  diffMode: boolean
}

export interface BrowseDataState {
  allRepositories: Repository[]
  repository: Repository | null
  treeNodes: TreeNode[]
  fileContent: FileContent | null
  fileSymbols: FileSymbol[]
  fileReferences: FileReference[]
  fileVersions: FileVersion[]
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

  // Diff mode
  enterDiffMode: () => void
  exitDiffMode: () => void
  closePanel: (panel: 'left' | 'right') => void
  setActivePanel: (panel: 'left' | 'right') => void

  // Version changes
  changeVersion: (commitHash: string | null) => void
  changeDiffVersion: (commitHash: string | null) => void

  // UI toggles
  toggleDrawer: () => void
  setDrawerOpen: (open: boolean) => void

  // References panel
  openRefsPanel: (symbol: Symbol, isDirect: boolean) => void
  openRefsPanelByName: (name: string, repositoryId: number) => void
  closeRefsPanel: () => void
  setRefPanel: (panel: 'left' | 'right') => void
  handleRefPanelChange: (panel: 'left' | 'right') => void

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
}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useBrowseState() {
  const { repoName, '*': splatPath } = useParams<{ repoName: string; '*': string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // ========== URL-derived state ==========
  const urlState = useMemo<BrowseUrlState>(() => {
    const filePath = splatPath || null
    const highlightLine = searchParams.get('line')
      ? parseInt(searchParams.get('line')!, 10)
      : undefined
    const selectedCommit = searchParams.get('commit')
    const diffCommit = searchParams.get('diff')
    return {
      repoName,
      filePath,
      highlightLine,
      selectedCommit,
      diffCommit,
      diffMode: !!diffCommit,
    }
  }, [repoName, splatPath, searchParams])

  // ========== Data state ==========
  const [allRepositories, setAllRepositories] = useState<Repository[]>([])
  const [repository, setRepository] = useState<Repository | null>(null)
  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([])
  const [fileContent, setFileContent] = useState<FileContent | null>(null)
  const [fileSymbols, setFileSymbols] = useState<FileSymbol[]>([])
  const [fileReferences, setFileReferences] = useState<FileReference[]>([])
  const [fileVersions, setFileVersions] = useState<FileVersion[]>([])

  // ========== Diff state ==========
  const [diffContent, setDiffContent] = useState<FileContent | null>(null)
  const [diffSymbols, setDiffSymbols] = useState<FileSymbol[]>([])
  const [diffReferences, setDiffReferences] = useState<FileReference[]>([])
  const [activePanel, setActivePanel] = useState<'left' | 'right'>('left')
  const [treePanel, setTreePanel] = useState<'left' | 'right'>('left')
  const [refPanel, setRefPanel] = useState<'left' | 'right'>('left')

  // ========== UI state ==========
  const [drawerOpen, setDrawerOpen] = useState(true)
  const [refsPanelOpen, setRefsPanelOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [fileLoading, setFileLoading] = useState(false)
  const [diffLoading, setDiffLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // ========== References state ==========
  const [selectedSymbol, setSelectedSymbol] = useState<Symbol | null>(null)
  const [isDirectDefinition, setIsDirectDefinition] = useState(false)
  const [searchByName, setSearchByName] = useState<{
    name: string
    repositoryId: number
  } | null>(null)

  // ========== Computed state ==========
  const computedState = useMemo<BrowseComputedState>(() => {
    const leftCommit = urlState.selectedCommit || fileVersions[0]?.commit_hash
    const rightCommit = urlState.diffCommit
    const treeCommit = urlState.diffMode
      ? treePanel === 'left'
        ? leftCommit
        : rightCommit
      : urlState.selectedCommit
    const refCommit = urlState.diffMode
      ? refPanel === 'left'
        ? leftCommit
        : rightCommit
      : urlState.selectedCommit
    const currentCommitHash = urlState.selectedCommit || fileVersions[0]?.commit_hash

    return { leftCommit, rightCommit, treeCommit, refCommit, currentCommitHash }
  }, [urlState, fileVersions, treePanel, refPanel])

  // ========== Data Loading Effects ==========

  // Load all repositories
  useEffect(() => {
    getRepositories().then(setAllRepositories).catch(console.error)
  }, [])

  // Load repository by name
  useEffect(() => {
    if (!urlState.repoName) return

    const loadRepository = async () => {
      setLoading(true)
      setError(null)
      try {
        const repo = await getRepositoryByName(urlState.repoName!)
        setRepository(repo)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load repository')
      } finally {
        setLoading(false)
      }
    }

    loadRepository()
  }, [urlState.repoName])

  // Load tree
  useEffect(() => {
    if (!urlState.repoName) return

    const loadTree = async () => {
      try {
        const tree = await getRepositoryTreeByName(
          urlState.repoName!,
          computedState.treeCommit || undefined
        )
        setTreeNodes(tree.root)
      } catch (err) {
        console.error('Failed to load tree:', err)
      }
    }

    loadTree()
  }, [urlState.repoName, computedState.treeCommit])

  // Load file versions
  useEffect(() => {
    if (!urlState.filePath || !urlState.repoName) {
      setFileVersions([])
      return
    }

    getFileHistory(urlState.repoName, urlState.filePath)
      .then((response) => setFileVersions(response.versions))
      .catch(() => setFileVersions([]))
  }, [urlState.repoName, urlState.filePath])

  // Load file content
  useEffect(() => {
    if (!urlState.filePath || !urlState.repoName) {
      setFileContent(null)
      setFileSymbols([])
      setFileReferences([])
      return
    }

    const loadFile = async () => {
      setFileLoading(true)
      try {
        const [content, symbols, references] = await Promise.all([
          getFileContentByPathAtCommit(
            urlState.repoName!,
            urlState.filePath!,
            urlState.selectedCommit || undefined
          ),
          getFileSymbolsByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.selectedCommit || undefined
          ),
          getFileReferencesByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.selectedCommit || undefined
          ),
        ])
        setFileContent(content)
        setFileSymbols(symbols.symbols)
        setFileReferences(references.references)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load file')
      } finally {
        setFileLoading(false)
      }
    }

    loadFile()
  }, [urlState.repoName, urlState.filePath, urlState.selectedCommit])

  // Load diff content
  useEffect(() => {
    if (!urlState.diffMode || !urlState.diffCommit || !urlState.filePath || !urlState.repoName) {
      setDiffContent(null)
      setDiffSymbols([])
      setDiffReferences([])
      return
    }

    const loadDiffFile = async () => {
      setDiffLoading(true)
      try {
        const [content, symbols, references] = await Promise.all([
          getFileContentByPathAtCommit(urlState.repoName!, urlState.filePath!, urlState.diffCommit!),
          getFileSymbolsByPath(urlState.repoName!, urlState.filePath!, urlState.diffCommit!),
          getFileReferencesByPath(urlState.repoName!, urlState.filePath!, urlState.diffCommit!),
        ])
        setDiffContent(content)
        setDiffSymbols(symbols.symbols)
        setDiffReferences(references.references)
      } catch (err) {
        console.error('Failed to load diff file:', err)
        setDiffContent(null)
        setDiffSymbols([])
        setDiffReferences([])
      } finally {
        setDiffLoading(false)
      }
    }

    loadDiffFile()
  }, [urlState.repoName, urlState.filePath, urlState.diffMode, urlState.diffCommit])

  // ========== Helper: Reset refs panel state ==========
  const resetRefsPanel = useCallback(() => {
    setRefsPanelOpen(false)
    setSelectedSymbol(null)
    setSearchByName(null)
  }, [])

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
      const query = params.toString()
      navigate(
        `/browse/${encodeURIComponent(urlState.repoName!)}/${path}${query ? `?${query}` : ''}`
      )
    },
    [navigate, urlState.repoName, urlState.selectedCommit]
  )

  const navigateToSymbol = useCallback(
    async (symbol: Symbol) => {
      if (symbol.file_path) {
        const params = new URLSearchParams()
        params.set('line', symbol.start_line.toString())
        if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
        navigate(`/browse/${encodeURIComponent(urlState.repoName!)}/${symbol.file_path}?${params}`)
      }
    },
    [navigate, urlState.repoName, urlState.selectedCommit]
  )

  const navigateToLine = useCallback(
    (line: number) => {
      if (urlState.filePath) {
        const params = new URLSearchParams()
        params.set('line', line.toString())
        if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
        if (urlState.diffCommit) params.set('diff', urlState.diffCommit)
        navigate(`/browse/${encodeURIComponent(urlState.repoName!)}/${urlState.filePath}?${params}`, {
          replace: true,
        })
      }
    },
    [navigate, urlState]
  )

  // ========== Diff Mode Actions ==========

  const enterDiffMode = useCallback(() => {
    if (!urlState.filePath) return

    const currentIndex = fileVersions.findIndex(
      (v) => v.commit_hash === (urlState.selectedCommit || fileVersions[0]?.commit_hash)
    )
    let diffTarget: string | null = null
    if (currentIndex >= 0 && currentIndex < fileVersions.length - 1) {
      diffTarget = fileVersions[currentIndex + 1]?.commit_hash || null
    } else if (fileVersions.length > 1) {
      diffTarget = fileVersions[1]?.commit_hash || null
    }

    if (diffTarget) {
      const params = new URLSearchParams()
      if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
      if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
      params.set('diff', diffTarget)
      navigate(`/browse/${encodeURIComponent(urlState.repoName!)}/${urlState.filePath}?${params}`)
    }
  }, [navigate, urlState, fileVersions])

  const exitDiffMode = useCallback(() => {
    if (!urlState.filePath) return

    setDiffContent(null)
    setDiffSymbols([])
    setDiffReferences([])
    setTreePanel('left')
    setRefPanel('left')

    const params = new URLSearchParams()
    if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
    if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
    navigate(`/browse/${encodeURIComponent(urlState.repoName!)}/${urlState.filePath}?${params}`)
  }, [navigate, urlState])

  const closePanel = useCallback(
    (panel: 'left' | 'right') => {
      if (!urlState.filePath) return

      if (panel === 'left' && urlState.diffCommit) {
        const params = new URLSearchParams()
        if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
        params.set('commit', urlState.diffCommit)
        navigate(`/browse/${encodeURIComponent(urlState.repoName!)}/${urlState.filePath}?${params}`)
        return
      }
      exitDiffMode()
    },
    [navigate, urlState, exitDiffMode]
  )

  // ========== Version Change Actions ==========

  const changeVersion = useCallback(
    (commitHash: string | null) => {
      if (urlState.filePath) {
        resetRefsPanel()
        const params = new URLSearchParams()
        if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
        if (commitHash) params.set('commit', commitHash)
        if (urlState.diffCommit) params.set('diff', urlState.diffCommit)
        navigate(`/browse/${encodeURIComponent(urlState.repoName!)}/${urlState.filePath}?${params}`)
      }
    },
    [navigate, urlState, resetRefsPanel]
  )

  const changeDiffVersion = useCallback(
    (commitHash: string | null) => {
      if (!urlState.filePath) return
      resetRefsPanel()
      const params = new URLSearchParams()
      if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
      if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
      if (commitHash) params.set('diff', commitHash)
      navigate(`/browse/${encodeURIComponent(urlState.repoName!)}/${urlState.filePath}?${params}`)
    },
    [navigate, urlState, resetRefsPanel]
  )

  // ========== References Panel Actions ==========

  const openRefsPanel = useCallback((symbol: Symbol, isDirect: boolean) => {
    setSelectedSymbol(symbol)
    setSearchByName(null)
    setIsDirectDefinition(isDirect)
    setRefsPanelOpen(true)
    setSearchQuery(symbol.name)
  }, [])

  const openRefsPanelByName = useCallback((name: string, repositoryId: number) => {
    setSelectedSymbol(null)
    setSearchByName({ name, repositoryId })
    setIsDirectDefinition(false)
    setRefsPanelOpen(true)
    setSearchQuery(name)
  }, [])

  const closeRefsPanel = useCallback(() => {
    setRefsPanelOpen(false)
    setSelectedSymbol(null)
    setSearchByName(null)
    setIsDirectDefinition(false)
    setSearchQuery('')
  }, [])

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
    [selectedSymbol, searchByName, repository]
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
      setActivePanel(panel)
      setRefPanel(panel)
      await handleSymbolClick(fileSymbol)
    },
    [handleSymbolClick]
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
      setActivePanel(panel)
      setRefPanel(panel)
      await handleCodeReferenceClick(ref)
    },
    [handleCodeReferenceClick]
  )

  const handleRefPanelClick = useCallback(
    (reference: { source_file_path: string | null; source_line: number }) => {
      if (reference.source_file_path) {
        const params = new URLSearchParams()
        params.set('line', reference.source_line.toString())
        const commitToUse =
          urlState.diffMode && activePanel === 'right'
            ? urlState.diffCommit
            : urlState.selectedCommit
        if (commitToUse) params.set('commit', commitToUse)
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${reference.source_file_path}?${params}`
        )
      }
    },
    [navigate, urlState, activePanel]
  )

  const handleDefinitionClick = useCallback(
    (sym: Symbol) => {
      if (sym.file_path) {
        const params = new URLSearchParams()
        params.set('line', sym.start_line.toString())
        const commitToUse =
          urlState.diffMode && activePanel === 'right'
            ? urlState.diffCommit
            : urlState.selectedCommit
        if (commitToUse) params.set('commit', commitToUse)
        navigate(`/browse/${encodeURIComponent(urlState.repoName!)}/${sym.file_path}?${params}`)
      }
    },
    [navigate, urlState, activePanel]
  )

  const handleDiffLineClick = useCallback(
    (line: number, panel: 'left' | 'right') => {
      setActivePanel(panel)
      navigateToLine(line)
    },
    [navigateToLine]
  )

  // ========== Return state and actions ==========

  const dataState: BrowseDataState = {
    allRepositories,
    repository,
    treeNodes,
    fileContent,
    fileSymbols,
    fileReferences,
    fileVersions,
  }

  const diffState: BrowseDiffState = {
    diffContent,
    diffSymbols,
    diffReferences,
    activePanel,
    treePanel,
    refPanel,
  }

  const uiState: BrowseUIState = {
    drawerOpen,
    refsPanelOpen,
    loading,
    fileLoading,
    diffLoading,
    error,
    searchQuery,
  }

  const refsState: BrowseRefsState = {
    selectedSymbol,
    isDirectDefinition,
    searchByName,
  }

  const actions: BrowseActions = {
    // Navigation
    navigateToRepository,
    navigateToFile,
    navigateToSymbol,
    navigateToLine,

    // Diff mode
    enterDiffMode,
    exitDiffMode,
    closePanel,
    setActivePanel,

    // Version changes
    changeVersion,
    changeDiffVersion,

    // UI toggles
    toggleDrawer: () => setDrawerOpen((prev) => !prev),
    setDrawerOpen,

    // References panel
    openRefsPanel,
    openRefsPanelByName,
    closeRefsPanel,
    setRefPanel,
    handleRefPanelChange,

    // Search
    setSearchQuery,

    // Click handlers
    handleSymbolClick,
    handleDiffSymbolClick,
    handleCodeReferenceClick,
    handleDiffReferenceClick,
    handleRefPanelClick,
    handleDefinitionClick,
    handleDiffLineClick,
  }

  return {
    urlState,
    dataState,
    diffState,
    uiState,
    refsState,
    computedState,
    actions,
  }
}
