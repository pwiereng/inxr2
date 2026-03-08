import { Box, Select, MenuItem, FormControl, CircularProgress } from '@mui/material'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import type { BranchInfo } from '@/lib/api'
import { MENU_PROPS } from '@/lib/menuProps'
import { CopyButton } from '@/components/CopyButton/CopyButton'

interface BranchSelectProps {
  branches: BranchInfo[]
  loading: boolean
  branch: string | null
  defaultBranch: string
  onBranchChange: (branch: string) => void
}

export function BranchSelect({
  branches,
  loading,
  branch,
  defaultBranch,
  onBranchChange,
}: BranchSelectProps): React.ReactElement | null {
  if (loading) {
    return <CircularProgress size={20} />
  }

  if (branches.length === 0) {
    return null
  }

  // Guard against out-of-range value when the current branch
  // is not in the available branches (e.g. switching repos).
  // Prefer branch if valid, then defaultBranch, then ''.
  const branchValue = branch || defaultBranch
  const hasBranch = branches.some((b) => b.name === branchValue)
  const hasDefault = branches.some((b) => b.name === defaultBranch)
  const selectValue = hasBranch ? branchValue : hasDefault ? defaultBranch : ''

  return (
    <FormControl size="small" sx={{ minWidth: 120 }}>
      <Select
        value={selectValue}
        onChange={(e) => onBranchChange(e.target.value as string)}
        displayEmpty
        MenuProps={MENU_PROPS}
        sx={{
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
            {selected || defaultBranch}
          </Box>
        )}
      >
        {branches.map((branchInfo) => (
          <MenuItem key={branchInfo.name} value={branchInfo.name}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, width: '100%' }}>
              <Box component="span" sx={{ flex: 1 }}>
                {branchInfo.name}
                {branchInfo.name === defaultBranch && ' (default)'}
              </Box>
              <CopyButton value={branchInfo.name} tooltip="Copy branch name" size={12} />
            </Box>
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  )
}
