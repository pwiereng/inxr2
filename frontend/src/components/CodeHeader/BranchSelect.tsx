import { Box, Select, MenuItem, FormControl, CircularProgress } from '@mui/material'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import type { BranchInfo } from '@/lib/api'
import { MENU_PROPS } from '@/lib/menuProps'

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
            {branchInfo.name}
            {branchInfo.name === defaultBranch && ' (default)'}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  )
}
