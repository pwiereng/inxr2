import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
  ButtonBase,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Button,
  Paper,
  List,
  ListItem,
  Pagination,
  CircularProgress,
  Alert,
  Checkbox,
  FormControlLabel,
  FormGroup,
  ToggleButton,
  Tooltip,
  Divider,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'

import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'

import { CodeHeader, type TabValue } from '@/components/CodeHeader'
import { isMarkdownFile } from '@/lib/fileUtils'
import { highlightMatches, sanitizeHeadline } from '@/lib/highlightMatches'
import {
  searchText,
  searchFiles,
  searchSymbols,
  searchDependencies,
  getRepositories,
  getFileExtensions,
  type TextSearchResult,
  type FileSearchResult,
  type DependencySearchResult,
  type Repository,
  type Symbol,
} from '@/lib/api'
import { MENU_PROPS } from '@/lib/menuProps'
import { useSelectionToolbar } from '@/hooks/useSelectionToolbar'
import { SelectionToolbar } from '@/components/SelectionToolbar'

/** Guard click handler: no-op when user has an active text selection (drag-select). */
function hasActiveSelection(): boolean {
  const sel = window.getSelection()
  return sel !== null && sel.toString().trim().length > 0
}

// Search mode type
type SearchMode = 'keyword' | 'phrase' | 'regex' | 'file'

// Unified result type for combining text, symbol, and dependency search results
type UnifiedResult =
  | { kind: 'text'; data: TextSearchResult }
  | { kind: 'symbol'; data: Symbol }
  | { kind: 'dependency'; data: DependencySearchResult }

// Source type options
const SOURCE_TYPES = [
  { value: 'symbol', label: 'Definitions' },
  { value: 'reference', label: 'References' },
  { value: 'comment', label: 'Comments' },
  { value: 'docstring', label: 'Docstrings' },
  { value: 'commit_message', label: 'Commit Messages' },
  { value: 'file_content', label: 'File Content' },
  { value: 'dependency', label: 'Dependencies' },
]

const ALL_SOURCE_TYPE_VALUES = SOURCE_TYPES.map((t) => t.value)
const NON_TEXT_TYPES = new Set(['symbol', 'reference', 'dependency'])
const ALL_TEXT_TYPE_VALUES = SOURCE_TYPES.filter((t) => !NON_TEXT_TYPES.has(t.value)).map(
  (t) => t.value
)

const RESULTS_PER_PAGE = 50

/**
 * Compute per-source offset and limit for unified pagination.
 * Sources are displayed in a fixed order; this determines which slice
 * of a given source falls within the global page window.
 */
function sourceSlice(
  sourceStart: number,
  sourceTotal: number,
  globalOffset: number,
  pageSize: number
): { offset: number; limit: number } {
  const overlapStart = Math.max(sourceStart, globalOffset)
  const overlapEnd = Math.min(sourceStart + sourceTotal, globalOffset + pageSize)
  if (overlapStart >= overlapEnd) return { offset: 0, limit: 0 }
  return { offset: overlapStart - sourceStart, limit: overlapEnd - overlapStart }
}

// Sentinel values for extension dropdown actions
const EXT_SELECT_NONE = '__select_none__'
const EXT_SHOW_ALL = '__show_all__'

