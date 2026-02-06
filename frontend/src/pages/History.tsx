import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  Box,
  Container,
  Typography,
  List,
  ListItem,
  ListItemText,
  Paper,
  CircularProgress,
} from '@mui/material'
import { CodeHeader, type TabValue } from '@/components/CodeHeader'
import { getCommits, type CommitInfo } from '@/lib/api'

export function History() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // Get state from URL
  const repoName = searchParams.get('repo')
  const branch = searchParams.get('branch')
  const commit = searchParams.get('commit')

  // Local state
  const [commits, setCommits] = useState<CommitInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load commits when repo/branch changes
  useEffect(() => {
    if (!repoName) {
      setCommits([])
      return
    }

    const loadCommits = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await getCommits(repoName, branch || undefined, 100)
        setCommits(response.commits)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load commits')
        setCommits([])
      } finally {
        setLoading(false)
      }
    }

    loadCommits()
  }, [repoName, branch])

  // Header handlers
  const handleRepoChange = (newRepo: string) => {
    navigate(`/history?repo=${newRepo}`)
  }

  const handleBranchChange = (newBranch: string) => {
    const params = new URLSearchParams()
    if (repoName) params.set('repo', repoName)
    params.set('branch', newBranch)
    navigate(`/history?${params.toString()}`)
  }

  const handleCommitChange = (newCommit: string) => {
    const params = new URLSearchParams()
    if (repoName) params.set('repo', repoName)
    if (branch) params.set('branch', branch)
    params.set('commit', newCommit)
    navigate(`/history?${params.toString()}`)
  }

  const handleTabChange = (tab: TabValue) => {
    const params = new URLSearchParams()
    if (repoName) params.set('repo', repoName)
    if (branch) params.set('branch', branch)
    if (commit) params.set('commit', commit)

    switch (tab) {
      case 'browse':
        navigate(`/browse/${repoName}?${params.toString()}`)
        break
      case 'search':
        navigate(`/search?${params.toString()}`)
        break
      case 'history':
        // Already on history
        break
    }
  }

  const handleCommitClick = (commitHash: string) => {
    // Navigate to browse at this commit with changedOnly=true by default
    // This shows only files changed in that commit, which is typically what
    // users want when exploring a specific commit from history
    if (repoName) {
      const params = new URLSearchParams()
      if (branch) params.set('branch', branch)
      params.set('commit', commitHash)
      params.set('co', '1') // Show only changed files by default
      navigate(`/browse/${repoName}?${params.toString()}`)
    }
  }

  // Format date for display
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <CodeHeader
        currentTab="history"
        repoName={repoName}
        branch={branch}
        commit={commit}
        onRepoChange={handleRepoChange}
        onBranchChange={handleBranchChange}
        onCommitChange={handleCommitChange}
        onTabChange={handleTabChange}
      />

      <Container maxWidth="lg" sx={{ flex: 1, py: 3, overflow: 'auto' }}>
        {!repoName ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h6" color="text.secondary">
              Select a repository to view commit history
            </Typography>
          </Paper>
        ) : loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="error">{error}</Typography>
          </Paper>
        ) : commits.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">No commits found</Typography>
          </Paper>
        ) : (
          <Paper>
            <List>
              {commits.map((commitInfo, index) => (
                <ListItem
                  key={commitInfo.hash}
                  divider={index < commits.length - 1}
                  sx={{
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                  onClick={() => handleCommitClick(commitInfo.hash)}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Typography
                          component="span"
                          sx={{
                            fontFamily: 'monospace',
                            fontSize: '0.875rem',
                            color: 'primary.main',
                            fontWeight: 500,
                          }}
                        >
                          {commitInfo.short_hash}
                        </Typography>
                        <Typography
                          component="span"
                          sx={{
                            flex: 1,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {commitInfo.message}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 2,
                          mt: 0.5,
                        }}
                      >
                        <Typography component="span" variant="body2" color="text.secondary">
                          {commitInfo.author_name}
                        </Typography>
                        <Typography component="span" variant="body2" color="text.secondary">
                          {formatDate(commitInfo.commit_date)}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        )}
      </Container>
    </Box>
  )
}

export default History
