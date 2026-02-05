import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
  AppBar,
  Toolbar,
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
  Breadcrumbs,
  Link,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import HomeIcon from '@mui/icons-material/Home'

import {
  searchText,
  getRepositories,
  type TextSearchParams,
  type TextSearchResult,
  type Repository,
} from '@/lib/api'

// Source type options
const SOURCE_TYPES = [
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

const RESULTS_PER_PAGE = 20

interface SearchProps {
  /** If true, renders without AppBar (for use in tabs) */
  noAppBar?: boolean
  /** Repository name to filter by (for tab mode) */
  repoName?: string
}

export default function Search({ noAppBar = false, repoName }: SearchProps) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // State from URL
  const query = searchParams.get('q') || ''
  const mode = (searchParams.get('mode') as 'keyword' | 'phrase' | 'regex') || 'keyword'
  const branch = searchParams.get('branch') || undefined
  // In standalone mode, repo param is an ID; in tab mode, it comes from repoName prop
  const repoParam = searchParams.get('repo')
  const parsedRepo = noAppBar ? undefined : (repoParam ? parseInt(repoParam) : undefined)
  // Handle case where repo param is a name (not a number) - just ignore it for filtering
  const standaloneSelectedRepo = Number.isNaN(parsedRepo) ? undefined : parsedRepo
  const page = parseInt(searchParams.get('page') || '1')
  const offset = (page - 1) * RESULTS_PER_PAGE

  // Parse array params
  const sourceTypesParam = searchParams.get('source_types')
  const languagesParam = searchParams.get('languages')
  const selectedSourceTypes = sourceTypesParam ? sourceTypesParam.split(',') : []
  const selectedLanguages = languagesParam ? languagesParam.split(',') : []
  const sourceTypesKey = selectedSourceTypes.join(',')
  const languagesKey = selectedLanguages.join(',')

  // Local state for input (debouncing)
  const [inputQuery, setInputQuery] = useState(query)

  // Data state
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [results, setResults] = useState<TextSearchResult[]>([])
  const [totalResults, setTotalResults] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // In tab mode, look up repo ID from repoName prop; in standalone mode, use URL param
  const repoFromName = repoName ? repositories.find((r) => r.name === repoName)?.id : undefined
  const validSelectedRepo = noAppBar ? repoFromName : standaloneSelectedRepo

  // Debounce search - update URL after delay
  useEffect(() => {
    if (!inputQuery.trim()) return

    const timer = setTimeout(() => {
      const newParams = new URLSearchParams(searchParams)
      newParams.set('q', inputQuery)
      newParams.delete('page') // Reset to page 1 on new search
      setSearchParams(newParams)
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
      setTotalResults(0)
      return
    }

    const performSearch = async () => {
      setLoading(true)
      setError(null)

      try {
        const params: TextSearchParams = {
          q: query,
          mode,
          repo: validSelectedRepo,
          branch,
          source_types: selectedSourceTypes.length > 0 ? selectedSourceTypes : undefined,
          languages: selectedLanguages.length > 0 ? selectedLanguages : undefined,
          limit: RESULTS_PER_PAGE,
          offset,
        }

        const response = await searchText(params)
        setResults(response.results)
        setTotalResults(response.total)
      } catch (err) {
        console.error('Search failed:', err)
        setError(err instanceof Error ? err.message : 'Search failed')
        setResults([])
        setTotalResults(0)
      } finally {
        setLoading(false)
      }
    }

    performSearch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, mode, validSelectedRepo, repoName, branch, sourceTypesKey, languagesKey, offset])

  // Handlers
  const handleModeChange = (newMode: string) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('mode', newMode)
    newParams.delete('page')
    setSearchParams(newParams)
  }

  const handleRepoChange = (repoId: string) => {
    const newParams = new URLSearchParams(searchParams)
    if (repoId) {
      newParams.set('repo', repoId)
    } else {
      newParams.delete('repo')
    }
    newParams.delete('page')
    setSearchParams(newParams)
  }

  const handleSourceTypeToggle = (type: string) => {
    const newParams = new URLSearchParams(searchParams)
    const current = selectedSourceTypes
    const updated = current.includes(type) ? current.filter((t) => t !== type) : [...current, type]

    if (updated.length > 0) {
      newParams.set('source_types', updated.join(','))
    } else {
      newParams.delete('source_types')
    }
    newParams.delete('page')
    setSearchParams(newParams)
  }

  const handleLanguageChange = (lang: string) => {
    const newParams = new URLSearchParams(searchParams)
    if (lang) {
      newParams.set('languages', lang)
    } else {
      newParams.delete('languages')
    }
    newParams.delete('page')
    setSearchParams(newParams)
  }

  const handlePageChange = (_event: React.ChangeEvent<unknown>, value: number) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('page', value.toString())
    setSearchParams(newParams)
    // Scroll to top of results
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleResultClick = (result: TextSearchResult) => {
    // Navigate to Browse tab with the result's location
    const repoName = result.repository_name
    const filePath = result.file_path

    if (!filePath) {
      // Commit message - navigate to repository
      if (noAppBar) {
        // In tab mode, switch to browse tab
        const params = new URLSearchParams()
        params.set('tab', 'browse')
        params.set('repo', repoName)
        navigate(`?${params}`)
      } else {
        navigate(`/browse/${encodeURIComponent(repoName)}`)
      }
      return
    }

    // Build URL with file, line, and commit
    const params = new URLSearchParams()
    if (noAppBar) {
      params.set('tab', 'browse')
      params.set('repo', repoName)
    }
    params.set('file', filePath)
    if (result.source_line) {
      params.set('line', result.source_line.toString())
    }
    if (result.commit_hash) {
      params.set('commit', result.commit_hash)
    }
    if (result.branch) {
      params.set('branch', result.branch)
    }

    if (noAppBar) {
      // In tab mode, stay on same page but switch to browse tab
      navigate(`?${params}`)
    } else {
      navigate(`/browse/${encodeURIComponent(repoName)}?${params}`)
    }
  }

  const handleClearFilters = () => {
    const newParams = new URLSearchParams()
    if (query) newParams.set('q', query)
    if (mode !== 'keyword') newParams.set('mode', mode)
    setSearchParams(newParams)
  }

  const getSourceTypeBadgeColor = (
    sourceType: string
  ): 'default' | 'primary' | 'secondary' | 'info' | 'success' => {
    switch (sourceType) {
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
  const hasFilters =
    validSelectedRepo || branch || selectedSourceTypes.length > 0 || selectedLanguages.length > 0

  const appBarContent = !noAppBar && (
    <AppBar
      position="static"
      sx={{
        bgcolor: 'background.paper',
        borderBottom: 1,
        borderColor: 'divider',
      }}
      elevation={0}
    >
      <Toolbar sx={{ gap: 2 }}>
        <SearchIcon color="primary" />
        <Breadcrumbs sx={{ flex: 1 }}>
          <Link
            href="/"
            underline="hover"
            color="inherit"
            sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
          >
            <HomeIcon fontSize="small" />
            Home
          </Link>
          <Typography color="text.primary">Search</Typography>
        </Breadcrumbs>
      </Toolbar>
    </AppBar>
  )

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: noAppBar ? '100%' : '100vh' }}>
      {appBarContent}

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
                  <MenuItem value="keyword">Keyword</MenuItem>
                  <MenuItem value="phrase">Phrase</MenuItem>
                  <MenuItem value="regex">Regex</MenuItem>
                </Select>
              </FormControl>
            </Box>

            {/* Filters */}
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              {/* Only show repo selector in standalone mode - CodeExplorer provides its own */}
              {!noAppBar && repositories.length > 1 && (
                <FormControl sx={{ minWidth: 200 }}>
                  <InputLabel>Repository</InputLabel>
                  <Select
                    value={validSelectedRepo?.toString() || ''}
                    label="Repository"
                    onChange={(e) => handleRepoChange(e.target.value)}
                  >
                    <MenuItem value="">All Repositories</MenuItem>
                    {repositories.map((repo) => (
                      <MenuItem key={repo.id} value={repo.id.toString()}>
                        {repo.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}

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
                <Button onClick={handleClearFilters} variant="outlined" size="small">
                  Clear Filters
                </Button>
              )}
            </Box>

            {/* Source Type Filters */}
            <Box sx={{ mt: 2 }}>
              <Typography
                variant="caption"
                sx={{ display: 'block', mb: 0.5, color: 'text.secondary' }}
              >
                Source Types:
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
                      />
                    }
                    label={type.label}
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
          ) : query.trim() && results.length === 0 ? (
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
                  Found {totalResults.toLocaleString()} result{totalResults !== 1 ? 's' : ''}
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
                  {results.map((result, index) => (
                    <ListItem
                      key={`${result.id}-${index}`}
                      disablePadding
                      divider={index < results.length - 1}
                    >
                      <ListItemButton onClick={() => handleResultClick(result)}>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                              <Chip
                                label={formatSourceType(result.source_type)}
                                size="small"
                                color={getSourceTypeBadgeColor(result.source_type)}
                              />
                              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                {result.repository_name}
                                {result.file_path && ` / ${result.file_path}`}
                                {result.source_line && `:${result.source_line}`}
                              </Typography>
                              {result.language && (
                                <Chip label={result.language} size="small" variant="outlined" />
                              )}
                            </Box>
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
                              {result.headline || result.content}
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
              <SearchIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
              <Typography color="text.secondary">
                Enter a search query to find text in comments, docstrings, commit messages, and
                files
              </Typography>
            </Paper>
          )}
        </Box>
      </Box>
    </Box>
  )
}
