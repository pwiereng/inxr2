import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Container,
  Typography,
  Box,
  Paper,
  Card,
  CardContent,
  CardActionArea,
  CircularProgress,
  Alert,
  Chip,
} from '@mui/material'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import CodeIcon from '@mui/icons-material/Code'
import TimerIcon from '@mui/icons-material/Timer'
import { type RepositoryStats, getAllRepositoryStats } from '@/lib/api'
import { formatDateTimeUTC, formatDuration } from '@/lib/dateUtils'

export default function Repositories(): React.ReactElement {
  const [stats, setStats] = useState<RepositoryStats[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async (): Promise<void> => {
    try {
      const data = await getAllRepositoryStats()
      setStats(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
          <CircularProgress />
        </Box>
      </Container>
    )
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">Error: {error}</Alert>
      </Container>
    )
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Repositories
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Browse indexed code repositories
        </Typography>
      </Box>

      {stats.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" gutterBottom>
            No repositories indexed yet.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Use the API to index a local directory
          </Typography>
        </Paper>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {stats.map((repo) => (
            <Card key={repo.repository_id} elevation={1}>
              <CardActionArea component={Link} to={`/browse/${encodeURIComponent(repo.name)}`}>
                <CardContent>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <Box sx={{ flex: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <CodeIcon color="primary" />
                        <Typography variant="h6" component="h2">
                          {repo.name}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {repo.last_indexed_at != null && (
                          <Chip
                            size="small"
                            icon={<AccessTimeIcon />}
                            label={`Last indexed: ${formatDateTimeUTC(repo.last_indexed_at)}`}
                            variant="outlined"
                          />
                        )}
                        {repo.last_indexing_duration_seconds != null && (
                          <Chip
                            size="small"
                            icon={<TimerIcon />}
                            label={`Duration: ${formatDuration(repo.last_indexing_duration_seconds)}${repo.last_resolving_duration_seconds != null ? ` (resolve: ${formatDuration(repo.last_resolving_duration_seconds)})` : ''}`}
                            variant="outlined"
                          />
                        )}
                      </Box>
                    </Box>
                    <ChevronRightIcon color="action" />
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Box>
      )}
    </Container>
  )
}
