import { useState, useCallback } from 'react'
import { IconButton, Tooltip } from '@mui/material'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import CheckIcon from '@mui/icons-material/Check'

interface CopyButtonProps {
  /** The text to copy on click (typically short hash or branch name) */
  value: string
  /** Optional full value to copy on Shift+click (e.g., full commit hash) */
  fullValue?: string
  /** Tooltip text (defaults to "Copy") */
  tooltip?: string
  /** Size of the icon button */
  size?: number
}

export function CopyButton({
  value,
  fullValue,
  tooltip = 'Copy',
  size = 14,
}: CopyButtonProps): React.ReactElement {
  const [copied, setCopied] = useState(false)

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      e.preventDefault()
      const textToCopy = e.shiftKey && fullValue ? fullValue : value
      navigator.clipboard.writeText(textToCopy).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      })
    },
    [value, fullValue]
  )

  const tooltipText = copied
    ? 'Copied!'
    : fullValue
      ? `${tooltip} (Shift+click for full hash)`
      : tooltip

  return (
    <Tooltip title={tooltipText} placement="top">
      <IconButton
        size="small"
        onClick={handleClick}
        aria-label={tooltip}
        sx={{
          p: 0.25,
          opacity: copied ? 1 : 0.4,
          transition: 'opacity 0.15s',
          '&:hover': { opacity: 1 },
          color: copied ? 'success.main' : 'text.secondary',
        }}
      >
        {copied ? (
          <CheckIcon sx={{ fontSize: size }} />
        ) : (
          <ContentCopyIcon sx={{ fontSize: size }} />
        )}
      </IconButton>
    </Tooltip>
  )
}
