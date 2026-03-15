import { IconButton, Tooltip } from '@mui/material'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import LastPageIcon from '@mui/icons-material/LastPage'
import type { CommitInfo } from '@/lib/api'

interface CommitNavButtonsProps {
  commits: CommitInfo[]
  commitDisplayValue: string
  onCommitChange: (commit: string) => void
}

export function CommitNavButtons({
  commits,
  commitDisplayValue,
  onCommitChange,
}: CommitNavButtonsProps): React.ReactElement | null {
  if (commits.length === 0) {
    return null
  }

  const currentIndex = commits.findIndex((c) => c.hash === commitDisplayValue)
  // If commit not found in list, treat as HEAD (index 0)
  const effectiveIndex = currentIndex === -1 ? 0 : currentIndex

  const canGoNewer = effectiveIndex > 0
  const canGoOlder = effectiveIndex < commits.length - 1

  const handleOlder = () => {
    if (canGoOlder) {
      const olderCommit = commits[effectiveIndex + 1]
      if (olderCommit) {
        onCommitChange(olderCommit.hash)
      }
    }
  }

  const handleNewer = () => {
    if (canGoNewer) {
      const newerCommit = commits[effectiveIndex - 1]
      if (newerCommit) {
        onCommitChange(newerCommit.hash)
      }
    }
  }

  const handleLatest = () => {
    const latestCommit = commits[0]
    if (latestCommit) {
      onCommitChange(latestCommit.hash)
    }
  }

  return (
    <>
      <Tooltip title="Older commit">
        <span>
          <IconButton
            size="small"
            onClick={handleOlder}
            disabled={!canGoOlder}
            aria-label="Older commit"
            sx={{ p: 0.25, color: 'text.secondary' }}
          >
            <ChevronLeftIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Newer commit">
        <span>
          <IconButton
            size="small"
            onClick={handleNewer}
            disabled={!canGoNewer}
            aria-label="Newer commit"
            sx={{ p: 0.25, color: 'text.secondary' }}
          >
            <ChevronRightIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Go to latest">
        <span>
          <IconButton
            size="small"
            onClick={handleLatest}
            disabled={!canGoNewer}
            aria-label="Go to latest"
            sx={{ p: 0.25, color: 'text.secondary' }}
          >
            <LastPageIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
    </>
  )
}
