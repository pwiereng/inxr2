/**
 * Shared type definitions for the Browse page hooks.
 *
 * Extracted into a dedicated module to avoid circular dependencies
 * between the orchestrator (useBrowseState) and its sub-hooks.
 */

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

/**
 * Compute the treeCommit value from browse state inputs.
 *
 * Shared between the orchestrator (for computedState) and useBrowseData
 * (for tree loading effect) to avoid duplicating the logic.
 */
export function computeTreeCommit(
  urlState: BrowseUrlState,
  fileVersions: FileVersion[],
  diffFileVersions: FileVersion[],
  latestBranchCommit: string | null | undefined
): string | null | undefined {
  const leftCommit = urlState.selectedCommit || latestBranchCommit || fileVersions[0]?.commit_hash
  const rightCommit = urlState.diffCommit || diffFileVersions[0]?.commit_hash || null
  return urlState.diffMode
    ? urlState.treePanel === 'left'
      ? leftCommit
      : rightCommit
    : urlState.selectedCommit || latestBranchCommit
}
