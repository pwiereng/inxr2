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
  getCommits,
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
// Helpers
// ============================================================================

/**
 * Encode a file path for use in URLs, preserving directory separators.
 * Each path segment is encoded individually to handle special characters
 * (spaces, #, ?, %, etc.) while keeping slashes as path separators.
 */
function encodeFilePath(path: string): string {
  return path
    .split('/')
    .map((segment) => encodeURIComponent(segment))
    .join('/')
}

// ============================================================================
// Types
// ============================================================================

/**
 * State derived from URL parameters for bookmarkability.
 *
 * URL params: line, commit, diff, q, drawer, refs, tp, rp, ap, branch, diffBranch
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
  // URL-persisted UI state (q, drawer, refs, tp, rp, ap, co)
  searchQuery: string // q param - used for both search and refs panel restoration
  drawerOpen: boolean // drawer param (0 = closed, absent = open)
  refsPanelOpen: boolean // refs param (1 = open, absent = closed)
  treePanel: 'left' | 'right' // tp param (r = right, absent = left)
  refPanel: 'left' | 'right' // rp param (r = right, absent = left)
  activePanel: 'left' | 'right' // ap param (r = right, absent = left)
  changedOnly: boolean // co param (1 = show only files changed in commit, absent = full tree)
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

export function useBrowseState(repoNameProp?: string) {
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

  // ========== Data state ==========
  const [allRepositories, setAllRepositories] = useState<Repository[]>([])
  const [repository, setRepository] = useState<Repository | null>(null)
  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([])
  const [fileContent, setFileContent] = useState<FileContent | null>(null)
  const [fileSymbols, setFileSymbols] = useState<FileSymbol[]>([])
  const [fileReferences, setFileReferences] = useState<FileReference[]>([])
  const [fileVersions, setFileVersions] = useState<FileVersion[]>([])

  // Latest commit hash for the current branch (HEAD fallback for changedOnly)
  const [latestBranchCommit, setLatestBranchCommit] = useState<string | null>(null)

  // ========== Diff state ==========
  const [diffContent, setDiffContent] = useState<FileContent | null>(null)
  const [diffSymbols, setDiffSymbols] = useState<FileSymbol[]>([])
  const [diffReferences, setDiffReferences] = useState<FileReference[]>([])
  const [diffFileVersions, setDiffFileVersions] = useState<FileVersion[]>([])

  // ========== UI state (loading/error only - rest is URL-driven) ==========
  const [loading, setLoading] = useState(true)
  const [fileLoading, setFileLoading] = useState(false)
  const [diffLoading, setDiffLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    const rightCommit = urlState.diffCommit || diffFileVersions[0]?.commit_hash || null
    const treeCommit = urlState.diffMode
      ? urlState.treePanel === 'left'
        ? leftCommit
        : rightCommit
      : urlState.selectedCommit || latestBranchCommit
    const refCommit = urlState.diffMode
      ? urlState.refPanel === 'left'
        ? leftCommit
        : rightCommit
      : urlState.selectedCommit
    const currentCommitHash = urlState.selectedCommit || fileVersions[0]?.commit_hash

    // Check if file was changed at the selected commit.
    // When changedOnly is on, trust the tree — if the file appears in the
    // changed-files tree, git confirmed it changed (even for merge commits
    // where the file's indexed version is from the original branch commit).
    // Otherwise, check if the selected commit appears in file versions.
    const fileChangedInCommit = urlState.changedOnly
      ? true // tree already filtered to changed files
      : urlState.selectedCommit
        ? fileVersions.some((v) => v.commit_hash === urlState.selectedCommit)
        : true

    return {
      leftCommit,
      rightCommit,
      treeCommit,
      refCommit,
      currentCommitHash,
      fileChangedInCommit,
    }
  }, [urlState, fileVersions, diffFileVersions, latestBranchCommit])

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

  // Fetch latest commit for the current branch (used as HEAD fallback)
  useEffect(() => {
    if (!urlState.repoName) return

    const branch = urlState.selectedBranch || repository?.default_branch
    getCommits(urlState.repoName, branch || undefined, 1)
      .then((res) => {
        const latest = res.commits.find((c) => c.is_indexed)
        setLatestBranchCommit(latest?.hash ?? null)
      })
      .catch(() => setLatestBranchCommit(null))
  }, [urlState.repoName, urlState.selectedBranch, repository?.default_branch])

  // Load tree
  useEffect(() => {
    if (!urlState.repoName) return

    // Determine which branch to use for tree (left or right panel in diff mode)
    const treeBranch = urlState.diffMode
      ? urlState.treePanel === 'left'
        ? urlState.selectedBranch
        : urlState.diffBranch
      : urlState.selectedBranch

    const loadTree = async () => {
      try {
        // changedOnly only applies when viewing a specific commit
        const shouldUseChangedOnly = urlState.changedOnly && !!computedState.treeCommit
        const tree = await getRepositoryTreeByName(
          urlState.repoName!,
          computedState.treeCommit || undefined,
          treeBranch || undefined,
          shouldUseChangedOnly
        )
        setTreeNodes(tree.root)
      } catch (err) {
        console.error('Failed to load tree:', err)
      }
    }

    loadTree()
  }, [
    urlState.repoName,
    computedState.treeCommit,
    urlState.selectedBranch,
    urlState.diffBranch,
    urlState.diffMode,
    urlState.treePanel,
    urlState.changedOnly,
  ])

  // Clear selected file if it's not in the changed-files tree
  useEffect(() => {
    if (!urlState.changedOnly || !urlState.filePath || !urlState.repoName) return

    // Recursively check if a file path exists in the tree
    const fileInTree = (nodes: TreeNode[], path: string): boolean =>
      nodes.some(
        (n) =>
          (n.type === 'file' && n.path === path) ||
          (n.children != null && fileInTree(n.children, path))
      )

    if (treeNodes.length > 0 && !fileInTree(treeNodes, urlState.filePath)) {
      // File not in the changed-files tree — clear selection
      const params = new URLSearchParams(searchParams)
      navigate(
        `/browse/${encodeURIComponent(urlState.repoName)}?${params}`,
        { replace: true }
      )
    }
  }, [urlState.changedOnly, urlState.filePath, urlState.repoName, treeNodes, navigate, searchParams])

  // Load file versions
  useEffect(() => {
    if (!urlState.filePath || !urlState.repoName) {
      setFileVersions([])
      return
    }

    getFileHistory(urlState.repoName, urlState.filePath, urlState.selectedBranch || undefined)
      .then((response) => setFileVersions(response.versions))
      .catch(() => setFileVersions([]))
  }, [urlState.repoName, urlState.filePath, urlState.selectedBranch])

  // Load diff file versions (for diff mode - either cross-branch or same-branch version comparison)
  useEffect(() => {
    if (!urlState.filePath || !urlState.repoName || !urlState.diffMode) {
      setDiffFileVersions([])
      return
    }

    // Use the same branch logic as the right panel's VersionSelector
    const diffBranchToUse = urlState.diffBranch || urlState.selectedBranch
    getFileHistory(urlState.repoName, urlState.filePath, diffBranchToUse || undefined)
      .then((response) => setDiffFileVersions(response.versions))
      .catch(() => setDiffFileVersions([]))
  }, [
    urlState.repoName,
    urlState.filePath,
    urlState.diffMode,
    urlState.diffBranch,
    urlState.selectedBranch,
  ])

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
            urlState.selectedCommit || undefined,
            urlState.selectedBranch || undefined
          ),
          getFileSymbolsByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.selectedCommit || undefined,
            urlState.selectedBranch || undefined
          ),
          getFileReferencesByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.selectedCommit || undefined,
            urlState.selectedBranch || undefined
          ),
        ])
        setError(null) // Clear any previous error on successful load
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
  }, [urlState.repoName, urlState.filePath, urlState.selectedCommit, urlState.selectedBranch])

  // Load diff content
  useEffect(() => {
    // Diff mode can work with either diffCommit or diffBranch
    const hasDiffTarget = urlState.diffCommit || urlState.diffBranch
    if (!urlState.diffMode || !hasDiffTarget || !urlState.filePath || !urlState.repoName) {
      setDiffContent(null)
      setDiffSymbols([])
      setDiffReferences([])
      return
    }

    const loadDiffFile = async () => {
      setDiffLoading(true)
      try {
        const [content, symbols, references] = await Promise.all([
          getFileContentByPathAtCommit(
            urlState.repoName!,
            urlState.filePath!,
            urlState.diffCommit || undefined,
            urlState.diffBranch || undefined
          ),
          getFileSymbolsByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.diffCommit || undefined,
            urlState.diffBranch || undefined
          ),
          getFileReferencesByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.diffCommit || undefined,
            urlState.diffBranch || undefined
          ),
        ])
        setDiffContent(content)
        setDiffSymbols(symbols.symbols)
        setDiffReferences(references.references)
      } catch (err) {
        // 404 errors are expected when file doesn't exist on the target branch/commit
        // Only log unexpected errors
        const isNotFoundError =
          err instanceof Error && (err.message.includes('not found') || err.message.includes('404'))
        if (!isNotFoundError) {
          console.error('Failed to load diff file:', err)
        }
        setDiffContent(null)
        setDiffSymbols([])
        setDiffReferences([])
      } finally {
        setDiffLoading(false)
      }
    }

    loadDiffFile()
  }, [
    urlState.repoName,
    urlState.filePath,
    urlState.diffMode,
    urlState.diffCommit,
    urlState.diffBranch,
  ])

  // ========== Restore refs panel search state from URL ==========
  // When loading a bookmarked URL with refs=1 and q=symbolName, initialize
  // the search-by-name state so the refs panel shows the correct results.
  //
  // Design note: We use `q` (search query) for bookmarkability instead of storing
  // symbol IDs in the URL. This is intentional because:
  // - Symbol IDs can change between indexing runs
  // - Name-based search is more robust for bookmarks across time
  // - It simplifies URL structure while still achieving bookmarkability
  //
  // The selectedSymbol and searchByName dependencies ensure we don't override
  // state that was set by user actions (e.g., clicking a symbol).
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
  // Note: This only resets React state. Callers (changeVersion, changeDiffVersion)
  // are responsible for URL updates via their navigate() calls.
  const resetRefsPanel = useCallback(() => {
    setSelectedSymbol(null)
    setSearchByName(null)
    setIsDirectDefinition(false)
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
        // Note: Don't preserve selectedCommit - symbol search returns symbols from
        // the latest indexed commit, so we should view the latest version.
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

    const params = new URLSearchParams()
    if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
    if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
    // Preserve drawer state only - entering diff mode clears search context
    if (!urlState.drawerOpen) params.set('drawer', '0')
    // Don't preserve refs, searchQuery - diff mode is a new context
    // Preserve branch state
    if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)

    if (diffTarget) {
      // Compare against a different version on the same branch
      params.set('diff', diffTarget)
    } else {
      // No other versions available - enter cross-branch comparison mode
      // Set diffBranch to current branch so user can change it
      params.set('diffBranch', urlState.selectedBranch || repository?.default_branch || 'main')
    }

    navigate(
      `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
    )
  }, [navigate, urlState, fileVersions, repository])

  const exitDiffMode = useCallback(() => {
    if (!urlState.filePath) return

    setDiffContent(null)
    setDiffSymbols([])
    setDiffReferences([])
    // Note: tp/rp/ap params are not set, so they default to 'left' when URL is parsed

    const params = new URLSearchParams()
    if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
    if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
    // Preserve drawer state only - exiting diff mode clears search context
    if (!urlState.drawerOpen) params.set('drawer', '0')
    // Don't preserve refs, searchQuery - exiting diff mode is a context change
    // Preserve branch state (but not diffBranch since we're exiting diff mode)
    if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
    navigate(
      `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
    )
  }, [navigate, urlState])

  const closePanel = useCallback(
    (panel: 'left' | 'right') => {
      if (!urlState.filePath) return

      // When closing left panel, switch to the right panel's version/branch
      if (panel === 'left') {
        const params = new URLSearchParams()
        if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
        // Use the effective right commit (could be from diffCommit or diffFileVersions)
        if (computedState.rightCommit) params.set('commit', computedState.rightCommit)
        // Preserve drawer state only - closing panel clears search context
        if (!urlState.drawerOpen) params.set('drawer', '0')
        // Don't preserve refs, searchQuery - closing panel is a context change
        // When closing left panel, the diff side becomes the main view - use diffBranch
        if (urlState.diffBranch) params.set('branch', urlState.diffBranch)
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
        )
        return
      }
      // Closing right panel - keep the left panel's version/branch
      exitDiffMode()
    },
    [navigate, urlState, computedState.rightCommit, exitDiffMode]
  )

  // ========== Version Change Actions ==========

  const changeVersion = useCallback(
    (commitHash: string | null) => {
      if (!urlState.repoName) return
      resetRefsPanel()
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
      navigate(
        `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
      )
    },
    [navigate, urlState, resetRefsPanel]
  )

  // ========== Branch Change Actions ==========

  const changeBranch = useCallback(
    (branchName: string | null) => {
      resetRefsPanel()
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
    [navigate, urlState, resetRefsPanel]
  )

  const changeDiffBranch = useCallback(
    (branchName: string | null) => {
      if (!urlState.filePath) return
      resetRefsPanel()
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
      navigate(
        `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
      )
    },
    [navigate, urlState, resetRefsPanel]
  )

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
        // In cross-branch diff mode, diffCommit may be null - fall back to computedState.rightCommit
        const commitToUse = isRightPanel
          ? urlState.diffCommit || computedState.rightCommit
          : urlState.selectedCommit
        const branchToUse = isRightPanel ? urlState.diffBranch : urlState.selectedBranch
        if (commitToUse) params.set('commit', commitToUse)
        if (branchToUse) params.set('branch', branchToUse)
        // Preserve drawer state only - navigating to reference clears search context
        if (!urlState.drawerOpen) params.set('drawer', '0')
        // Don't preserve refs, searchQuery - navigating to a different file is a context change
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(reference.source_file_path)}?${params}`
        )
      }
    },
    [navigate, urlState, computedState.rightCommit]
  )

  const handleDefinitionClick = useCallback(
    (sym: Symbol) => {
      if (sym.file_path) {
        const params = new URLSearchParams()
        params.set('line', sym.start_line.toString())
        // Use refPanel (which side the ReferencesPanel is showing) not activePanel
        // (which code panel was last clicked) to determine commit and branch
        const isRightPanel = urlState.diffMode && urlState.refPanel === 'right'
        // In cross-branch diff mode, diffCommit may be null - fall back to computedState.rightCommit
        const commitToUse = isRightPanel
          ? urlState.diffCommit || computedState.rightCommit
          : urlState.selectedCommit
        const branchToUse = isRightPanel ? urlState.diffBranch : urlState.selectedBranch
        if (commitToUse) params.set('commit', commitToUse)
        if (branchToUse) params.set('branch', branchToUse)
        // Preserve drawer state only - navigating to definition clears search context
        if (!urlState.drawerOpen) params.set('drawer', '0')
        // Don't preserve refs, searchQuery - navigating to a definition is a context change
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(sym.file_path)}?${params}`
        )
      }
    },
    [navigate, urlState, computedState.rightCommit]
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
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`,
          { replace: true }
        )
      }
    },
    [navigate, urlState]
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
    activePanel: urlState.activePanel,
    treePanel: urlState.treePanel,
    refPanel: urlState.refPanel,
  }

  const uiState: BrowseUIState = {
    drawerOpen: urlState.drawerOpen,
    refsPanelOpen: urlState.refsPanelOpen,
    loading,
    fileLoading,
    diffLoading,
    error,
    searchQuery: urlState.searchQuery,
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
    setTreePanel,

    // Branch changes
    changeBranch,
    changeDiffBranch,

    // Version changes
    changeVersion,
    changeDiffVersion,

    // UI toggles
    toggleDrawer,
    setDrawerOpen,
    toggleChangedOnly,
    setChangedOnly,

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
