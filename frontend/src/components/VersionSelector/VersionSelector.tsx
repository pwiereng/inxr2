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

function formatCommitDate(dateString: string, allDates: string[]): string {
  const date = new Date(dateString)

  // Format as yyyymmdd in local timezone
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const dateStr = `${year}${month}${day}`

  // Check if there are other commits on the same day
  const sameDayCount = allDates.filter((d) => {
    const other = new Date(d)
    return (
      other.getFullYear() === date.getFullYear() &&
      other.getMonth() === date.getMonth() &&
      other.getDate() === date.getDate()
    )
  }).length

  // If multiple commits on same day, add time
  if (sameDayCount > 1) {
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${dateStr} ${hours}:${minutes}`
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

          return (
            <MenuItem key={version.commit_hash} value={version.commit_hash}>
              <Tooltip title={version.message} placement="left">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {hasChange && <EditIcon sx={{ fontSize: '0.9rem', color: 'warning.main' }} />}
                  <Typography component="span" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
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
