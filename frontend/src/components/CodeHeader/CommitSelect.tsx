import {
  Box,
  Select,
  MenuItem,
  FormControl,
  Tooltip,
  Typography,
  CircularProgress,
} from '@mui/material'
import type { CommitInfo } from '@/lib/api'
import { formatDateTimeUTC } from '@/lib/dateUtils'
import { MENU_PROPS } from '@/lib/menuProps'
import { CopyButton } from '@/components/CopyButton/CopyButton'

interface CommitSelectProps {
  commits: CommitInfo[]
  loading: boolean
  commitDisplayValue: string
  onCommitChange: (commit: string) => void
}

// Get short hash for commit display
const getShortHash = (hash: string) => hash.substring(0, 7)

export function CommitSelect({
  commits,
  loading,
  commitDisplayValue,
  onCommitChange,
}: CommitSelectProps): React.ReactElement | null {
  if (loading) {
    return <CircularProgress size={20} />
  }

  if (commits.length === 0) {
    return null
  }

  // Guard against out-of-range value warning when the commit hash
  // (e.g. HEAD) is not in the list of indexed commits
  const isValueInOptions = commits.some((c) => c.hash === commitDisplayValue)
  const selectValue = isValueInOptions ? commitDisplayValue : ''

  return (
    <FormControl size="small" sx={{ minWidth: 140 }}>
      <Select
        value={selectValue}
        onChange={(e) => onCommitChange(e.target.value as string)}
        displayEmpty
        MenuProps={MENU_PROPS}
        sx={{
          '& .MuiSelect-select': {
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            py: 0.5,
            fontSize: '0.875rem',
            fontFamily: 'monospace',
          },
        }}
        renderValue={(selected) => {
          if (!selected) return 'latest'
          const selectedCommitObj = commits.find((c) => c.hash === selected)
          return selectedCommitObj ? getShortHash(selectedCommitObj.hash) : 'latest'
        }}
      >
        {commits.map((commitInfo, index) => {
          const formattedDate = commitInfo.commit_date
            ? formatDateTimeUTC(commitInfo.commit_date)
            : ''
          return (
            <MenuItem
              key={commitInfo.hash}
              value={commitInfo.hash}
              sx={{
                ...(commitInfo.is_branch_specific && {
                  borderLeft: 3,
                  borderColor: 'success.main',
                  bgcolor: 'action.hover',
                }),
                ...(commitInfo.is_merge_base && {
                  borderBottom: 2,
                  borderColor: 'info.main',
                }),
              }}
            >
              <Tooltip title={commitInfo.message} placement="left">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box
                    component="span"
                    sx={{
                      fontFamily: 'monospace',
                      fontSize: '0.8rem',
                    }}
                  >
                    {getShortHash(commitInfo.hash)}
                  </Box>
                  <CopyButton
                    value={getShortHash(commitInfo.hash)}
                    fullValue={commitInfo.hash}
                    tooltip="Copy commit hash"
                    size={12}
                  />
                  {formattedDate && (
                    <Box
                      component="span"
                      sx={{
                        fontSize: '0.75rem',
                        color: 'text.secondary',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {formattedDate}
                    </Box>
                  )}
                  <Box
                    component="span"
                    sx={{
                      fontSize: '0.75rem',
                      color: 'text.secondary',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      maxWidth: 200,
                    }}
                  >
                    {commitInfo.message}
                  </Box>
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
                        whiteSpace: 'nowrap',
                      }}
                    >
                      HEAD
                    </Typography>
                  )}
                  {commitInfo.is_merge_base && (
                    <Typography
                      component="span"
                      variant="caption"
                      sx={{
                        ml: 0.5,
                        px: 0.5,
                        py: 0.125,
                        bgcolor: 'info.main',
                        color: 'info.contrastText',
                        borderRadius: 0.5,
                        fontSize: '0.65rem',
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      FORK
                    </Typography>
                  )}
                  {commitInfo.tags?.map((tag) => (
                    <Typography
                      key={tag}
                      component="span"
                      variant="caption"
                      sx={{
                        ml: 0.5,
                        px: 0.5,
                        py: 0.125,
                        bgcolor: 'warning.main',
                        color: 'warning.contrastText',
                        borderRadius: 0.5,
                        fontSize: '0.65rem',
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {tag}
                    </Typography>
                  ))}
                </Box>
              </Tooltip>
            </MenuItem>
          )
        })}
      </Select>
    </FormControl>
  )
}
