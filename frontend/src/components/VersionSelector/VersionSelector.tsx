import { useState, useEffect } from 'react'
import {
  FormControl,
  Select,
  MenuItem,
  Typography,
  Box,
  Tooltip,
  CircularProgress,
} from '@mui/material'
import HistoryIcon from '@mui/icons-material/History'
import EditIcon from '@mui/icons-material/Edit'
import { getCommits, getFileHistory, type CommitInfo } from '@/lib/api'
import { formatDateTimeUTC } from '@/lib/dateUtils'
import { MENU_PROPS } from '@/lib/menuProps'

interface VersionSelectorProps {
  repoName: string
  filePath: string
  selectedCommit: string | null
  onVersionChange: (commitHash: string | null) => void
  selectedBranch?: string | null
  /** When true, show EditIcon on commits that modified the file */
  showFileChanges?: boolean
  // Compact mode for inline use (e.g., diff right panel)
  compact?: boolean
}

export function VersionSelector({
  repoName,
  filePath,
  selectedCommit,
  onVersionChange,
  selectedBranch,
  showFileChanges = false,
  compact = false,
}: VersionSelectorProps): React.ReactElement | null {
  const [commits, setCommits] = useState<CommitInfo[]>([])
  const [fileChangeHashes, setFileChangeHashes] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true) // Start true to show loading until first fetch completes
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!repoName || !filePath) {
      setCommits([])
      setFileChangeHashes(new Set())
      setLoading(false)
      return
    }

    const loadData = async () => {
      setLoading(true)
      setError(null)
      try {
        const commitsResponse = await getCommits(repoName, selectedBranch || undefined, 500)
        // Backend returns newest-first; spread for immutability
        setCommits([...commitsResponse.commits])

        // Fetch file history separately so a 404 doesn't break the commit list
        if (showFileChanges) {
          try {
            const fileHistoryResponse = await getFileHistory(
              repoName,
              filePath,
              selectedBranch || undefined
            )
            setFileChangeHashes(new Set(fileHistoryResponse.versions.map((v) => v.commit_hash)))
          } catch {
            // File may not exist on this branch — degrade gracefully (no EditIcons)
            setFileChangeHashes(new Set())
          }
        } else {
          setFileChangeHashes(new Set())
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load commits')
        setCommits([])
        setFileChangeHashes(new Set())
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [repoName, filePath, selectedBranch, showFileChanges])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <CircularProgress size={16} />
      </Box>
    )
  }

  if (error || commits.length === 0) {
    return null
  }

  // If only one commit, show static display (no dropdown needed)
  if (commits.length === 1) {
    const singleCommit = commits[0]
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
        <HistoryIcon fontSize="small" />
        <Typography variant="caption">{singleCommit?.short_hash}</Typography>
      </Box>
    )
  }

  const latestHash = commits[0]?.hash
  // Precompute the first indexed commit hash for HEAD badge (avoids O(n²) in render loop)
  const headHash = commits.find((c) => c.is_indexed)?.hash

  // Always use the selected commit if provided - show what's actually being viewed
  const effectiveValue = selectedCommit || latestHash || ''

  return (
    <FormControl size="small">
      <Select
        value={effectiveValue}
        MenuProps={MENU_PROPS}
        onChange={(e) => {
          const value = e.target.value as string
          // Always pass the commit hash to include it in the URL
          onVersionChange(value || null)
        }}
        displayEmpty
        sx={{
          minWidth: compact ? 90 : 120,
          '& .MuiSelect-select': {
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            py: compact ? 0.25 : 0.5,
            px: compact ? 0.5 : undefined,
            fontSize: compact ? '0.75rem' : '0.875rem',
            fontFamily: 'monospace',
          },
          ...(compact && {
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: 'divider',
            },
          }),
        }}
      >
        {commits.map((commit) => {
          const hasChange = showFileChanges && fileChangeHashes.has(commit.hash)
          // Check if this commit is selected
          const isSelected =
            commit.hash === selectedCommit || (!selectedCommit && commit.hash === latestHash)

          return (
            <MenuItem
              key={commit.hash}
              value={commit.hash}
              sx={{
                bgcolor: isSelected ? 'action.selected' : 'transparent',
                borderLeft: commit.is_branch_specific ? 3 : isSelected ? 3 : 0,
                borderColor: commit.is_branch_specific ? 'info.main' : 'primary.main',
                '&.Mui-selected': {
                  bgcolor: 'action.selected',
                },
              }}
            >
              <Tooltip title={commit.message} placement="left">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {hasChange && <EditIcon sx={{ fontSize: '0.9rem', color: 'warning.main' }} />}
                  <Typography
                    component="span"
                    sx={{
                      fontFamily: 'monospace',
                      fontSize: '0.8rem',
                      fontWeight: isSelected ? 600 : 400,
                      color: isSelected ? 'primary.main' : 'text.primary',
                    }}
                  >
                    {commit.short_hash}
                  </Typography>
                  <Typography component="span" variant="caption" color="text.secondary">
                    {formatDateTimeUTC(commit.commit_date)}
                  </Typography>
                  {/* Show HEAD badge for the first indexed commit */}
                  {commit.hash === headHash && (
                    <Typography
                      component="span"
                      variant="caption"
                      sx={{
                        ml: 0.5,
                        px: 0.5,
                        py: 0.125,
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                        borderRadius: 0.5,
                        fontSize: '0.65rem',
                        fontWeight: 600,
                      }}
                    >
                      HEAD
                    </Typography>
                  )}
                  {/* Show FORK badge for merge-base commits */}
                  {commit.is_merge_base && (
                    <Typography
                      component="span"
                      variant="caption"
                      sx={{
                        ml: 0.5,
                        px: 0.5,
                        py: 0.125,
                        bgcolor: 'secondary.main',
                        color: 'secondary.contrastText',
                        borderRadius: 0.5,
                        fontSize: '0.65rem',
                        fontWeight: 600,
                      }}
                    >
                      FORK
                    </Typography>
                  )}
                </Box>
              </Tooltip>
            </MenuItem>
          )
        })}
      </Select>
    </FormControl>
  )
}
