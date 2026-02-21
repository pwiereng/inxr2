import { useState, useEffect } from 'react'
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
} from '@mui/material'
import CodeIcon from '@mui/icons-material/Code'
import FolderIcon from '@mui/icons-material/Folder'
import {
  getRepositories,
  getAllRepositoryStats,
  type Repository,
  type RepositoryStats,
} from '@/lib/api'

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
 * Displays repository cards that navigate to Browse view
 */
export function Home() {
  const navigate = useNavigate()
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [statsMap, setStatsMap] = useState<Map<number, RepositoryStats>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
        // Stats failure is non-critical — cards still render without stats
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load repositories')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleRepoClick = (repo: Repository) => {
    // Navigate to browse with default branch
    const params = new URLSearchParams()
    if (repo.default_branch) {
      params.set('branch', repo.default_branch)
    }
    navigate(`/browse/${repo.name}?${params.toString()}`)
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 6, mb: 4, textAlign: 'center' }}>
        <CodeIcon sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
        <Typography variant="h3" component="h1" gutterBottom>
          INXR2
        </Typography>
        <Typography variant="h6" component="h2" color="text.secondary" gutterBottom>
          Cross-Reference Code Browser
        </Typography>
      </Box>

      <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 2 }}>
        Repositories
      </Typography>

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
        <Grid container spacing={3}>
          {repositories.map((repo) => {
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
                        </Box>
                      )}
                    </CardContent>
                  </CardActionArea>
                </Card>
              </Grid>
            )
          })}
        </Grid>
      )}
    </Container>
  )
}
