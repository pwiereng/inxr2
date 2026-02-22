import { Box, Select, MenuItem, FormControl, CircularProgress } from '@mui/material'
import FolderIcon from '@mui/icons-material/Folder'
import PublicIcon from '@mui/icons-material/Public'
import type { Repository } from '@/lib/api'
import { MENU_PROPS } from '@/lib/menuProps'
import type { TabValue } from './CodeHeader'

interface RepositorySelectProps {
  repositories: Repository[]
  loading: boolean
  repoName: string | null
  currentTab: TabValue
  onRepoChange: (repoName: string) => void
}

export function RepositorySelect({
  repositories,
  loading,
  repoName,
  currentTab,
  onRepoChange,
}: RepositorySelectProps) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <CircularProgress size={20} />
      </Box>
    )
  }

  if (repositories.length > 1 || currentTab === 'search') {
    return (
      <FormControl size="small" sx={{ minWidth: 150 }}>
        <Select
          value={repoName || ''}
          onChange={(e) => onRepoChange(e.target.value as string)}
          displayEmpty
          MenuProps={MENU_PROPS}
          sx={{
            '& .MuiSelect-select': {
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              py: 0.5,
            },
          }}
        >
          {currentTab === 'search' && (
            <MenuItem value="">
              <PublicIcon fontSize="small" sx={{ mr: 1 }} />
              All Repositories
            </MenuItem>
          )}
          {repositories.map((repo) => (
            <MenuItem key={repo.id} value={repo.name}>
              <FolderIcon fontSize="small" sx={{ mr: 1 }} />
              {repo.name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    )
  }

  if (repositories.length === 1 && repositories[0]) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 1 }}>
        <FolderIcon fontSize="small" />
        {repositories[0].name}
      </Box>
    )
  }

  return null
}
