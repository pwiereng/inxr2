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

  return (
    <FormControl size="small" sx={{ minWidth: 120 }}>
      <Select
        value={branch || defaultBranch}
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
            {selected}
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
