import { useState, useCallback, useRef, useEffect } from 'react'
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
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  const handleClick = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation()
      e.preventDefault()
      const textToCopy = e.shiftKey && fullValue ? fullValue : value

      if (!navigator.clipboard?.writeText) {
        return
      }

      try {
        await navigator.clipboard.writeText(textToCopy)
        if (timeoutRef.current !== null) {
          clearTimeout(timeoutRef.current)
        }
        setCopied(true)
        timeoutRef.current = setTimeout(() => setCopied(false), 1500)
      } catch {
        // Graceful fallback: do not change UI state on failure
      }
    },
    [value, fullValue]
  )

  const tooltipText = copied
    ? 'Copied!'
    : fullValue
      ? `${tooltip} (Shift+click for full value)`
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
