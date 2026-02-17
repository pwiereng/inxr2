import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
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
  ListItemButton,
  ListItemText,
  Pagination,
  CircularProgress,
  Alert,
  Checkbox,
  FormControlLabel,
  FormGroup,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'

import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'

import { CodeHeader, type TabValue } from '@/components/CodeHeader'
import { highlightMatches } from '@/lib/highlightMatches'
import {
  searchText,
  searchFiles,
  searchSymbols,
  getRepositories,
  type TextSearchParams,
  type TextSearchResult,
  type FileSearchResult,
  type Repository,
  type Symbol,
} from '@/lib/api'

// Search mode type
type SearchMode = 'keyword' | 'phrase' | 'regex' | 'file'

// Unified result type for combining text and symbol search results
type UnifiedResult =
  | { kind: 'text'; data: TextSearchResult }
  | { kind: 'symbol'; data: Symbol }

// Source type options
const SOURCE_TYPES = [
  { value: 'symbol', label: 'Symbols' },
  { value: 'comment', label: 'Comments' },
  { value: 'docstring', label: 'Docstrings' },
  { value: 'commit_message', label: 'Commit Messages' },
  { value: 'file_content', label: 'File Content' },
]

// Common language options (can be expanded)
const LANGUAGES = [
  'python',
  'typescript',
  'javascript',
  'java',
  'go',
  'rust',
  'cpp',
  'markdown',
  'json',
  'yaml',
]

const ALL_SOURCE_TYPE_VALUES = SOURCE_TYPES.map((t) => t.value)
const ALL_TEXT_TYPE_VALUES = SOURCE_TYPES.filter((t) => t.value !== 'symbol').map((t) => t.value)

const RESULTS_PER_PAGE = 20

