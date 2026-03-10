import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  Box,
  ButtonBase,
  Container,
  Typography,
  List,
  ListItem,
  Paper,
  CircularProgress,
} from '@mui/material'
import { CodeHeader, type TabValue } from '@/components/CodeHeader'
import { getCommits, type CommitInfo } from '@/lib/api'
import { formatDateTimeUTC } from '@/lib/dateUtils'
import { CopyButton } from '@/components/CopyButton/CopyButton'
import { useSelectionToolbar } from '@/hooks/useSelectionToolbar'
import { SelectionToolbar } from '@/components/SelectionToolbar'

export function History(): React.ReactElement {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // Get state from URL
  const repoName = searchParams.get('repo')
  const branch = searchParams.get('branch')
  const commit = searchParams.get('commit')

  // Selection toolbar for copy + search
  const { toolbar, containerRef, handleClose } = useSelectionToolbar()

  // Local state
  const [commits, setCommits] = useState<CommitInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const focusedCommitRef = useRef<HTMLLIElement>(null)

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
        const response = await getCommits(repoName, branch || undefined, 1000)
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

  // Scroll to focused commit when commits load
  useEffect(() => {
    if (commit && commits.length > 0 && focusedCommitRef.current) {
      focusedCommitRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [commit, commits])

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

  const handleCommitClick = (commitInfo: CommitInfo) => {
    // Only navigate to browse for indexed commits (files are browseable)
    if (!commitInfo.is_indexed || !repoName) return

    const params = new URLSearchParams()
    if (branch) params.set('branch', branch)
    params.set('commit', commitInfo.hash)
    params.set('co', '1') // Show only changed files by default
    navigate(`/browse/${repoName}?${params.toString()}`)
  }

  // Format date for display (always UTC)
  const formatDate = (dateStr: string) => formatDateTimeUTC(dateStr)

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

      <Container maxWidth="lg" sx={{ flex: 1, py: 3, overflow: 'auto' }} ref={containerRef}>
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
            <List disablePadding>
              {commits.map((commitInfo, index) => {
                const isFocused = commit === commitInfo.hash
                const messageParts = commitInfo.message.split('\n')
                const summary = messageParts[0] || ''
                const body = messageParts.slice(1).join('\n').trim()
                return (
                  <ListItem
                    key={commitInfo.hash}
                    ref={isFocused ? focusedCommitRef : undefined}
                    divider={index < commits.length - 1}
                    sx={{
                      display: 'block',
                      py: 2,
                      px: 3,
                      userSelect: 'text',
                      ...(isFocused && {
                        bgcolor: 'action.selected',
                        borderLeft: 3,
                        borderColor: 'primary.main',
                      }),
                    }}
                  >
                    {/* Summary line */}
                    <Typography
                      sx={{
                        fontWeight: 600,
                        fontSize: '0.95rem',
                        mb: 0.5,
                      }}
                    >
                      {summary}
                    </Typography>

                    {/* Metadata: hash, author, date */}
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 2,
                        mb: body ? 1.5 : 0,
                      }}
                    >
                      {commitInfo.is_indexed ? (
                        <ButtonBase
                          onClick={() => handleCommitClick(commitInfo)}
                          sx={{
                            fontFamily: 'monospace',
                            fontSize: '0.8rem',
                            color: 'primary.main',
                            fontWeight: 500,
                            cursor: 'pointer',
                            '&:hover': { textDecoration: 'underline' },
                          }}
                        >
                          {commitInfo.short_hash}
                        </ButtonBase>
                      ) : (
                        <Typography
                          component="span"
                          sx={{
                            fontFamily: 'monospace',
                            fontSize: '0.8rem',
                            color: 'text.disabled',
                            fontWeight: 500,
                          }}
                        >
                          {commitInfo.short_hash}
                          <Typography
                            component="span"
                            sx={{ fontSize: '0.7rem', color: 'text.disabled', ml: 0.5 }}
                          >
                            (not indexed)
                          </Typography>
                        </Typography>
                      )}
                      <CopyButton
                        value={commitInfo.short_hash}
                        fullValue={commitInfo.hash}
                        tooltip="Copy commit hash"
                      />
                      <Typography component="span" variant="body2" color="text.secondary">
                        {commitInfo.author_name}
                      </Typography>
                      <Typography component="span" variant="body2" color="text.secondary">
                        {formatDate(commitInfo.commit_date)}
                      </Typography>
                    </Box>

                    {/* Full commit body */}
                    {body && (
                      <Typography
                        component="pre"
                        sx={{
                          fontFamily: 'inherit',
                          fontSize: '0.825rem',
                          color: 'text.secondary',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          m: 0,
                          pl: 0,
                          lineHeight: 1.6,
                        }}
                      >
                        {body}
                      </Typography>
                    )}
                  </ListItem>
                )
              })}
            </List>
          </Paper>
        )}
      </Container>
      <SelectionToolbar
        toolbar={toolbar}
        onCopy={() => {
          const text = toolbar?.selectedText
          if (text) navigator.clipboard?.writeText(text)
        }}
        onSearch={() => {
          const text = toolbar?.selectedText
          if (!text || !repoName) return
          const params = new URLSearchParams()
          params.set('repo', repoName)
          if (branch) params.set('branch', branch)
          if (commit) params.set('commit', commit)
          params.set('query', text)
          navigate(`/search?${params.toString()}`)
        }}
        onClose={handleClose}
      />
    </Box>
  )
}

export default History
