import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Typography,
  Box,
  Paper,
  Grid,
  CircularProgress,
  Card,
  CardContent,
  CardActionArea,
  Chip,
  Tooltip,
  TextField,
  InputAdornment,
  IconButton,
} from '@mui/material'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import FolderIcon from '@mui/icons-material/Folder'
import SearchIcon from '@mui/icons-material/Search'
import TimerIcon from '@mui/icons-material/Timer'
import ViewListIcon from '@mui/icons-material/ViewList'
import ViewModuleIcon from '@mui/icons-material/ViewModule'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import { useApp } from '@/contexts/AppContext'
import {
  getRepositories,
  getAllRepositoryStats,
  type Repository,
  type RepositoryStats,
} from '@/lib/api'
import { formatDateTimeUTC, formatDuration } from '@/lib/dateUtils'
import logoLight from '@/assets/logo-light.svg'
import logoDark from '@/assets/logo-dark-v4.svg'

type ViewMode = 'grid' | 'list'

const VIEW_MODE_KEY = 'inxr2-home-view-mode'

function getStoredViewMode(): ViewMode {
  const stored = localStorage.getItem(VIEW_MODE_KEY)
  return stored === 'list' ? 'list' : 'grid'
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Home page component
 * Displays repositories in grid or list view with filtering
 */
export function Home(): React.ReactElement {
  const navigate = useNavigate()
  const { themeMode } = useApp()
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [statsMap, setStatsMap] = useState<Map<number, RepositoryStats>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>(getStoredViewMode)

  useEffect(() => {
    const load = async () => {
      try {
        const [repos, statsResult] = await Promise.allSettled([
          getRepositories(),
          getAllRepositoryStats(),
        ])

        if (repos.status === 'fulfilled') {
          setRepositories(repos.value)
        } else {
          throw repos.reason
        }

        if (statsResult.status === 'fulfilled') {
          const map = new Map<number, RepositoryStats>()
          for (const s of statsResult.value) {
            map.set(s.repository_id, s)
          }
          setStatsMap(map)
        }
        // Stats failure is non-critical — items still render without stats
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load repositories')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filteredRepositories = useMemo(() => {
    if (!filter.trim()) return repositories
    const q = filter.trim().toLowerCase()
    return repositories.filter((r) => r.name.toLowerCase().includes(q))
  }, [repositories, filter])

  const handleRepoClick = (repo: Repository) => {
    const params = new URLSearchParams()
    if (repo.default_branch) {
      params.set('branch', repo.default_branch)
    }
    navigate(`/browse/${repo.name}?${params.toString()}`)
  }

  const handleViewModeToggle = () => {
    const next = viewMode === 'grid' ? 'list' : 'grid'
    setViewMode(next)
    localStorage.setItem(VIEW_MODE_KEY, next)
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 6, mb: 4, textAlign: 'center' }}>
        <a href="https://github.com/pwiereng/inxr2" target="_blank" rel="noopener noreferrer">
          <Box
            component="img"
            src={themeMode === 'dark' ? logoDark : logoLight}
            alt="INXR2"
            sx={{ width: 128, height: 128, mb: 2 }}
          />
        </a>
        <Typography variant="h3" component="h1" gutterBottom>
          INXR<sup>2</sup>
        </Typography>
        <Typography variant="h6" component="h2" color="text.secondary" gutterBottom>
          Cross-Reference Code Browser
        </Typography>
      </Box>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mt: 4,
          mb: 2,
        }}
      >
        <Typography variant="h5">Repositories</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {!loading && !error && repositories.length > 0 && (
            <Typography variant="body2" color="text.secondary">
              {filter.trim()
                ? `Showing ${filteredRepositories.length} of ${repositories.length} repositories`
                : `${repositories.length} ${repositories.length === 1 ? 'repository' : 'repositories'}`}
            </Typography>
          )}
          {!loading && !error && repositories.length > 0 && (
            <Tooltip title={viewMode === 'grid' ? 'Switch to list view' : 'Switch to grid view'}>
              <IconButton
                onClick={handleViewModeToggle}
                size="small"
                aria-label={viewMode === 'grid' ? 'Switch to list view' : 'Switch to grid view'}
              >
                {viewMode === 'grid' ? <ViewListIcon /> : <ViewModuleIcon />}
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="error">{error}</Typography>
        </Paper>
      ) : repositories.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            No repositories indexed yet. Use the CLI to index a repository.
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mt: 2, fontFamily: 'monospace' }}
          >
            inxr2 index full --config config.yaml
          </Typography>
        </Paper>
      ) : (
        <>
          <TextField
            fullWidth
            size="small"
            placeholder="Filter repositories..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon color="action" />
                </InputAdornment>
              ),
            }}
            sx={{ mb: 2 }}
            data-testid="repo-filter"
          />
          {filteredRepositories.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="text.secondary">
                No repositories match &ldquo;{filter}&rdquo;
              </Typography>
            </Paper>
          ) : viewMode === 'grid' ? (
            <Grid container spacing={3}>
              {filteredRepositories.map((repo) => {
                const stats = statsMap.get(repo.id)
                return (
                  <Grid item xs={12} sm={6} md={4} key={repo.id}>
                    <Card
                      sx={{
                        height: '100%',
                        '&:hover': {
                          boxShadow: 6,
                        },
                      }}
                    >
                      <CardActionArea
                        onClick={() => handleRepoClick(repo)}
                        sx={{ height: '100%', display: 'flex', alignItems: 'flex-start' }}
                      >
                        <CardContent sx={{ width: '100%' }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <FolderIcon color="primary" />
                            <Typography variant="h6" component="div">
                              {repo.name}
                            </Typography>
                          </Box>
                          {repo.description && (
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                              }}
                            >
                              {repo.description}
                            </Typography>
                          )}
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ display: 'block', mt: 1 }}
                          >
                            Default branch: {repo.default_branch || 'main'}
                          </Typography>

                          {stats && (
                            <Box
                              sx={{ mt: 1.5, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}
                              data-testid="repo-stats"
                            >
                              {stats.is_stale && (
                                <Tooltip
                                  title={`Last indexed: ${stats.last_indexed_at ? formatDate(stats.last_indexed_at) : 'unknown'}. Run \`inxr2 index\` to update.`}
                                >
                                  <Chip
                                    icon={<WarningAmberIcon />}
                                    label="Index outdated"
                                    size="small"
                                    color="warning"
                                  />
                                </Tooltip>
                              )}
                              <Chip
                                label={`${formatNumber(stats.total_lines)} lines`}
                                size="small"
                                variant="outlined"
                              />
                              <Chip
                                label={`${formatNumber(stats.total_files)} files`}
                                size="small"
                                variant="outlined"
                              />
                              <Chip
                                label={`${formatNumber(stats.total_symbols)} symbols`}
                                size="small"
                                variant="outlined"
                              />
                              {stats.total_references > 0 && (
                                <Chip
                                  label={`${Math.round((stats.total_references_resolved / stats.total_references) * 100)}% resolved`}
                                  size="small"
                                  variant="outlined"
                                  color={
                                    stats.total_references_resolved / stats.total_references >= 0.8
                                      ? 'success'
                                      : 'warning'
                                  }
                                />
                              )}
                              {Object.entries(stats.languages)
                                .filter(([lang]) => lang !== 'unknown')
                                .sort((a, b) => b[1] - a[1])
                                .slice(0, 3)
                                .map(([lang]) => (
                                  <Chip
                                    key={lang}
                                    label={lang}
                                    size="small"
                                    variant="outlined"
                                    color="info"
                                  />
                                ))}
                              {stats.commit_date_earliest && stats.commit_date_latest && (
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                  sx={{ width: '100%', mt: 0.5 }}
                                >
                                  Commits: {formatDate(stats.commit_date_earliest)} &ndash;{' '}
                                  {formatDate(stats.commit_date_latest)}
                                </Typography>
                              )}
                              {stats.last_indexed_at != null && (
                                <Chip
                                  icon={<AccessTimeIcon />}
                                  label={`Last indexed: ${formatDateTimeUTC(stats.last_indexed_at)}`}
                                  size="small"
                                  variant="outlined"
                                />
                              )}
                              {stats.last_indexing_duration_seconds != null && (
                                <Chip
                                  icon={<TimerIcon />}
                                  label={`Duration: ${formatDuration(stats.last_indexing_duration_seconds)}${stats.last_resolving_duration_seconds != null ? ` (resolve: ${formatDuration(stats.last_resolving_duration_seconds)})` : ''}`}
                                  size="small"
                                  variant="outlined"
                                />
                              )}
                            </Box>
                          )}
                        </CardContent>
                      </CardActionArea>
                    </Card>
                  </Grid>
                )
              })}
            </Grid>
          ) : (
            <Paper variant="outlined">
              {filteredRepositories.map((repo, index) => {
                const stats = statsMap.get(repo.id)
                return (
                  <Box
                    key={repo.id}
                    onClick={() => handleRepoClick(repo)}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      px: 2,
                      py: 1.5,
                      cursor: 'pointer',
                      borderBottom: index < filteredRepositories.length - 1 ? '1px solid' : 'none',
                      borderColor: 'divider',
                      '&:hover': {
                        bgcolor: 'action.hover',
                      },
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        handleRepoClick(repo)
                      }
                    }}
                  >
                    <FolderIcon color="primary" sx={{ flexShrink: 0 }} />
                    <Box sx={{ minWidth: 0, flex: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                          {repo.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {repo.default_branch || 'main'}
                        </Typography>
                        {stats?.is_stale && (
                          <Tooltip
                            title={`Last indexed: ${stats.last_indexed_at ? formatDate(stats.last_indexed_at) : 'unknown'}. Run \`inxr2 index\` to update.`}
                          >
                            <Chip
                              icon={<WarningAmberIcon />}
                              label="Index outdated"
                              size="small"
                              color="warning"
                            />
                          </Tooltip>
                        )}
                      </Box>
                      {repo.description && (
                        <Typography variant="body2" color="text.secondary" noWrap>
                          {repo.description}
                        </Typography>
                      )}
                    </Box>
                    {stats && (
                      <Box
                        sx={{
                          display: 'flex',
                          gap: 0.5,
                          flexShrink: 0,
                          flexWrap: 'wrap',
                          justifyContent: 'flex-end',
                          maxWidth: 400,
                        }}
                        data-testid="repo-stats"
                      >
                        <Chip
                          label={`${formatNumber(stats.total_files)} files`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          label={`${formatNumber(stats.total_symbols)} symbols`}
                          size="small"
                          variant="outlined"
                        />
                        {stats.total_references > 0 && (
                          <Chip
                            label={`${Math.round((stats.total_references_resolved / stats.total_references) * 100)}% resolved`}
                            size="small"
                            variant="outlined"
                            color={
                              stats.total_references_resolved / stats.total_references >= 0.8
                                ? 'success'
                                : 'warning'
                            }
                          />
                        )}
                        {Object.entries(stats.languages)
                          .filter(([lang]) => lang !== 'unknown')
                          .sort((a, b) => b[1] - a[1])
                          .slice(0, 3)
                          .map(([lang]) => (
                            <Chip
                              key={lang}
                              label={lang}
                              size="small"
                              variant="outlined"
                              color="info"
                            />
                          ))}
                        {stats.last_indexed_at != null && (
                          <Chip
                            icon={<AccessTimeIcon />}
                            label={`Last indexed: ${formatDateTimeUTC(stats.last_indexed_at)}`}
                            size="small"
                            variant="outlined"
                          />
                        )}
                        {stats.last_indexing_duration_seconds != null && (
                          <Chip
                            icon={<TimerIcon />}
                            label={`Duration: ${formatDuration(stats.last_indexing_duration_seconds)}${stats.last_resolving_duration_seconds != null ? ` (resolve: ${formatDuration(stats.last_resolving_duration_seconds)})` : ''}`}
                            size="small"
                            variant="outlined"
                          />
                        )}
                      </Box>
                    )}
                  </Box>
                )
              })}
            </Paper>
          )}
        </>
      )}
    </Container>
  )
}
