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

interface VersionSelectorProps {
  repoName: string
  filePath: string
  selectedCommit: string | null
  onVersionChange: (commitHash: string | null) => void
}

function parseAsUTC(dateString: string): Date {
  // If no timezone indicator, treat as UTC by appending Z
  if (!dateString.endsWith('Z') && !dateString.includes('+') && !dateString.includes('-', 10)) {
    return new Date(dateString + 'Z')
  }
  return new Date(dateString)
}

function formatCommitDate(dateString: string, allDates: string[]): string {
  // Parse as UTC since git commit dates are stored in UTC
  const date = parseAsUTC(dateString)

  // Format as yyyymmdd in UTC
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  const dateStr = `${year}${month}${day}`

  // Check if there are other commits on the same day (in UTC)
  const sameDayCount = allDates.filter((d) => {
    const other = parseAsUTC(d)
    return (
      other.getUTCFullYear() === date.getUTCFullYear() &&
      other.getUTCMonth() === date.getUTCMonth() &&
      other.getUTCDate() === date.getUTCDate()
    )
  }).length

  // If multiple commits on same day, add time with UTC indicator
  if (sameDayCount > 1) {
    const hours = String(date.getUTCHours()).padStart(2, '0')
    const minutes = String(date.getUTCMinutes()).padStart(2, '0')
    return `${dateStr} ${hours}:${minutes} UTC`
  }

  return dateStr
}

export function VersionSelector({
  repoName,
  filePath,
  selectedCommit,
  onVersionChange,
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
        const response = await getFileHistory(repoName, filePath)
        setVersions(response.versions)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load versions')
        setVersions([])
      } finally {
        setLoading(false)
      }
    }

    loadVersions()
  }, [repoName, filePath])

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

  return (
    <FormControl size="small">
      <Select
        value={selectedCommit || latestHash || ''}
        onChange={(e) => {
          const value = e.target.value as string
          // If selecting the latest version, set to null (default behavior)
          onVersionChange(value === latestHash ? null : value)
        }}
        displayEmpty
        sx={{
          minWidth: 180,
          '& .MuiSelect-select': {
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            py: 0.5,
            fontSize: '0.875rem',
          },
        }}
      >
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
                    {index === 0 && ' (latest)'}
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
