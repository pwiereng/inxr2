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
} from '@mui/material'
import CodeIcon from '@mui/icons-material/Code'
import FolderIcon from '@mui/icons-material/Folder'
import { getRepositories, type Repository } from '@/lib/api'

/**
 * Home page component
 * Displays repository cards that navigate to Browse view
 */
export function Home() {
  const navigate = useNavigate()
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadRepositories = async () => {
      try {
        const repos = await getRepositories()
        setRepositories(repos)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load repositories')
      } finally {
        setLoading(false)
      }
    }
    loadRepositories()
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
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, fontFamily: 'monospace' }}>
            inxr2 index full --config config.yaml
          </Typography>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          {repositories.map((repo) => (
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
                  </CardContent>
                </CardActionArea>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  )
}
