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
import { getFileHistory, type FileVersion } from '@/lib/api'
import { formatCommitDate } from '@/lib/dateUtils'

interface VersionSelectorProps {
  repoName: string
  filePath: string
  selectedCommit: string | null
  onVersionChange: (commitHash: string | null) => void
  selectedBranch?: string | null
  defaultBranch?: string | null
}

export function VersionSelector({
  repoName,
  filePath,
  selectedCommit,
  onVersionChange,
  selectedBranch,
  defaultBranch,
}: VersionSelectorProps) {
  const [versions, setVersions] = useState<FileVersion[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!repoName || !filePath) {
      setVersions([])
      return
    }

    const loadVersions = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await getFileHistory(repoName, filePath, selectedBranch || undefined)
        setVersions(response.versions)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load versions')
        setVersions([])
      } finally {
        setLoading(false)
      }
    }

    loadVersions()
  }, [repoName, filePath, selectedBranch])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <CircularProgress size={16} />
      </Box>
    )
  }

  if (error || versions.length === 0) {
    return null
  }

  // If only one version, don't show the selector
  if (versions.length === 1) {
    const singleVersion = versions[0]
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
        <HistoryIcon fontSize="small" />
        <Typography variant="caption">{singleVersion?.short_hash}</Typography>
      </Box>
    )
  }

  const latestHash = versions[0]?.commit_hash
  const allDates = versions.map((v) => v.commit_date)

  // Check if selectedCommit exists in the versions list
  const selectedExists = selectedCommit
    ? versions.some((v) => v.commit_hash === selectedCommit)
    : true

  // Always use the selected commit if provided - show what's actually being viewed
  const effectiveValue = selectedCommit || latestHash || ''

  return (
    <FormControl size="small">
      <Select
        value={effectiveValue}
        onChange={(e) => {
          const value = e.target.value as string
          // Always pass the commit hash to include it in the URL
          onVersionChange(value || null)
        }}
        displayEmpty
        sx={{
          minWidth: 120,
          '& .MuiSelect-select': {
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            py: 0.5,
            fontSize: '0.875rem',
          },
        }}
      >
        {/* Show selected commit if it's not in the versions list (file unchanged at that commit) */}
        {!selectedExists && selectedCommit && (
          <MenuItem
            key={selectedCommit}
            value={selectedCommit}
            sx={{
              bgcolor: 'action.selected',
              borderLeft: 3,
              borderColor: 'primary.main',
              '&.Mui-selected': {
                bgcolor: 'action.selected',
              },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography
                component="span"
                sx={{
                  fontFamily: 'monospace',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  color: 'primary.main',
                }}
              >
                {selectedCommit.substring(0, 7)}
              </Typography>
              <Typography component="span" variant="caption" color="text.secondary">
                (unchanged)
              </Typography>
            </Box>
          </MenuItem>
        )}
        {versions.map((version, index) => {
          // Check if content changed from previous version (next in array since sorted newest first)
          const prevVersion = versions[index + 1]
          const hasChange = !prevVersion || version.content_hash !== prevVersion.content_hash
          // Check if this version is selected
          const isSelected =
            version.commit_hash === selectedCommit ||
            (!selectedCommit && version.commit_hash === latestHash)

          return (
            <MenuItem
              key={version.commit_hash}
              value={version.commit_hash}
              sx={{
                bgcolor: isSelected ? 'action.selected' : 'transparent',
                borderLeft: isSelected ? 3 : 0,
                borderColor: 'primary.main',
                '&.Mui-selected': {
                  bgcolor: 'action.selected',
                },
              }}
            >
              <Tooltip title={version.message} placement="left">
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
                    {version.short_hash}
                  </Typography>
                  <Typography component="span" variant="caption" color="text.secondary">
                    {formatCommitDate(version.commit_date, allDates)}
                    {/* Only show "(latest)" for head of default branch */}
                    {index === 0 &&
                      (!selectedBranch || selectedBranch === defaultBranch) &&
                      ' (latest)'}
                  </Typography>
                </Box>
              </Tooltip>
            </MenuItem>
          )
        })}
      </Select>
    </FormControl>
  )
}
