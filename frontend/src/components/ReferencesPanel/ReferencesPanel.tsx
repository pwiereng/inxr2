import { useState, useEffect } from 'react'
import {
  Box,
  Typography,
  List,
  ListItemButton,
  ListItemText,
  Chip,
  CircularProgress,
  IconButton,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import DownloadIcon from '@mui/icons-material/Download'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import VisibilityIcon from '@mui/icons-material/Visibility'
import FunctionsIcon from '@mui/icons-material/Functions'
import ClassIcon from '@mui/icons-material/Class'
import CodeIcon from '@mui/icons-material/Code'
import DataObjectIcon from '@mui/icons-material/DataObject'
import PushPinIcon from '@mui/icons-material/PushPin'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'

import { getSymbolReferences, getSymbolsByName, type Reference, type Symbol } from '@/lib/api'

// Get icon for reference type
function getReferenceIcon(refType: string) {
  switch (refType.toLowerCase()) {
    case 'import':
      return <DownloadIcon fontSize="small" sx={{ color: '#ce9178' }} />
    case 'call':
      return <PlayArrowIcon fontSize="small" sx={{ color: '#dcdcaa' }} />
    case 'usage':
    default:
      return <VisibilityIcon fontSize="small" sx={{ color: '#9cdcfe' }} />
  }
}

// Get chip color for reference type
function getReferenceChipColor(refType: string): 'warning' | 'info' | 'success' | 'default' {
  switch (refType.toLowerCase()) {
    case 'import':
      return 'warning'
    case 'call':
      return 'success'
    case 'usage':
      return 'info'
    default:
      return 'default'
  }
}

// Get icon for symbol kind
function getSymbolKindIcon(kind: string) {
  switch (kind.toLowerCase()) {
    case 'function':
    case 'method':
      return <FunctionsIcon fontSize="small" />
    case 'class':
      return <ClassIcon fontSize="small" />
    case 'interface':
    case 'type':
      return <DataObjectIcon fontSize="small" />
    default:
      return <CodeIcon fontSize="small" />
  }
}

interface ReferencesPanelProps {
  symbol: Symbol | null
  onReferenceClick?: (reference: Reference) => void
  onDefinitionClick?: (symbol: Symbol) => void
  onClose?: () => void
}

export function ReferencesPanel({
  symbol,
  onReferenceClick,
  onDefinitionClick,
  onClose,
}: ReferencesPanelProps) {
  const [references, setReferences] = useState<Reference[]>([])
  const [allDefinitions, setAllDefinitions] = useState<Symbol[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!symbol) {
      setReferences([])
      setAllDefinitions([])
      return
    }

    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        // Fetch references and all definitions with the same name in parallel
        const [refsResult, defsResult] = await Promise.all([
          getSymbolReferences(symbol.id),
          getSymbolsByName(symbol.name, symbol.repository_id),
        ])
        setReferences(refsResult.items)
        setAllDefinitions(defsResult.items)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load references')
        setReferences([])
        setAllDefinitions([])
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [symbol])

  if (!symbol) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Select a symbol to see its references
        </Typography>
      </Box>
    )
  }

  // Group references by file
  const referencesByFile = references.reduce(
    (acc, ref) => {
      const file = ref.source_file_path || `File ${ref.source_file_id}`
      if (!acc[file]) {
        acc[file] = []
      }
      acc[file].push(ref)
      return acc
    },
    {} as Record<string, Reference[]>
  )

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          p: 1.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
            {getSymbolKindIcon(symbol.kind)}
            <Chip
              label={symbol.kind}
              size="small"
              variant="outlined"
              sx={{ height: 18, fontSize: '0.65rem' }}
            />
          </Box>
          <Typography variant="subtitle2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {symbol.name}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {references.length} reference{references.length !== 1 ? 's' : ''}
          </Typography>
        </Box>
        {onClose && (
          <IconButton size="small" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        )}
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
            <CircularProgress size={24} />
          </Box>
        ) : error ? (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="error">
              {error}
            </Typography>
          </Box>
        ) : (
          <List dense disablePadding>
            {/* Definition section - show all possible definitions */}
            <Box>
              <Box
                sx={{
                  px: 1.5,
                  py: 0.5,
                  bgcolor: 'primary.dark',
                  borderBottom: 1,
                  borderColor: 'divider',
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    fontWeight: 600,
                    display: 'block',
                    color: 'primary.contrastText',
                  }}
                >
                  {allDefinitions.length > 1
                    ? `Possible Definitions (${allDefinitions.length})`
                    : 'Definition'}
                </Typography>
              </Box>
              {allDefinitions.length > 0 ? (
                allDefinitions.map((def) => {
                  const isSelected = def.id === symbol.id
                  // Extract short file name from path
                  const fileName = def.file_path?.split('/').pop() || ''
                  return (
                    <ListItemButton
                      key={def.id}
                      onClick={() => onDefinitionClick?.(def)}
                      sx={{
                        py: 0.5,
                        px: 1.5,
                        bgcolor: isSelected ? 'action.selected' : 'transparent',
                        borderLeft: isSelected ? 3 : 0,
                        borderColor: 'primary.main',
                      }}
                    >
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {getSymbolKindIcon(def.kind)}
                            <Typography
                              variant="body2"
                              sx={{
                                fontFamily: 'monospace',
                                fontWeight: isSelected ? 600 : 400,
                                color: isSelected ? 'primary.main' : 'text.primary',
                              }}
                            >
                              {def.qualified_name || def.name}
                            </Typography>
                            <Typography
                              variant="body2"
                              sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                            >
                              :{def.start_line}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Typography
                            variant="caption"
                            sx={{
                              fontFamily: 'monospace',
                              color: 'text.secondary',
                              display: 'block',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {fileName}
                          </Typography>
                        }
                      />
                    </ListItemButton>
                  )
                })
              ) : symbol.file_path ? (
                <ListItemButton
                  onClick={() => onDefinitionClick?.(symbol)}
                  sx={{ py: 0.5, px: 1.5 }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <PushPinIcon fontSize="small" sx={{ color: '#4fc3f7' }} />
                        <Chip
                          label="definition"
                          size="small"
                          color="primary"
                          sx={{ height: 18, fontSize: '0.65rem', minWidth: 50 }}
                        />
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                        >
                          :{symbol.start_line}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Typography
                        variant="caption"
                        sx={{
                          fontFamily: 'monospace',
                          color: 'text.secondary',
                          display: 'block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {symbol.file_path}
                      </Typography>
                    }
                  />
                </ListItemButton>
              ) : (
                <Box sx={{ py: 1, px: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <HelpOutlineIcon fontSize="small" sx={{ color: 'text.disabled' }} />
                  <Typography variant="body2" color="text.disabled" sx={{ fontStyle: 'italic' }}>
                    No definition found (external symbol)
                  </Typography>
                </Box>
              )}
            </Box>

            {/* References section */}
            {references.length === 0 ? (
              <Box sx={{ p: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  No references found
                </Typography>
              </Box>
            ) : (
              <>
                <Box
                  sx={{
                    px: 1.5,
                    py: 0.5,
                    bgcolor: 'action.selected',
                    borderBottom: 1,
                    borderColor: 'divider',
                    mt: 1,
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 600,
                      display: 'block',
                    }}
                  >
                    References ({references.length})
                  </Typography>
                </Box>
                {Object.entries(referencesByFile).map(([file, refs]) => (
                  <Box key={file}>
                    {/* File header */}
                    <Box
                      sx={{
                        px: 1.5,
                        py: 0.5,
                        bgcolor: 'action.hover',
                        borderBottom: 1,
                        borderColor: 'divider',
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          fontFamily: 'monospace',
                          fontWeight: 500,
                          display: 'block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {file}
                      </Typography>
                    </Box>

                    {/* References in file */}
                    {refs.map((ref) => (
                      <ListItemButton
                        key={ref.id}
                        onClick={() => onReferenceClick?.(ref)}
                        sx={{ py: 0.5, px: 1.5 }}
                      >
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              {getReferenceIcon(ref.reference_type)}
                              <Chip
                                label={ref.reference_type}
                                size="small"
                                color={getReferenceChipColor(ref.reference_type)}
                                sx={{ height: 18, fontSize: '0.65rem', minWidth: 50 }}
                              />
                              <Typography
                                variant="body2"
                                sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                              >
                                :{ref.source_line}
                              </Typography>
                            </Box>
                          }
                        />
                      </ListItemButton>
                    ))}
                  </Box>
                ))}
              </>
            )}
          </List>
        )}
      </Box>
    </Box>
  )
}

export default ReferencesPanel
