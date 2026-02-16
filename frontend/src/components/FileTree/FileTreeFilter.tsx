import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useTheme } from '@mui/material/styles'
import {
  Box,
  TextField,
  InputAdornment,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import ClearIcon from '@mui/icons-material/Clear'
import FolderIcon from '@mui/icons-material/Folder'
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'

import type { TreeNode } from '@/lib/api'
import { FileTypeIcon } from './file-icons'
import { flattenTree, filterAndRank, highlightMatch } from './filterTreeNodes'
import type { FlatFileEntry } from './filterTreeNodes'

interface FileTreeFilterProps {
  nodes: TreeNode[]
  filterText: string
  onFilterChange: (text: string) => void
  onFileSelect: (path: string) => void
  onDirectorySelect: (path: string) => void
}

export function FileTreeFilter({
  nodes,
  filterText,
  onFilterChange,
  onFileSelect,
  onDirectorySelect,
}: FileTreeFilterProps) {
  const theme = useTheme()
  const [activeIndex, setActiveIndex] = useState(0)
  const listRef = useRef<HTMLUListElement>(null)

  const flat = useMemo(() => flattenTree(nodes), [nodes])
  const results = useMemo(() => filterAndRank(flat, filterText), [flat, filterText])

  // Reset active index when results change
  useEffect(() => {
    setActiveIndex(0)
  }, [results.length, filterText])

  const handleSelect = useCallback(
    (entry: FlatFileEntry) => {
      if (entry.type === 'file') {
        onFileSelect(entry.path)
      } else {
        onDirectorySelect(entry.path)
      }
    },
    [onFileSelect, onDirectorySelect]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!filterText) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex((prev) => Math.min(prev + 1, results.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex((prev) => Math.max(prev - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (results[activeIndex]) {
          handleSelect(results[activeIndex])
        }
      } else if (e.key === 'Escape') {
        e.preventDefault()
        onFilterChange('')
      }
    },
    [filterText, results, activeIndex, handleSelect, onFilterChange]
  )

  // Scroll active item into view
  useEffect(() => {
    if (listRef.current) {
      const activeItem = listRef.current.querySelector(`[data-index="${activeIndex}"]`)
      if (activeItem && typeof (activeItem as HTMLElement).scrollIntoView === 'function') {
        ;(activeItem as HTMLElement).scrollIntoView({ block: 'nearest' })
      }
    }
  }, [activeIndex])

  const showResults = filterText.trim().length > 0

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* Search input */}
      <Box sx={{ px: 1, pt: 1, pb: 0.5, flexShrink: 0 }}>
        <TextField
          size="small"
          fullWidth
          placeholder="Filter files..."
          value={filterText}
          onChange={(e) => onFilterChange(e.target.value)}
          onKeyDown={handleKeyDown}
          inputProps={{ 'aria-label': 'Filter files' }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
            endAdornment: filterText ? (
              <InputAdornment position="end">
                <IconButton
                  size="small"
                  onClick={() => onFilterChange('')}
                  aria-label="Clear filter"
                  edge="end"
                >
                  <ClearIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ) : null,
            sx: {
              fontFamily: 'monospace',
              fontSize: '13px',
            },
          }}
        />
      </Box>

      {/* Results list */}
      {showResults && (
        <Box sx={{ overflow: 'auto', flex: 1 }}>
          {results.length === 0 ? (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ px: 2, py: 1, fontStyle: 'italic' }}
            >
              No matches found
            </Typography>
          ) : (
            <List dense disablePadding ref={listRef} role="listbox">
              {results.map((entry, index) => {
                const nameHighlight = highlightMatch(entry.name, filterText)
                const isActive = index === activeIndex

                return (
                  <ListItemButton
                    key={entry.path}
                    data-index={index}
                    selected={isActive}
                    onClick={() => handleSelect(entry)}
                    role="option"
                    aria-selected={isActive}
                    sx={{
                      py: 0.5,
                      px: 1.5,
                      minHeight: 36,
                      '&.Mui-selected': {
                        bgcolor: 'action.selected',
                      },
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 28 }}>
                      {entry.type === 'directory' ? (
                        <FolderIcon
                          fontSize="small"
                          sx={{ color: theme.palette.fileTree.folder }}
                        />
                      ) : (
                        <FileTypeIcon
                          filename={entry.name}
                          language={entry.node.language}
                          fontSize="small"
                          fallback={
                            <InsertDriveFileIcon
                              fontSize="small"
                              sx={{ color: theme.palette.fileTree.defaultFile }}
                            />
                          }
                        />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <span style={{ fontFamily: 'monospace', fontSize: '13px' }}>
                          {nameHighlight.before}
                          <strong>{nameHighlight.match}</strong>
                          {nameHighlight.after}
                        </span>
                      }
                      secondary={
                        <span
                          style={{
                            fontFamily: 'monospace',
                            fontSize: '11px',
                            opacity: 0.6,
                          }}
                        >
                          {entry.path}
                        </span>
                      }
                      sx={{ my: 0 }}
                    />
                  </ListItemButton>
                )
              })}
            </List>
          )}
        </Box>
      )}
    </Box>
  )
}