export default function Search(): React.ReactElement {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { toolbar, containerRef: toolbarContainerRef, handleClose } = useSelectionToolbar()

  // State from URL for CodeHeader
  const repoNameParam = searchParams.get('repo') || null
  const branchParam = searchParams.get('branch') || null
  const commitParam = searchParams.get('commit') || null

  // State from URL for search
  const query = searchParams.get('query') || ''
  const mode = (searchParams.get('mode') as SearchMode) || 'keyword'
  const caseSensitive = searchParams.get('case_sensitive') !== 'false' // default: true
  const isFileMode = mode === 'file'
  const page = parseInt(searchParams.get('page') || '1')
  const offset = (page - 1) * RESULTS_PER_PAGE

  // Parse inclusive filter params (types derived here, extensions derived after state declarations)
  const typesParam = searchParams.get('types')
  const extParam = searchParams.get('ext')
  const activeSourceTypes =
    typesParam !== null
      ? typesParam.split(',').filter((t) => ALL_SOURCE_TYPE_VALUES.includes(t))
      : [...ALL_SOURCE_TYPE_VALUES]
  const typesKey = activeSourceTypes.join(',')

  // Local state for input (debouncing)
  const [inputQuery, setInputQuery] = useState(query)

  // Sync input when URL query param changes externally (e.g. selection toolbar search)
  useEffect(() => {
    setInputQuery(query)
  }, [query])

  // Data state
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [reposLoading, setReposLoading] = useState(true)
  const [availableExtensions, setAvailableExtensions] = useState<string[]>([])

  // No ext param = all extensions included. Empty string = none selected. Otherwise, explicit list.
  const includedExtensions =
    extParam !== null ? (extParam ? extParam.split(',') : []) : [...availableExtensions]
  // Use a stable sentinel when extParam is null (all extensions) to avoid
  // re-triggering the search effect when availableExtensions loads asynchronously.
  const extKey = extParam !== null ? includedExtensions.join(',') : '__all__'
  const [results, setResults] = useState<UnifiedResult[]>([])
  const [fileResults, setFileResults] = useState<FileSearchResult[]>([])
  const [totalResults, setTotalResults] = useState(0)
  const [paginationTotal, setPaginationTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Per-source totals for unified pagination (symbols → deps → text ordering).
  // Stored in state so they persist across page changes within the same query.
  // Reset when search parameters change (tracked via searchKey).
  const [sourceTotals, setSourceTotals] = useState({ symbol: 0, dep: 0, text: 0 })
  const [totalsDiscovered, setTotalsDiscovered] = useState(false)
  const [totalsSearchKey, setTotalsSearchKey] = useState('')

  // Look up repo ID from repoName param
  const selectedRepoId = repoNameParam
    ? repositories.find((r) => r.name === repoNameParam)?.id
    : undefined

  // Debounce search - update URL after delay
  useEffect(() => {
    if (!inputQuery.trim()) return
    // Only update URL when the query text actually changed; skip when
    // other URL params (e.g. page) changed to avoid resetting pagination.
    if (inputQuery === query) return

    const timer = setTimeout(() => {
      const newParams = new URLSearchParams(searchParams)
      newParams.set('query', inputQuery)
      newParams.delete('page') // Reset to page 1 on new search
      setSearchParams(newParams, { replace: true })
    }, 300)

    return () => clearTimeout(timer)
  }, [inputQuery, query, searchParams, setSearchParams])

  // Load repositories
  useEffect(() => {
    const loadRepos = async () => {
      try {
        const repos = await getRepositories()
        setRepositories(repos)
      } catch (err) {
        console.error('Failed to load repositories:', err)
      } finally {
        setReposLoading(false)
      }
    }
    loadRepos()
  }, [])

  // Load available extensions when repo/branch changes
  useEffect(() => {
    const loadExtensions = async () => {
      try {
        const response = await getFileExtensions({
          repository_id: selectedRepoId,
          branch: branchParam || undefined,
          scope: selectedRepoId ? undefined : 'latest',
        })
        setAvailableExtensions(response.extensions)
      } catch (err) {
        console.error('Failed to load extensions:', err)
        setAvailableExtensions([])
      }
    }
    loadExtensions()
  }, [selectedRepoId, branchParam])

  // Perform search when query or filters change
  useEffect(() => {
    let cancelled = false

    if (!query.trim()) {
      setResults([])
      setFileResults([])
      setTotalResults(0)
      setPaginationTotal(0)
      return
    }

    // Don't search until repos are loaded when a repo filter is set,
    // otherwise selectedRepoId is undefined and the search runs unfiltered.
    if (repoNameParam && reposLoading) {
      return
    }
    // When a commit filter is set, also defer if repoNameParam is present but
    // selectedRepoId hasn't resolved yet (race: reposLoading=false but
    // repositories state hasn't propagated to derived selectedRepoId).
    // Only defer while repositories haven't been populated yet — if repos are
    // loaded but the name doesn't match, fall through and search unfiltered.
    if (commitParam && repoNameParam && selectedRepoId === undefined && repositories.length === 0) {
      return
    }

    const performSearch = async () => {
      setLoading(true)
      setError(null)

      try {
        // scope is only passed when no repository is selected (global search)
        const scope = selectedRepoId ? undefined : 'latest'

        // When ext param is set, pass those extensions to backend; otherwise undefined (all)
        const apiExtensions = extParam !== null ? includedExtensions : undefined

        // No extensions selected — no results possible, skip search entirely
        if (apiExtensions !== undefined && apiExtensions.length === 0) {
          setResults([])
          setFileResults([])
          setTotalResults(0)
          setPaginationTotal(0)
          setLoading(false)
          return
        }

        if (isFileMode) {
          // File search mode
          const response = await searchFiles({
            q: query,
            repository: repoNameParam || undefined,
            branch: branchParam || undefined,
            commit_hash: commitParam || undefined,
            extensions: apiExtensions,
            scope,
            limit: RESULTS_PER_PAGE,
            offset,
          })
          if (cancelled) return
          setFileResults(response.files)
          setResults([])
          setTotalResults(response.total_count)
          setPaginationTotal(response.total_count)
        } else {
          // Text/symbol/reference search mode
          const textSourceTypes = activeSourceTypes.filter((t) => !NON_TEXT_TYPES.has(t))
          const hasSymbol = activeSourceTypes.includes('symbol')
          const hasReference = activeSourceTypes.includes('reference')
          const hasDependency = activeSourceTypes.includes('dependency')
          const callText = textSourceTypes.length > 0 || hasReference
          const allTextTypesSelected = ALL_TEXT_TYPE_VALUES.every((v) =>
            textSourceTypes.includes(v)
          )

          // Unified pagination: sources in order symbols → deps → text.
          // On page 1 (offset=0), fetch all sources with full limit and
          // learn totals from the responses. On later pages, use cached
          // totals to compute per-source slices. If deep-linking to a
          // page > 1 without cached totals, do a discovery fetch first.

          // Build source_types for the text API
          let apiSourceTypes: string[] | undefined
          if (callText) {
            if (allTextTypesSelected && !hasReference) {
              apiSourceTypes = undefined
            } else {
              apiSourceTypes = [...textSourceTypes, ...(hasReference ? ['reference'] : [])]
            }
          }

          // Detect whether the search parameters changed (vs. just a page change).
          const currentSearchKey = [
            query,
            mode,
            caseSensitive,
            selectedRepoId,
            branchParam,
            commitParam,
            typesKey,
            extKey,
          ].join('|')
          const searchKeyChanged = currentSearchKey !== totalsSearchKey
          const hasCachedTotals = !searchKeyChanged && totalsDiscovered

          // Use cached totals only if they're still valid for this search
          let symbolTotal = hasCachedTotals && hasSymbol ? sourceTotals.symbol : 0
          let depTotal = hasCachedTotals && hasDependency ? sourceTotals.dep : 0
          let textTotal = hasCachedTotals && callText ? sourceTotals.text : 0

          // Deep link to page > 1 without cached totals: discover first
          if (offset > 0 && !hasCachedTotals) {
            const discoveryPromises: Promise<void>[] = []
            if (hasSymbol) {
              discoveryPromises.push(
                searchSymbols({
                  q: query,
                  repository_id: selectedRepoId,
                  branch: branchParam || undefined,
                  commit: selectedRepoId && commitParam ? commitParam : undefined,
                  extensions: apiExtensions,
                  mode: mode === 'regex' ? 'regex' : undefined,
                  case_sensitive: caseSensitive,
                  scope,
                  limit: 1,
                  offset: 0,
                }).then((r) => {
                  symbolTotal = r.total
                })
              )
            }
            if (callText) {
              discoveryPromises.push(
                searchText({
                  q: query,
                  mode: mode as 'keyword' | 'phrase' | 'regex',
                  repo: selectedRepoId,
                  branch: branchParam || undefined,
                  commit: selectedRepoId && commitParam ? commitParam : undefined,
                  source_types: apiSourceTypes,
                  extensions: apiExtensions,
                  case_sensitive: caseSensitive,
                  scope,
                  limit: 1,
                  offset: 0,
                }).then((r) => {
                  textTotal = r.total
                })
              )
            }
            if (hasDependency) {
              discoveryPromises.push(
                searchDependencies({
                  q: query,
                  repository_id: selectedRepoId,
                  branch: branchParam || undefined,
                  limit: 1,
                  offset: 0,
                }).then((r) => {
                  depTotal = r.total
                })
              )
            }
            await Promise.all(discoveryPromises)
            if (cancelled) return
          }

          // Compute per-source slices for this page.
          // On page 1 without cached totals, totals are 0 so all slices
          // have limit=0 — we fetch all sources with RESULTS_PER_PAGE instead.
          const isFirstPage = offset === 0 && !hasCachedTotals
          const depStart = symbolTotal
          const txtStart = depStart + depTotal

          const symSlice = sourceSlice(0, symbolTotal, offset, RESULTS_PER_PAGE)
          const depSlice = sourceSlice(depStart, depTotal, offset, RESULTS_PER_PAGE)
          const txtSlice = sourceSlice(txtStart, textTotal, offset, RESULTS_PER_PAGE)

          const promises: Promise<void>[] = []
          let symbolResults: Symbol[] = []
          let textResults: TextSearchResult[] = []
          let depResults: DependencySearchResult[] = []

          if (hasSymbol && (isFirstPage || symSlice.limit > 0)) {
            promises.push(
              searchSymbols({
                q: query,
                repository_id: selectedRepoId,
                branch: branchParam || undefined,
                commit: selectedRepoId && commitParam ? commitParam : undefined,
                extensions: apiExtensions,
                mode: mode === 'regex' ? 'regex' : undefined,
                case_sensitive: caseSensitive,
                scope,
                limit: isFirstPage ? RESULTS_PER_PAGE : symSlice.limit,
                offset: isFirstPage ? 0 : symSlice.offset,
              }).then((response) => {
                symbolResults = response.items
                symbolTotal = response.total
              })
            )
          }

          if (callText && (isFirstPage || txtSlice.limit > 0)) {
            promises.push(
              searchText({
                q: query,
                mode: mode as 'keyword' | 'phrase' | 'regex',
                repo: selectedRepoId,
                branch: branchParam || undefined,
                commit: selectedRepoId && commitParam ? commitParam : undefined,
                source_types: apiSourceTypes,
                extensions: apiExtensions,
                case_sensitive: caseSensitive,
                scope,
                limit: isFirstPage ? RESULTS_PER_PAGE : txtSlice.limit,
                offset: isFirstPage ? 0 : txtSlice.offset,
              }).then((response) => {
                textResults = response.results
                textTotal = response.total
              })
            )
          }

          if (hasDependency && (isFirstPage || depSlice.limit > 0)) {
            promises.push(
              searchDependencies({
                q: query,
                repository_id: selectedRepoId,
                branch: branchParam || undefined,
                limit: isFirstPage ? RESULTS_PER_PAGE : depSlice.limit,
                offset: isFirstPage ? 0 : depSlice.offset,
              }).then((response) => {
                depResults = response.results
                depTotal = response.total
              })
            )
          }

          await Promise.all(promises)
          if (cancelled) return

          // Update stored totals
          setSourceTotals({ symbol: symbolTotal, dep: depTotal, text: textTotal })
          setTotalsDiscovered(true)
          setTotalsSearchKey(currentSearchKey)

          // Build unified result list in order: symbols → deps → text.
          // On first page, we fetched generously; slice to page size.
          const unified: UnifiedResult[] = [
            ...symbolResults.map((s) => ({ kind: 'symbol' as const, data: s })),
            ...depResults.map((d) => ({ kind: 'dependency' as const, data: d })),
            ...textResults.map((t) => ({ kind: 'text' as const, data: t })),
          ].slice(0, RESULTS_PER_PAGE)
          setResults(unified)
          setFileResults([])
          const combinedTotal = symbolTotal + depTotal + textTotal
          setTotalResults(combinedTotal)
          setPaginationTotal(combinedTotal)
        }
      } catch (err) {
        if (cancelled) return
        console.error('Search failed:', err)
        setError(err instanceof Error ? err.message : 'Search failed')
        setResults([])
        setFileResults([])
        setTotalResults(0)
        setPaginationTotal(0)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    performSearch()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    query,
    mode,
    caseSensitive,
    selectedRepoId,
    repoNameParam,
    reposLoading,
    branchParam,
    commitParam,
    typesKey,
    extKey,
    offset,
  ])

  // CodeHeader handlers
  const handleHeaderRepoChange = (newRepoName: string) => {
    if (newRepoName) {
      // Navigate to specific repo, resetting to default branch and HEAD
      navigate(`/search?repo=${newRepoName}`)
    } else {
      // "All Repositories" selected — remove repo/branch/commit from URL
      const newParams = new URLSearchParams(searchParams)
      newParams.delete('repo')
      newParams.delete('branch')
      newParams.delete('commit')
      if (query) newParams.set('query', query)
      setSearchParams(newParams, { replace: true })
    }
  }

  const handleHeaderBranchChange = (newBranch: string) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('branch', newBranch)
    newParams.delete('commit') // Reset to HEAD when branch changes
    setSearchParams(newParams, { replace: true })
  }

  const handleHeaderCommitChange = (newCommit: string) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('commit', newCommit)
    setSearchParams(newParams, { replace: true })
  }

  const handleTabChange = (tab: TabValue) => {
    const params = new URLSearchParams()
    if (repoNameParam) params.set('repo', repoNameParam)
    if (branchParam) params.set('branch', branchParam)
    if (commitParam) params.set('commit', commitParam)

    switch (tab) {
      case 'browse':
        if (repoNameParam) {
          navigate(`/browse/${repoNameParam}?${params.toString()}`)
        } else {
          navigate('/')
        }
        break
      case 'search':
        // Already on search
        break
      case 'history':
        navigate(`/history?${params.toString()}`)
        break
      case 'logical-view':
        navigate(`/logical-view?${params.toString()}`)
        break
      case 'dependencies':
        navigate(`/dependencies?${params.toString()}`)
        break
      case 'help':
        navigate(`/help?${params.toString()}`)
        break
    }
  }

  // Search filter handlers
  const handleModeChange = (newMode: string) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('mode', newMode)
    newParams.delete('page')
    // Clear types when switching to file mode (they don't apply)
    if (newMode === 'file') {
      newParams.delete('types')
    }
    setSearchParams(newParams, { replace: true })
  }

  const handleCaseSensitiveToggle = () => {
    const newParams = new URLSearchParams(searchParams)
    if (caseSensitive) {
      newParams.set('case_sensitive', 'false')
    } else {
      newParams.delete('case_sensitive') // default is true, so remove param
    }
    newParams.delete('page')
    setSearchParams(newParams, { replace: true })
  }

  const handleSourceTypeToggle = (type: string) => {
    const newParams = new URLSearchParams(searchParams)
    const current = activeSourceTypes
    const updated = current.includes(type) ? current.filter((t) => t !== type) : [...current, type]

    // If all types selected, remove param (back to default = all shown)
    if (updated.length === ALL_SOURCE_TYPE_VALUES.length) {
      newParams.delete('types')
    } else {
      newParams.set('types', updated.join(','))
    }
    newParams.delete('page')
    setSearchParams(newParams, { replace: true })
  }

  const handleIncludeExtensionChange = (included: string[]) => {
    const newParams = new URLSearchParams(searchParams)
    // If all extensions are selected, remove param (back to default = all shown).
    // Guard with length > 0 so an empty availableExtensions list (not loaded yet)
    // doesn't falsely match 0 === 0.
    if (
      availableExtensions.length > 0 &&
      included.length === availableExtensions.length &&
      availableExtensions.every((ext) => included.includes(ext))
    ) {
      newParams.delete('ext')
    } else if (included.length > 0) {
      newParams.set('ext', included.join(','))
    } else {
      // Empty array = nothing selected (no results)
      newParams.set('ext', '')
    }
    newParams.delete('page')
    setSearchParams(newParams, { replace: true })
  }

  const handlePageChange = (_event: React.ChangeEvent<unknown>, value: number) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('page', value.toString())
    setSearchParams(newParams, { replace: true })
    // Scroll to top of results
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleUnifiedResultClick = (result: UnifiedResult) => {
    if (result.kind === 'text') {
      handleResultClick(result.data)
    } else if (result.kind === 'dependency') {
      // Dependency result - navigate to the manifest file in browse
      const dep = result.data
      if (!dep.file_path) return

      const params = new URLSearchParams()
      params.set('repo', dep.repository_name)
      if (branchParam) params.set('branch', branchParam)
      if (commitParam) params.set('commit', commitParam)
      if (dep.source_line) params.set('line', dep.source_line.toString())

      const encodedPath = dep.file_path
        .split('/')
        .map((segment) => encodeURIComponent(segment))
        .join('/')

      navigate(
        `/browse/${encodeURIComponent(dep.repository_name)}/${encodedPath}?${params.toString()}`
      )
    } else {
      // Symbol result - navigate to browse at the file and line
      const repo = repositories.find((r) => r.id === result.data.repository_id)
      if (!repo || !result.data.file_path) return

      const params = new URLSearchParams()
      params.set('repo', repo.name)
      if (branchParam) params.set('branch', branchParam)
      if (commitParam) params.set('commit', commitParam)
      params.set('line', result.data.start_line.toString())

      navigate(
        `/browse/${encodeURIComponent(repo.name)}/${result.data.file_path}?${params.toString()}`
      )
    }
  }

  const handleResultClick = (result: TextSearchResult) => {
    const resultRepoName = result.repository_name
    const filePath = result.file_path

    // Build URL params
    const params = new URLSearchParams()
    params.set('repo', resultRepoName)
    if (result.branch) {
      params.set('branch', result.branch)
    }
    if (result.commit_hash && result.commit_hash !== 'unknown') {
      params.set('commit', result.commit_hash)
    }

    if (result.source_type === 'commit_message') {
      // Commit messages navigate to History, focused on that commit
      navigate(`/history?${params.toString()}`)
    } else if (filePath) {
      // File-based results navigate to Browse at the specific file/line
      if (result.source_line) {
        params.set('line', result.source_line.toString())
      }
      // Show markdown files as raw text so line-number navigation works
      if (isMarkdownFile(filePath, result.language)) {
        params.set('view', 'raw')
      }
      const encodedFilePath = filePath
        .split('/')
        .map((segment) => encodeURIComponent(segment))
        .join('/')
      navigate(
        `/browse/${encodeURIComponent(resultRepoName)}/${encodedFilePath}?${params.toString()}`
      )
    } else {
      // Fallback: navigate to repository root in Browse
      navigate(`/browse/${encodeURIComponent(resultRepoName)}?${params.toString()}`)
    }
  }

  const handleFileResultClick = (file: FileSearchResult) => {
    // Navigate to Browse with the file's location
    const params = new URLSearchParams()
    if (branchParam) {
      params.set('branch', branchParam)
    }
    if (file.commit_hash) {
      params.set('commit', file.commit_hash)
    }

    // Encode each path segment to handle special characters
    const encodedPath = file.path
      .split('/')
      .map((segment) => encodeURIComponent(segment))
      .join('/')

    const queryString = params.toString()
    navigate(
      `/browse/${encodeURIComponent(file.repository_name)}/${encodedPath}${queryString ? `?${queryString}` : ''}`
    )
  }

  const handleClearFilters = () => {
    const newParams = new URLSearchParams(searchParams)
    newParams.delete('types')
    newParams.delete('ext')
    newParams.delete('page')
    setSearchParams(newParams, { replace: true })
  }

  const handleSelectNone = () => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('types', '')
    newParams.delete('page')
    setSearchParams(newParams, { replace: true })
  }

  const getSourceTypeBadgeColor = (
    sourceType: string
  ): 'default' | 'primary' | 'secondary' | 'info' | 'success' | 'warning' => {
    switch (sourceType) {
      case 'symbol':
        return 'primary'
      case 'reference':
        return 'warning'
      case 'comment':
        return 'info'
      case 'docstring':
        return 'success'
      case 'commit_message':
        return 'secondary'
      case 'file_content':
        return 'default'
      case 'dependency':
        return 'info'
      default:
        return 'default'
    }
  }

  const formatSourceType = (sourceType: string): string => {
    return sourceType.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())
  }

  const totalPages = Math.ceil(paginationTotal / RESULTS_PER_PAGE)
  const hasFilters = typesParam !== null || extParam !== null

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Global Header with tabs */}
      <CodeHeader
        currentTab="search"
        repoName={repoNameParam}
        branch={branchParam}
        commit={commitParam}
        onRepoChange={handleHeaderRepoChange}
        onBranchChange={handleHeaderBranchChange}
        onCommitChange={handleHeaderCommitChange}
        onTabChange={handleTabChange}
      />

      {/* Main Content */}
      <Box ref={toolbarContainerRef} sx={{ flex: 1, overflow: 'auto', p: 3 }}>
        <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
          {/* Search Input */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <TextField
                fullWidth
                label="Search query"
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                placeholder="Enter search query..."
                autoFocus
                InputProps={{
                  startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
              />
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <FormControl sx={{ minWidth: 150 }}>
                  <InputLabel>Mode</InputLabel>
                  <Select
                    value={mode}
                    label="Mode"
                    onChange={(e) => handleModeChange(e.target.value)}
                    MenuProps={MENU_PROPS}
                  >
                    <MenuItem value="keyword">Keyword (fuzzy)</MenuItem>
                    <MenuItem value="phrase">Phrase</MenuItem>
                    <MenuItem value="regex">Regex</MenuItem>
                    <MenuItem value="file">File</MenuItem>
                  </Select>
                </FormControl>
                <Tooltip
                  title={
                    <Box sx={{ maxWidth: 320 }}>
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>
                        Keyword (fuzzy)
                      </Typography>
                      <Typography variant="caption" display="block">
                        Matches individual words in any order with stemming.
                      </Typography>
                      <Typography
                        variant="caption"
                        display="block"
                        sx={{ fontFamily: 'monospace', opacity: 0.8, ml: 1 }}
                      >
                        run &rarr; matches &ldquo;run&rdquo;, &ldquo;running&rdquo;,
                        &ldquo;runner&rdquo;
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 600, mt: 0.5 }}
                        display="block"
                      >
                        Phrase
                      </Typography>
                      <Typography variant="caption" display="block">
                        Matches the exact sequence of words. Good for single-word exact match.
                      </Typography>
                      <Typography
                        variant="caption"
                        display="block"
                        sx={{ fontFamily: 'monospace', opacity: 0.8, ml: 1 }}
                      >
                        File &rarr; matches &ldquo;File&rdquo; but not &ldquo;FileAdapter&rdquo;
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 600, mt: 0.5 }}
                        display="block"
                      >
                        Regex
                      </Typography>
                      <Typography variant="caption" display="block">
                        PostgreSQL regular expression for advanced pattern matching.
                      </Typography>
                      <Typography
                        variant="caption"
                        display="block"
                        sx={{ fontFamily: 'monospace', opacity: 0.8, ml: 1 }}
                      >
                        \bFile\b &rarr; exact word boundary
                      </Typography>
                      <Typography
                        variant="caption"
                        display="block"
                        sx={{ fontFamily: 'monospace', opacity: 0.8, ml: 1 }}
                      >
                        get_.*_by_id &rarr; wildcard matching
                      </Typography>
                      <Typography
                        variant="caption"
                        display="block"
                        sx={{ fontFamily: 'monospace', opacity: 0.8, ml: 1 }}
                      >
                        [A-Z][a-z]+Service &rarr; class name patterns
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 600, mt: 0.5 }}
                        display="block"
                      >
                        File
                      </Typography>
                      <Typography variant="caption" display="block">
                        Search files by path or name.
                      </Typography>
                      <Typography
                        variant="caption"
                        display="block"
                        sx={{ fontFamily: 'monospace', opacity: 0.8, ml: 1 }}
                      >
                        utils.py &rarr; find by filename
                      </Typography>
                    </Box>
                  }
                  arrow
                  placement="bottom"
                >
                  <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.disabled', cursor: 'help' }} />
                </Tooltip>
                {!isFileMode && (
                  <Tooltip
                    title={
                      caseSensitive
                        ? 'Case-sensitive (click to toggle)'
                        : 'Case-insensitive (click to toggle)'
                    }
                  >
                    <ToggleButton
                      value="case-sensitive"
                      selected={caseSensitive}
                      onChange={handleCaseSensitiveToggle}
                      size="small"
                      sx={{
                        px: 1,
                        py: 0.5,
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        textTransform: 'none',
                        minWidth: 32,
                      }}
                    >
                      Aa
                    </ToggleButton>
                  </Tooltip>
                )}
              </Box>
            </Box>

            {/* Exclusion Filters */}
            <Box sx={{ mt: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Filters
                </Typography>
                <Tooltip
                  title="Check items to include them in results. When no filters are set, everything is shown."
                  arrow
                  placement="right"
                >
                  <HelpOutlineIcon sx={{ fontSize: 14, color: 'text.disabled', cursor: 'help' }} />
                </Tooltip>
                {isFileMode && (
                  <Typography
                    variant="caption"
                    sx={{ ml: 0.5, fontStyle: 'italic', color: 'text.secondary' }}
                  >
                    (source types not applicable in File mode)
                  </Typography>
                )}
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                <FormControl size="small" sx={{ minWidth: 180 }}>
                  <InputLabel>Extensions</InputLabel>
                  <Select
                    multiple
                    value={includedExtensions}
                    label="Extensions"
                    MenuProps={MENU_PROPS}
                    onChange={(e) => {
                      const value = e.target.value
                      const arr = typeof value === 'string' ? value.split(',') : value
                      if (arr.includes(EXT_SELECT_NONE)) {
                        handleIncludeExtensionChange([])
                        return
                      }
                      if (arr.includes(EXT_SHOW_ALL)) {
                        // Clear ext param = show all
                        const newParams = new URLSearchParams(searchParams)
                        newParams.delete('ext')
                        newParams.delete('page')
                        setSearchParams(newParams, { replace: true })
                        return
                      }
                      handleIncludeExtensionChange(arr)
                    }}
                    renderValue={(selected) =>
                      extParam === null ? (
                        <em>All</em>
                      ) : selected.length === 0 ? (
                        <em>None selected</em>
                      ) : selected.length === availableExtensions.length ? (
                        <em>All</em>
                      ) : (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {selected.map((ext) => (
                            <Chip
                              key={ext}
                              label={ext === '(none)' ? '(no extension)' : ext}
                              size="small"
                              color="primary"
                            />
                          ))}
                        </Box>
                      )
                    }
                  >
                    <MenuItem value={EXT_SHOW_ALL}>
                      <Typography variant="body2" sx={{ fontWeight: 500, fontStyle: 'italic' }}>
                        Show all extensions
                      </Typography>
                    </MenuItem>
                    <MenuItem value={EXT_SELECT_NONE}>
                      <Typography variant="body2" sx={{ fontWeight: 500, fontStyle: 'italic' }}>
                        Select none
                      </Typography>
                    </MenuItem>
                    <Divider />
                    {availableExtensions.map((ext) => (
                      <MenuItem key={ext} value={ext}>
                        <Checkbox checked={includedExtensions.includes(ext)} size="small" />
                        <Typography
                          sx={{
                            color: includedExtensions.includes(ext)
                              ? 'text.primary'
                              : 'text.secondary',
                            fontWeight: includedExtensions.includes(ext) ? 500 : 400,
                            fontStyle: ext === '(none)' ? 'italic' : 'normal',
                          }}
                        >
                          {ext === '(none)' ? '(no extension)' : ext}
                        </Typography>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormGroup row sx={{ opacity: isFileMode ? 0.5 : 1 }}>
                  {SOURCE_TYPES.map((type) => (
                    <FormControlLabel
                      key={type.value}
                      control={
                        <Checkbox
                          checked={activeSourceTypes.includes(type.value)}
                          onChange={() => handleSourceTypeToggle(type.value)}
                          size="small"
                          disabled={isFileMode}
                        />
                      }
                      label={
                        <Typography
                          variant="body2"
                          sx={{
                            color: activeSourceTypes.includes(type.value)
                              ? 'text.primary'
                              : 'text.disabled',
                            fontWeight: activeSourceTypes.includes(type.value) ? 500 : 400,
                          }}
                        >
                          {type.label}
                        </Typography>
                      }
                      sx={{ cursor: isFileMode ? 'not-allowed' : 'pointer' }}
                    />
                  ))}
                </FormGroup>
                <Button
                  onClick={handleSelectNone}
                  variant="outlined"
                  size="small"
                  disabled={isFileMode}
                >
                  Select None
                </Button>
                <Button
                  onClick={handleClearFilters}
                  variant="outlined"
                  size="small"
                  disabled={!hasFilters}
                >
                  Show All
                </Button>
              </Box>
            </Box>
          </Paper>

          {/* Results */}
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          ) : query.trim() && (isFileMode ? fileResults.length === 0 : results.length === 0) ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="text.secondary">No results found</Typography>
            </Paper>
          ) : query.trim() ? (
            <>
              {/* Results header */}
              <Box
                sx={{
                  mb: 2,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  Found {totalResults.toLocaleString()} {isFileMode ? 'file' : 'result'}
                  {totalResults !== 1 ? 's' : ''}
                </Typography>
                {totalPages > 1 && (
                  <Typography variant="body2" color="text.secondary">
                    Page {page} of {totalPages}
                  </Typography>
                )}
              </Box>

              {/* Results list */}
              <Paper>
                <List>
                  {isFileMode
                    ? fileResults.map((file, index) => (
                        <ListItem
                          key={file.id}
                          divider={index < fileResults.length - 1}
                          sx={{
                            display: 'flex',
                            alignItems: 'stretch',
                            py: 0,
                            px: 0,
                            userSelect: 'text',
                          }}
                        >
                          <ButtonBase
                            onClick={() => {
                              if (!hasActiveSelection()) handleFileResultClick(file)
                            }}
                            aria-label="Go to file"
                            sx={{
                              width: 10,
                              minWidth: 10,
                              flexShrink: 0,
                              bgcolor: 'primary.main',
                              cursor: 'pointer',
                              opacity: 0.4,
                              transition: 'opacity 0.15s',
                              '&:hover': { opacity: 1 },
                            }}
                          />
                          <Box sx={{ flex: 1, py: 1.5, px: 2 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <InsertDriveFileIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                              <ButtonBase
                                onClick={() => {
                                  if (!hasActiveSelection()) handleFileResultClick(file)
                                }}
                                sx={{
                                  fontFamily: 'monospace',
                                  fontWeight: 500,
                                  fontSize: '0.875rem',
                                  userSelect: 'text',
                                  '&:hover': {
                                    textDecoration: 'underline',
                                    color: 'primary.main',
                                  },
                                }}
                              >
                                {file.name}
                              </ButtonBase>
                              {file.language && (
                                <Chip label={file.language} size="small" variant="outlined" />
                              )}
                            </Box>
                            <Typography
                              variant="body2"
                              sx={{
                                color: 'text.secondary',
                                fontFamily: 'monospace',
                                fontSize: '0.8rem',
                                mt: 0.5,
                              }}
                            >
                              {file.repository_name} / {file.path}
                            </Typography>
                          </Box>
                        </ListItem>
                      ))
                    : results.map((result, index) => (
                        <ListItem
                          key={`${result.kind}-${result.kind === 'text' ? result.data.source_type : result.kind}-${result.data.id}`}
                          divider={index < results.length - 1}
                          sx={{
                            display: 'flex',
                            alignItems: 'stretch',
                            py: 0,
                            px: 0,
                            userSelect: 'text',
                          }}
                        >
                          <ButtonBase
                            onClick={() => {
                              if (!hasActiveSelection()) handleUnifiedResultClick(result)
                            }}
                            aria-label="Go to result"
                            sx={{
                              width: 10,
                              minWidth: 10,
                              flexShrink: 0,
                              bgcolor: 'primary.main',
                              cursor: 'pointer',
                              opacity: 0.4,
                              transition: 'opacity 0.15s',
                              '&:hover': { opacity: 1 },
                            }}
                          />
                          <Box sx={{ flex: 1, py: 1.5, px: 2 }}>
                            {result.kind === 'symbol' ? (
                              <Box
                                sx={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 1,
                                  mb: 0.5,
                                }}
                              >
                                <Chip label="Symbol" size="small" color="primary" />
                                <Chip label={result.data.kind} size="small" variant="outlined" />
                                <ButtonBase
                                  onClick={() => {
                                    if (!hasActiveSelection()) handleUnifiedResultClick(result)
                                  }}
                                  sx={{
                                    fontFamily: 'monospace',
                                    fontSize: '0.875rem',
                                    userSelect: 'text',
                                    '&:hover': {
                                      textDecoration: 'underline',
                                      color: 'primary.main',
                                    },
                                  }}
                                >
                                  {repositories.find((r) => r.id === result.data.repository_id)
                                    ?.name || ''}
                                  {result.data.file_path && ` / ${result.data.file_path}`}:
                                  {result.data.start_line}
                                </ButtonBase>
                              </Box>
                            ) : result.kind === 'dependency' ? (
                              <Box
                                sx={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 1,
                                  mb: 0.5,
                                }}
                              >
                                <Chip label="Dependency" size="small" color="info" />
                                <Chip
                                  label={result.data.dependency_type}
                                  size="small"
                                  variant="outlined"
                                />
                                {!result.data.is_direct && (
                                  <Chip
                                    label="transitive"
                                    size="small"
                                    variant="outlined"
                                    sx={{ fontStyle: 'italic' }}
                                  />
                                )}
                                <ButtonBase
                                  onClick={() => {
                                    if (!hasActiveSelection()) handleUnifiedResultClick(result)
                                  }}
                                  sx={{
                                    fontFamily: 'monospace',
                                    fontSize: '0.875rem',
                                    userSelect: 'text',
                                    '&:hover': {
                                      textDecoration: 'underline',
                                      color: 'primary.main',
                                    },
                                  }}
                                >
                                  {result.data.repository_name}
                                  {result.data.file_path && ` / ${result.data.file_path}`}
                                </ButtonBase>
                                <Chip
                                  label={result.data.language}
                                  size="small"
                                  variant="outlined"
                                />
                              </Box>
                            ) : (
                              <Box
                                sx={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 1,
                                  mb: 0.5,
                                }}
                              >
                                <Chip
                                  label={formatSourceType(result.data.source_type)}
                                  size="small"
                                  color={getSourceTypeBadgeColor(result.data.source_type)}
                                />
                                <ButtonBase
                                  onClick={() => {
                                    if (!hasActiveSelection()) handleUnifiedResultClick(result)
                                  }}
                                  sx={{
                                    fontFamily: 'monospace',
                                    fontSize: '0.875rem',
                                    userSelect: 'text',
                                    '&:hover': {
                                      textDecoration: 'underline',
                                      color: 'primary.main',
                                    },
                                  }}
                                >
                                  {result.data.repository_name}
                                  {result.data.file_path && ` / ${result.data.file_path}`}
                                  {result.data.source_line && `:${result.data.source_line}`}
                                </ButtonBase>
                                {result.data.language && (
                                  <Chip
                                    label={result.data.language}
                                    size="small"
                                    variant="outlined"
                                  />
                                )}
                              </Box>
                            )}
                            <Typography
                              variant="body2"
                              component="div"
                              sx={{
                                color: 'text.primary',
                                fontFamily: 'monospace',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                              }}
                            >
                              {result.kind === 'symbol' ? (
                                highlightMatches(
                                  result.data.signature ||
                                    result.data.qualified_name ||
                                    result.data.name,
                                  query,
                                  'keyword'
                                )
                              ) : result.kind === 'dependency' ? (
                                <Box
                                  component="span"
                                  sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                                >
                                  {highlightMatches(result.data.package_name, query, 'keyword')}
                                  {result.data.version_spec && (
                                    <Chip
                                      label={result.data.version_spec}
                                      size="small"
                                      variant="outlined"
                                      sx={{ fontFamily: 'monospace', height: 20 }}
                                    />
                                  )}
                                  {result.data.resolved_version && (
                                    <Chip
                                      label={`= ${result.data.resolved_version}`}
                                      size="small"
                                      sx={{ fontFamily: 'monospace', height: 20 }}
                                    />
                                  )}
                                </Box>
                              ) : result.data.headline ? (
                                <span
                                  dangerouslySetInnerHTML={{
                                    __html: sanitizeHeadline(result.data.headline),
                                  }}
                                />
                              ) : (
                                highlightMatches(result.data.content, query, mode)
                              )}
                            </Typography>
                          </Box>
                        </ListItem>
                      ))}
                </List>
              </Paper>

              {/* Pagination */}
              {totalPages > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={handlePageChange}
                    color="primary"
                    showFirstButton
                    showLastButton
                  />
                </Box>
              )}
            </>
          ) : (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              {isFileMode ? (
                <InsertDriveFileIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
              ) : (
                <SearchIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
              )}
              <Typography color="text.secondary">
                {isFileMode
                  ? 'Enter a file name to search for files by path'
                  : 'Enter a search query to find symbols, comments, docstrings, commit messages, dependencies, and files'}
              </Typography>
            </Paper>
          )}
        </Box>
      </Box>
      <SelectionToolbar
        toolbar={toolbar}
        onCopy={() => {
          const text = toolbar?.selectedText
          if (text) navigator.clipboard?.writeText(text)
        }}
        onSearch={() => {
          const text = toolbar?.selectedText
          if (!text) return
          const newParams = new URLSearchParams(searchParams)
          newParams.set('query', text)
          newParams.delete('page')
          setSearchParams(newParams, { replace: true })
        }}
        onClose={handleClose}
      />
    </Box>
  )
}
