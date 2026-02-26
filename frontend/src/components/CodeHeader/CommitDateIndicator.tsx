import { Box, Tooltip, Typography } from '@mui/material'
import CalendarTodayIcon from '@mui/icons-material/CalendarToday'

interface CommitDateIndicatorProps {
  currentCommitDate: string
}

export function CommitDateIndicator({
  currentCommitDate,
}: CommitDateIndicatorProps): React.ReactElement {
  return (
    <Tooltip title={`Browsing code as of ${currentCommitDate}`}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          color: 'text.secondary',
          ml: 0.5,
        }}
      >
        <CalendarTodayIcon sx={{ fontSize: '0.95rem' }} />
        <Typography
          variant="body2"
          sx={{
            fontSize: '0.85rem',
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          {currentCommitDate}
        </Typography>
      </Box>
    </Tooltip>
  )
}
