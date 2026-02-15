import { useMemo } from 'react'
import { Box, Typography } from '@mui/material'
import type { RawFileContent } from '@/lib/api'

interface ImageViewerProps {
  rawContent: RawFileContent
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ImageViewer({ rawContent }: ImageViewerProps) {
  const imgSrc = useMemo(() => {
    if (rawContent.encoding === 'utf-8' && rawContent.content_type === 'image/svg+xml') {
      // SVG as UTF-8 text — use a data URI with the raw SVG
      return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(rawContent.data)}`
    }
    // Base64-encoded binary image
    return `data:${rawContent.content_type};base64,${rawContent.data}`
  }, [rawContent])

  const fileType = rawContent.content_type.split('/')[1]?.toUpperCase() ?? 'IMAGE'

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        flex: 1,
        p: 3,
        gap: 2,
      }}
    >
      <Box
        component="img"
        src={imgSrc}
        alt={rawContent.path}
        sx={{
          maxWidth: '100%',
          maxHeight: 'calc(100vh - 200px)',
          objectFit: 'contain',
          borderRadius: 1,
          boxShadow: 1,
        }}
      />
      <Typography variant="caption" color="text.secondary">
        {fileType} &middot; {formatFileSize(rawContent.size_bytes)}
      </Typography>
    </Box>
  )
}

export default ImageViewer
