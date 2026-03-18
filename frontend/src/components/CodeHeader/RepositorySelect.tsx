import { Box, Autocomplete, TextField, CircularProgress, createFilterOptions } from '@mui/material'
import FolderIcon from '@mui/icons-material/Folder'
import PublicIcon from '@mui/icons-material/Public'
import type { Repository } from '@/lib/api'
import type { TabValue } from './CodeHeader'

const baseFilter = createFilterOptions<string>()

interface RepositorySelectProps {
  repositories: Repository[]
  loading: boolean
  repoName: string | null
  currentTab: TabValue
  onRepoChange: (repoName: string) => void
}

const ALL_REPOS_OPTION = '__all__'

export function RepositorySelect({
  repositories,
  loading,
  repoName,
  currentTab,
  onRepoChange,
}: RepositorySelectProps): React.ReactElement | null {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <CircularProgress size={20} />
      </Box>
    )
  }

  if (repositories.length > 1 || currentTab === 'search') {
    const options =
      currentTab === 'search'
        ? [ALL_REPOS_OPTION, ...repositories.map((r) => r.name)]
        : repositories.map((r) => r.name)

    const value = repoName || (currentTab === 'search' ? ALL_REPOS_OPTION : undefined)

    return (
      <Autocomplete
        size="small"
        options={options}
        value={value}
        filterOptions={
          currentTab === 'search'
            ? (opts, params) => [
                ALL_REPOS_OPTION,
                ...baseFilter(
                  opts.filter((o) => o !== ALL_REPOS_OPTION),
                  params,
                ),
              ]
            : undefined
        }
        onChange={(_e, newValue) => {
          if (newValue === ALL_REPOS_OPTION) {
            onRepoChange('')
          } else if (newValue) {
            onRepoChange(newValue)
          }
        }}
        disableClearable
        getOptionLabel={(option) => (option === ALL_REPOS_OPTION ? 'All Repositories' : option)}
        renderOption={({ key, ...props }, option) => (
          <li key={key} {...props}>
            {option === ALL_REPOS_OPTION ? (
              <PublicIcon fontSize="small" sx={{ mr: 1 }} />
            ) : (
              <FolderIcon fontSize="small" sx={{ mr: 1 }} />
            )}
            {option === ALL_REPOS_OPTION ? 'All Repositories' : option}
          </li>
        )}
        renderInput={(params) => (
          <TextField
            {...params}
            placeholder="Repository..."
            InputProps={{
              ...params.InputProps,
              startAdornment: (
                <>
                  {value === ALL_REPOS_OPTION ? (
                    <PublicIcon fontSize="small" sx={{ ml: 0.5, mr: 0.5 }} />
                  ) : (
                    <FolderIcon fontSize="small" sx={{ ml: 0.5, mr: 0.5 }} />
                  )}
                  {params.InputProps.startAdornment}
                </>
              ),
            }}
          />
        )}
        sx={{ minWidth: 200 }}
      />
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