export default function Search() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // State from URL for CodeHeader
  const repoNameParam = searchParams.get('repo') || null
  const branchParam = searchParams.get('branch') || null
  const commitParam = searchParams.get('commit') || null

  // State from URL for search
  const query = searchParams.get('query') || ''
  const mode = (searchParams.get('mode') as SearchMode) || 'keyword'
  const isFileMode = mode === 'file'
  const page = parseInt(searchParams.get('page') || '1')
  const offset = (page - 1) * RESULTS_PER_PAGE

  // Parse array params
  // No source_types param = all selected (default). Param present = only those selected.
  const sourceTypesParam = searchParams.get('source_types')
  const languagesParam = searchParams.get('languages')
  const selectedSourceTypes: string[] =
    sourceTypesParam === null
      ? ALL_SOURCE_TYPE_VALUES
      : sourceTypesParam
        ? sourceTypesParam.split(',')
        : []
  const selectedLanguages = languagesParam ? languagesParam.split(',') : []
  const sourceTypesKey = selectedSourceTypes.join(',')
  const languagesKey = selectedLanguages.join(',')

  // Local state for input (debouncing)
  const [inputQuery, setInputQuery] = useState(query)

  // Data state
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [results, setResults] = useState<UnifiedResult[]>([])
  const [fileResults, setFileResults] = useState<FileSearchResult[]>([])
  const [totalResults, setTotalResults] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Look up repo ID from repoName param
  const selectedRepoId = repoNameParam
    ? repositories.find((r) => r.name === repoNameParam)?.id
    : undefined

  // Debounce search - update URL after delay
  useEffect(() => {
    if (!inputQuery.trim()) return

    const timer = setTimeout(() => {
      const newParams = new URLSearchParams(searchParams)
      newParams.set('query', inputQuery)
      newParams.delete('page') // Reset to page 1 on new search
      setSearchParams(newParams, { replace: true })
    }, 300)

    return () => clearTimeout(timer)
  }, [inputQuery, searchParams, setSearchParams])

  // Load repositories
  useEffect(() => {
    const loadRepos = async () => {
      try {
        const repos = await getRepositories()
        setRepositories(repos)
      } catch (err) {
        console.error('Failed to load repositories:', err)
      }
    }
    loadRepos()
  }, [])

  // Perform search when query or filters change
  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      setFileResults([])
      setTotalResults(0)
      return
    }

    const performSearch = async () => {
      setLoading(true)
      setError(null)

      try {
        if (isFileMode) {
          // File search mode
          const response = await searchFiles({
            q: query,
            repository: repoNameParam || undefined,
            branch: branchParam || undefined,
            commit_hash: commitParam || undefined,
            language: selectedLanguages[0] || undefined,
            limit: RESULTS_PER_PAGE,
          })
          setFileResults(response.files)
          setResults([])
          setTotalResults(response.total_count)
        } else {
          // Text/symbol search mode
          const textSourceTypes = selectedSourceTypes.filter((t) => t !== 'symbol')
          const hasSymbol = selectedSourceTypes.includes('symbol')
          const callText = textSourceTypes.length > 0
          const allTextTypesSelected = ALL_TEXT_TYPE_VALUES.every((v) =>
            textSourceTypes.includes(v)
          )

          const promises: Promise<void>[] = []
          let symbolResults: Symbol[] = []
          let textResults: TextSearchResult[] = []
          let symbolTotal = 0
          let textTotal = 0

          if (hasSymbol) {
            promises.push(
              searchSymbols({
                q: query,
                repository_id: selectedRepoId,
                limit: RESULTS_PER_PAGE,
                offset,
              }).then((response) => {
                symbolResults = response.items
                symbolTotal = response.total
              })
            )
          }

          if (callText) {
            const params: TextSearchParams = {
              q: query,
              mode: mode as 'keyword' | 'phrase' | 'regex',
              repo: selectedRepoId,
              branch: branchParam || undefined,
              source_types: allTextTypesSelected ? undefined : textSourceTypes,
              languages: selectedLanguages.length > 0 ? selectedLanguages : undefined,
              limit: RESULTS_PER_PAGE,
              offset,
            }
            promises.push(
              searchText(params).then((response) => {
                textResults = response.results
                textTotal = response.total
              })
            )
          }

          await Promise.all(promises)

          const unified: UnifiedResult[] = [
            ...symbolResults.map((s) => ({ kind: 'symbol' as const, data: s })),
            ...textResults.map((t) => ({ kind: 'text' as const, data: t })),
          ]
          setResults(unified)
          setFileResults([])
          setTotalResults(symbolTotal + textTotal)
        }
      } catch (err) {
        console.error('Search failed:', err)
        setError(err instanceof Error ? err.message : 'Search failed')
        setResults([])
        setFileResults([])
        setTotalResults(0)
      } finally {
        setLoading(false)
      }
    }

    performSearch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    query,
    mode,
    selectedRepoId,
    repoNameParam,
    branchParam,
    commitParam,
    sourceTypesKey,
    languagesKey,
    offset,
  ])

  // CodeHeader handlers
  const handleHeaderRepoChange = (newRepoName: string) => {
    // Navigate to new repo, resetting to default branch and HEAD
    navigate(`/search?repo=${newRepoName}`)
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
    }
  }

  // Search filter handlers
  const handleModeChange = (newMode: string) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('mode', newMode)
    newParams.delete('page')
    // Clear source_types when switching to file mode (they don't apply)
    if (newMode === 'file') {
      newParams.delete('source_types')
    }
    setSearchParams(newParams, { replace: true })
  }

  const handleSourceTypeToggle = (type: string) => {
    const newParams = new URLSearchParams(searchParams)
    const current = selectedSourceTypes
    const updated = current.includes(type) ? current.filter((t) => t !== type) : [...current, type]

    // If all types re-selected, remove param (back to default)
    if (
      updated.length === ALL_SOURCE_TYPE_VALUES.length &&
      ALL_SOURCE_TYPE_VALUES.every((v) => updated.includes(v))
    ) {
      newParams.delete('source_types')
    } else {
      newParams.set('source_types', updated.join(','))
    }
    newParams.delete('page')
    setSearchParams(newParams, { replace: true })
  }

  const handleLanguageChange = (lang: string) => {
    const newParams = new URLSearchParams(searchParams)
    if (lang) {
      newParams.set('languages', lang)
    } else {
      newParams.delete('languages')
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
    } else {
      // Symbol result - navigate to browse at the file and line
      const repo = repositories.find((r) => r.id === result.data.repository_id)
      if (!repo || !result.data.file_path) return

      const params = new URLSearchParams()
      params.set('repo', repo.name)
      if (branchParam) params.set('branch', branchParam)
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
      navigate(`/browse/${encodeURIComponent(resultRepoName)}/${filePath}?${params.toString()}`)
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

  const handleSelectAll = () => {
    const newParams = new URLSearchParams(searchParams)
    newParams.delete('source_types')
    newParams.delete('languages')
    newParams.delete('page')
    setSearchParams(newParams, { replace: true })
  }

  const getSourceTypeBadgeColor = (
    sourceType: string
  ): 'default' | 'primary' | 'secondary' | 'info' | 'success' => {
    switch (sourceType) {
      case 'symbol':
        return 'primary'
      case 'comment':
        return 'info'
      case 'docstring':
        return 'success'
      case 'commit_message':
        return 'secondary'
      case 'file_content':
        return 'default'
      default:
        return 'default'
    }
  }

  const formatSourceType = (sourceType: string): string => {
    return sourceType.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())
  }

  const totalPages = Math.ceil(totalResults / RESULTS_PER_PAGE)
  const hasFilters = sourceTypesParam !== null || selectedLanguages.length > 0

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
      <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
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
              <FormControl sx={{ minWidth: 150 }}>
                <InputLabel>Mode</InputLabel>
                <Select
                  value={mode}
                  label="Mode"
                  onChange={(e) => handleModeChange(e.target.value)}
                >
                  <MenuItem value="keyword">Keyword (fuzzy)</MenuItem>
                  <MenuItem value="phrase">Phrase</MenuItem>
                  <MenuItem value="regex">Regex</MenuItem>
                  <MenuItem value="file">File</MenuItem>
                </Select>
              </FormControl>
            </Box>

            {/* Filters */}
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <FormControl sx={{ minWidth: 150 }}>
                <InputLabel>Language</InputLabel>
                <Select
                  value={selectedLanguages[0] || ''}
                  label="Language"
                  onChange={(e) => handleLanguageChange(e.target.value)}
                >
                  <MenuItem value="">All Languages</MenuItem>
                  {LANGUAGES.map((lang) => (
                    <MenuItem key={lang} value={lang}>
                      {lang}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {hasFilters && (
                <Button onClick={handleSelectAll} variant="outlined" size="small">
                  Select All
                </Button>
              )}
            </Box>

            {/* Source Type Filters */}
            <Box sx={{ mt: 2, opacity: isFileMode ? 0.5 : 1 }}>
              <Typography
                variant="caption"
                sx={{ display: 'block', mb: 0.5, color: 'text.secondary' }}
              >
                Source Types:
                {isFileMode && (
                  <Typography
                    component="span"
                    variant="caption"
                    sx={{ ml: 1, fontStyle: 'italic' }}
                  >
                    (not applicable in File mode)
                  </Typography>
                )}
              </Typography>
              <FormGroup row>
                {SOURCE_TYPES.map((type) => (
                  <FormControlLabel
                    key={type.value}
                    control={
                      <Checkbox
                        checked={selectedSourceTypes.includes(type.value)}
                        onChange={() => handleSourceTypeToggle(type.value)}
                        size="small"
                        disabled={isFileMode}
                      />
                    }
                    label={type.label}
                    sx={{ cursor: isFileMode ? 'not-allowed' : 'pointer' }}
                  />
                ))}
              </FormGroup>
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
                          key={`${file.id}-${index}`}
                          disablePadding
                          divider={index < fileResults.length - 1}
                        >
                          <ListItemButton onClick={() => handleFileResultClick(file)}>
                            <ListItemText
                              primary={
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <InsertDriveFileIcon
                                    sx={{ fontSize: 18, color: 'text.secondary' }}
                                  />
                                  <Typography
                                    variant="body2"
                                    sx={{ fontFamily: 'monospace', fontWeight: 500 }}
                                  >
                                    {file.name}
                                  </Typography>
                                  {file.language && (
                                    <Chip label={file.language} size="small" variant="outlined" />
                                  )}
                                </Box>
                              }
                              secondary={
                                <Typography
                                  variant="body2"
                                  sx={{
                                    color: 'text.secondary',
                                    fontFamily: 'monospace',
                                    fontSize: '0.8rem',
                                  }}
                                >
                                  {file.repository_name} / {file.path}
                                </Typography>
                              }
                            />
                          </ListItemButton>
                        </ListItem>
                      ))
                    : results.map((result, index) => (
                        <ListItem
                          key={`${result.kind}-${result.data.id}-${index}`}
                          disablePadding
                          divider={index < results.length - 1}
                        >
                          <ListItemButton onClick={() => handleUnifiedResultClick(result)}>
                            <ListItemText
                              primary={
                                result.kind === 'symbol' ? (
                                  <Box
                                    sx={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: 1,
                                      mb: 0.5,
                                    }}
                                  >
                                    <Chip label="Symbol" size="small" color="primary" />
                                    <Chip
                                      label={result.data.kind}
                                      size="small"
                                      variant="outlined"
                                    />
                                    <Typography
                                      variant="body2"
                                      sx={{ fontFamily: 'monospace' }}
                                    >
                                      {repositories.find(
                                        (r) => r.id === result.data.repository_id
                                      )?.name || ''}
                                      {result.data.file_path &&
                                        ` / ${result.data.file_path}`}
                                      :{result.data.start_line}
                                    </Typography>
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
                                      color={getSourceTypeBadgeColor(
                                        result.data.source_type
                                      )}
                                    />
                                    <Typography
                                      variant="body2"
                                      sx={{ fontFamily: 'monospace' }}
                                    >
                                      {result.data.repository_name}
                                      {result.data.file_path &&
                                        ` / ${result.data.file_path}`}
                                      {result.data.source_line &&
                                        `:${result.data.source_line}`}
                                    </Typography>
                                    {result.data.language && (
                                      <Chip
                                        label={result.data.language}
                                        size="small"
                                        variant="outlined"
                                      />
                                    )}
                                  </Box>
                                )
                              }
                              secondary={
                                <Typography
                                  variant="body2"
                                  sx={{
                                    color: 'text.primary',
                                    fontFamily: 'monospace',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                  }}
                                >
                                  {result.kind === 'symbol'
                                    ? highlightMatches(
                                        result.data.signature ||
                                          result.data.qualified_name ||
                                          result.data.name,
                                        query,
                                        'keyword'
                                      )
                                    : highlightMatches(
                                        result.data.headline || result.data.content,
                                        query,
                                        mode
                                      )}
                                </Typography>
                              }
                            />
                          </ListItemButton>
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
                  : 'Enter a search query to find symbols, comments, docstrings, commit messages, and files'}
              </Typography>
            </Paper>
          )}
        </Box>
      </Box>
    </Box>
  )
}
