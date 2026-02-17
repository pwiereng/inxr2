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
import EditIcon from '@mui/icons-material/Edit'
import { getRepositoryBranches, getFileHistory, type BranchInfo } from '@/lib/api'

interface BranchSelectorProps {
  repositoryId: number
  selectedBranch: string | null
  defaultBranch: string
  onBranchChange: (branchName: string | null) => void
  // Optional: when provided, indicators show file status per branch
  repoName?: string
  filePath?: string
  // Compact mode for inline use (e.g., diff right panel)
  compact?: boolean
}

export function BranchSelector({
  repositoryId,
  selectedBranch,
  defaultBranch,
  onBranchChange,
  repoName,
  filePath,
  compact = false,
}: BranchSelectorProps) {
  const [branches, setBranches] = useState<BranchInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Track which branches have the file (for checkmark)
  const [branchesWithFile, setBranchesWithFile] = useState<Set<string>>(new Set())
  // Track which branches have changes to the file (different content than default branch)
  const [branchesWithChanges, setBranchesWithChanges] = useState<Set<string>>(new Set())

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
        // Only show indexed branches (those with a last_indexed_commit)
        const indexedBranches = response.branches.filter((b) => b.last_indexed_commit)
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

  // Check which branches have the file and which have changes
  useEffect(() => {
    if (!repoName || !filePath || branches.length === 0) {
      setBranchesWithFile(new Set())
      setBranchesWithChanges(new Set())
      return
    }

    const checkBranchesForFile = async () => {
      const branchesWithVersions = new Set<string>()
      const branchesWithUniqueChanges = new Set<string>()
      // Store content hashes per branch for comparison
      const branchContentHashes: Map<string, Set<string>> = new Map()

      // Fetch file history for each branch in parallel
      await Promise.all(
        branches.map(async (branch) => {
          try {
            const response = await getFileHistory(repoName, filePath, branch.name)
            if (response.versions && response.versions.length > 0) {
              branchesWithVersions.add(branch.name)
              // Collect content hashes for this branch
              const hashes = new Set(response.versions.map((v) => v.content_hash))
              branchContentHashes.set(branch.name, hashes)
            }
          } catch {
            // If API fails for a branch, assume file doesn't exist there
          }
        })
      )

      // Get default branch's content hashes for comparison
      const defaultHashes = branchContentHashes.get(defaultBranch) || new Set<string>()

      // Check which branches have content hashes not in the default branch
      for (const [branchName, hashes] of branchContentHashes) {
        if (branchName !== defaultBranch) {
          // Branch has changes if it has any content hash not in the default branch
          for (const hash of hashes) {
            if (!defaultHashes.has(hash)) {
              branchesWithUniqueChanges.add(branchName)
              break
            }
          }
        }
      }

      setBranchesWithFile(branchesWithVersions)
      setBranchesWithChanges(branchesWithUniqueChanges)
    }

    checkBranchesForFile()
  }, [repoName, filePath, branches, defaultBranch])

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
    // Show checkmark if: no file context (branch is indexed) OR file exists in this branch
    const hasFile = branchesWithFile.has(singleBranch?.name || '')
    const showCheckmark = filePath
      ? hasFile
      : singleBranch?.commit_count && singleBranch.commit_count > 0
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
        <AccountTreeIcon fontSize="small" />
        <Typography variant="caption">{singleBranch?.name}</Typography>
        {showCheckmark && (
          <Tooltip title={filePath ? 'File exists in this branch' : 'Branch is indexed'}>
            <CheckCircleIcon sx={{ fontSize: '0.9rem', color: 'success.main' }} />
          </Tooltip>
        )}
      </Box>
    )
  }

  // Determine the currently selected value
  // If selectedBranch isn't in the indexed branches, fall back to defaultBranch
  const selectedExists = branches.some((b) => b.name === selectedBranch)
  const currentValue = selectedExists ? selectedBranch || defaultBranch : defaultBranch

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
          minWidth: compact ? 80 : 100,
          '& .MuiSelect-select': {
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            py: compact ? 0.25 : 0.5,
            px: compact ? 0.5 : undefined,
            fontSize: compact ? '0.75rem' : '0.875rem',
          },
          ...(compact && {
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: 'divider',
            },
          }),
        }}
        renderValue={(selected) => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <AccountTreeIcon
              fontSize="small"
              sx={{ color: 'text.secondary', fontSize: compact ? '0.875rem' : undefined }}
            />
            <Typography variant={compact ? 'caption' : 'body2'}>{selected}</Typography>
          </Box>
        )}
      >
        {branches.map((branch) => {
          const isSelected = branch.name === currentValue
          const isDefault = branch.name === defaultBranch
          // File exists in this branch (show checkmark)
          const hasFile = branchesWithFile.has(branch.name)
          // File was changed on this branch (show edit icon) - only for non-default branches
          const hasChanges = branchesWithChanges.has(branch.name)
          // Show checkmark if: no file context (branch is indexed) OR file exists in this branch
          const showCheckmark = filePath ? hasFile : true

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
                {filePath && hasChanges && (
                  <Tooltip title="File was modified on this branch">
                    <EditIcon sx={{ fontSize: '0.9rem', color: 'warning.main' }} />
                  </Tooltip>
                )}
                {showCheckmark && (
                  <Tooltip
                    title={
                      filePath
                        ? 'File exists in this branch'
                        : `${branch.commit_count} commits indexed`
                    }
                  >
                    <CheckCircleIcon sx={{ fontSize: '1rem', color: 'success.main' }} />
                  </Tooltip>
                )}
              </Box>
            </MenuItem>
          )
        })}
      </Select>
    </FormControl>
  )
}
