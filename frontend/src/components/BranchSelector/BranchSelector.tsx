import { useState, useEffect } from 'react'
import {
  FormControl,
  Select,
  MenuItem,
  Typography,
  Box,
  CircularProgress,
  Tooltip,
  Chip,
} from '@mui/material'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import { getRepositoryBranches, type BranchInfo } from '@/lib/api'

interface BranchSelectorProps {
  repositoryId: number
  selectedBranch: string | null
  defaultBranch: string
  onBranchChange: (branchName: string | null) => void
}

export function BranchSelector({
  repositoryId,
  selectedBranch,
  defaultBranch,
  onBranchChange,
}: BranchSelectorProps) {
  const [branches, setBranches] = useState<BranchInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!repositoryId) {
      setBranches([])
      return
    }

    const loadBranches = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await getRepositoryBranches(repositoryId)
        // Only show indexed branches (those with commit_count > 0)
        const indexedBranches = response.branches.filter(
          (b) => b.commit_count && b.commit_count > 0
        )
        setBranches(indexedBranches)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load branches')
        setBranches([])
      } finally {
        setLoading(false)
      }
    }

    loadBranches()
  }, [repositoryId])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <CircularProgress size={16} />
      </Box>
    )
  }

  if (error || branches.length === 0) {
    return null
  }

  // If only one branch, show as plain text
  if (branches.length === 1) {
    const singleBranch = branches[0]
    const isIndexed = singleBranch?.commit_count && singleBranch.commit_count > 0
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
        <AccountTreeIcon fontSize="small" />
        <Typography variant="caption">{singleBranch?.name}</Typography>
        {isIndexed && (
          <Tooltip title="Branch is indexed">
            <CheckCircleIcon sx={{ fontSize: '0.9rem', color: 'success.main' }} />
          </Tooltip>
        )}
      </Box>
    )
  }

  // Determine the currently selected value
  // If selectedBranch isn't in the indexed branches, fall back to defaultBranch
  const selectedExists = branches.some((b) => b.name === selectedBranch)
  const currentValue = selectedExists ? (selectedBranch || defaultBranch) : defaultBranch

  return (
    <FormControl size="small">
      <Select
        value={currentValue}
        onChange={(e) => {
          const value = e.target.value as string
          // Always pass the branch name for URL bookmarkability
          onBranchChange(value || null)
        }}
        displayEmpty
        sx={{
          minWidth: 100,
          '& .MuiSelect-select': {
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            py: 0.5,
            fontSize: '0.875rem',
          },
        }}
        renderValue={(selected) => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <AccountTreeIcon fontSize="small" sx={{ color: 'text.secondary' }} />
            <Typography variant="body2">{selected}</Typography>
          </Box>
        )}
      >
        {branches.map((branch) => {
          const isSelected = branch.name === currentValue
          const isDefault = branch.name === defaultBranch

          return (
            <MenuItem
              key={branch.name}
              value={branch.name}
              sx={{
                bgcolor: isSelected ? 'action.selected' : 'transparent',
                borderLeft: isSelected ? 3 : 0,
                borderColor: 'primary.main',
                '&.Mui-selected': {
                  bgcolor: 'action.selected',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                <Typography
                  component="span"
                  sx={{
                    flex: 1,
                    fontWeight: isSelected ? 600 : 400,
                    color: isSelected ? 'primary.main' : 'text.primary',
                  }}
                >
                  {branch.name}
                </Typography>
                {isDefault && (
                  <Chip label="default" size="small" sx={{ height: 18, fontSize: '0.7rem' }} />
                )}
                <Tooltip title={`${branch.commit_count} commits indexed`}>
                  <CheckCircleIcon sx={{ fontSize: '1rem', color: 'success.main' }} />
                </Tooltip>
              </Box>
            </MenuItem>
          )
        })}
      </Select>
    </FormControl>
  )
}
