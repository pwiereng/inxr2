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
import { formatDateTimeUTC } from '@/lib/dateUtils'
import { MENU_PROPS } from '@/lib/menuProps'

interface VersionSelectorProps {
  repoName: string
  filePath: string
  selectedCommit: string | null
  onVersionChange: (commitHash: string | null) => void
  selectedBranch?: string | null
  // Compact mode for inline use (e.g., diff right panel)
  compact?: boolean
}

export function VersionSelector({
  repoName,
  filePath,
  selectedCommit,
  onVersionChange,
  selectedBranch,
  compact = false,
}: VersionSelectorProps) {
  const [versions, setVersions] = useState<FileVersion[]>([])
  const [loading, setLoading] = useState(true) // Start true to show loading until first fetch completes
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!repoName || !filePath) {
      setVersions([])
      setLoading(false)
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

  // If only one version, show static display (no dropdown needed)
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
                    {formatDateTimeUTC(version.commit_date)}
                  </Typography>
                  {/* Show HEAD badge for the latest commit */}
                  {index === 0 && (
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
                </Box>
              </Tooltip>
            </MenuItem>
          )
        })}
      </Select>
    </FormControl>
  )
}
