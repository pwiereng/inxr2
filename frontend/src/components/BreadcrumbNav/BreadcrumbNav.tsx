import { Box, Link, Typography } from '@mui/material'
import NavigateNextIcon from '@mui/icons-material/NavigateNext'

interface BreadcrumbNavProps {
  /** Repository name (shown as root segment) */
  repoName: string
  /** Current path (file or directory) — null/empty for root */
  currentPath: string | null
  /** Called when a directory segment is clicked */
  onDirectoryClick: (path: string) => void
  /** Called when the repo root is clicked */
  onRootClick: () => void
}

export function BreadcrumbNav({
  repoName,
  currentPath,
  onDirectoryClick,
  onRootClick,
}: BreadcrumbNavProps): React.ReactElement {
  if (!currentPath) {
    // Root level — just show repo name as non-clickable
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', minWidth: 0, overflow: 'hidden' }}>
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'monospace',
            fontWeight: 600,
            whiteSpace: 'nowrap',
          }}
        >
          {repoName}
        </Typography>
      </Box>
    )
  }

  const segments = currentPath.replace(/\/$/, '').split('/')
  // Build cumulative paths for each segment
  const segmentPaths = segments.map((_, i) => segments.slice(0, i + 1).join('/'))

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        minWidth: 0,
        overflow: 'hidden',
        flexShrink: 1,
      }}
    >
      {/* Repo root */}
      <Link
        component="button"
        variant="body2"
        underline="hover"
        onClick={onRootClick}
        sx={{
          fontFamily: 'monospace',
          fontWeight: 600,
          whiteSpace: 'nowrap',
          color: 'primary.main',
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        {repoName}
      </Link>

      {segments.map((segment, index) => {
        const isLast = index === segments.length - 1

        return (
          <Box
            key={segmentPaths[index]}
            sx={{ display: 'flex', alignItems: 'center', flexShrink: isLast ? 1 : 0, minWidth: 0 }}
          >
            <NavigateNextIcon
              sx={{ fontSize: 16, color: 'text.disabled', mx: 0.25, flexShrink: 0 }}
            />
            {isLast ? (
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'monospace',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  minWidth: 0,
                }}
              >
                {segment}
              </Typography>
            ) : (
              <Link
                component="button"
                variant="body2"
                underline="hover"
                onClick={() => onDirectoryClick(segmentPaths[index]!)}
                sx={{
                  fontFamily: 'monospace',
                  whiteSpace: 'nowrap',
                  color: 'primary.main',
                  cursor: 'pointer',
                }}
              >
                {segment}
              </Link>
            )}
          </Box>
        )
      })}
    </Box>
  )
}
