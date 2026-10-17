import { useState, useEffect, useRef, useCallback } from 'react'
import { useTheme } from '@mui/material/styles'
import {
  Box,
  Typography,
  List,
  IconButton,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Collapse,
  CircularProgress,
} from '@mui/material'
import FolderIcon from '@mui/icons-material/Folder'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'

import type { TreeNode } from '@/lib/api'
import { FileTypeIcon } from './file-icons'
import { FileTreeFilter } from './FileTreeFilter'

// Find a file in the tree by its ID and return the path to it
function findFilePathById(nodes: TreeNode[], fileId: number): string | null {
  for (const node of nodes) {
    if (node.file_id === fileId) {
      return node.path
    }
    if (node.children) {
      const found = findFilePathById(node.children, fileId)
      if (found) return found
    }
  }
  return null
}

// Get all parent directory paths for a given file path
function getParentPaths(filePath: string): string[] {
  const parts = filePath.split('/')
  const paths: string[] = []
  for (let i = 1; i < parts.length; i++) {
    paths.push(parts.slice(0, i).join('/'))
  }
  return paths
}

interface FileTreeProps {
  nodes: TreeNode[]
  selectedFileId?: number | null
  /** When set, the tree auto-expands to reveal this directory */
  selectedDirectoryPath?: string | null
  onFileSelect?: (path: string) => void
  /** Called when a directory row (folder icon or name, not the chevron) is clicked */
  onDirectorySelect?: (path: string) => void
  loading?: boolean
}

interface TreeNodeItemProps {
  node: TreeNode
  level: number
  selectedFileId?: number | null
  selectedDirectoryPath?: string | null
  onFileSelect?: (path: string) => void
  onDirectoryClick: (path: string) => void
  expandedPaths: Set<string>
  toggleExpanded: (path: string) => void
  selectedFileRef?: React.RefObject<HTMLDivElement>
  selectedDirRef?: React.RefObject<HTMLDivElement>
}

function TreeNodeItem({
  node,
  level,
  selectedFileId,
  selectedDirectoryPath,
  onFileSelect,
  onDirectoryClick,
  expandedPaths,
  toggleExpanded,
  selectedFileRef,
  selectedDirRef,
}: TreeNodeItemProps) {
  const theme = useTheme()
  const isExpanded = expandedPaths.has(node.path)
  const isDirectory = node.type === 'directory'
  const isSelected = node.file_id != null && node.file_id === selectedFileId
  const isSelectedDirectory = isDirectory && node.path === selectedDirectoryPath
  const isRowSelected = isSelected || isSelectedDirectory
  const indent = 1 + level * 2

  const handleClick = () => {
    if (isDirectory) {
      onDirectoryClick(node.path)
    } else if (onFileSelect) {
      onFileSelect(node.path)
    }
  }

  // The chevron only expands/collapses; it is a sibling of the row button
  // (not nested in it) so it can be focused and activated on its own.
  const handleChevronClick = (event: React.MouseEvent) => {
    event.stopPropagation()
    toggleExpanded(node.path)
  }

  return (
    <>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          bgcolor: isRowSelected ? 'primary.main' : undefined,
        }}
      >
        {/* Expand/collapse control for directories */}
        {isDirectory && (
          <IconButton
            size="small"
            onClick={handleChevronClick}
            aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${node.name}`}
            aria-expanded={isExpanded}
            sx={{
              ml: indent,
              p: 0,
              width: 24,
              height: 24,
              borderRadius: 1,
              color: isRowSelected ? 'primary.contrastText' : 'text.secondary',
            }}
          >
            {isExpanded ? (
              <ExpandMoreIcon fontSize="small" />
            ) : (
              <ChevronRightIcon fontSize="small" />
            )}
          </IconButton>
        )}
        <ListItemButton
          ref={isSelected ? selectedFileRef : isSelectedDirectory ? selectedDirRef : undefined}
          onClick={handleClick}
          selected={isRowSelected}
          sx={{
            pl: isDirectory ? 0 : indent,
            py: 0.5,
            minHeight: 32,
            '&.Mui-selected': {
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              '&:hover': {
                bgcolor: 'primary.dark',
              },
              '& .MuiListItemIcon-root': {
                color: 'primary.contrastText',
              },
            },
          }}
        >
          {/* File/folder icon */}
          <ListItemIcon sx={{ minWidth: 28 }}>
            {isDirectory ? (
              isExpanded ? (
                <FolderOpenIcon fontSize="small" sx={{ color: theme.palette.fileTree.folder }} />
              ) : (
                <FolderIcon fontSize="small" sx={{ color: theme.palette.fileTree.folder }} />
              )
            ) : (
              <FileTypeIcon
                filename={node.name}
                language={node.language}
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

          {/* Name */}
          <ListItemText
            primary={node.name}
            primaryTypographyProps={{
              variant: 'body2',
              sx: {
                fontFamily: 'monospace',
                fontSize: '13px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              },
            }}
          />
        </ListItemButton>
      </Box>

      {/* Children (for directories) */}
      {isDirectory && node.children && (
        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
          <List disablePadding>
            {node.children.map((child) => (
              <TreeNodeItem
                key={child.path}
                node={child}
                level={level + 1}
                selectedFileId={selectedFileId}
                selectedDirectoryPath={selectedDirectoryPath}
                onFileSelect={onFileSelect}
                onDirectoryClick={onDirectoryClick}
                expandedPaths={expandedPaths}
                toggleExpanded={toggleExpanded}
                selectedFileRef={selectedFileRef}
                selectedDirRef={selectedDirRef}
              />
            ))}
          </List>
        </Collapse>
      )}
    </>
  )
}

export function FileTree({
  nodes,
  selectedFileId,
  selectedDirectoryPath,
  onFileSelect,
  onDirectorySelect,
  loading = false,
}: FileTreeProps): React.ReactElement {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set())
  const [filterText, setFilterText] = useState('')
  const selectedFileRef = useRef<HTMLDivElement>(null!)
  const selectedDirRef = useRef<HTMLDivElement>(null!)
  const fileScrollTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const dirScrollTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  // Directory the tree itself just asked the parent to open. When it comes back
  // as selectedDirectoryPath, the row click already set its expansion.
  const treeSelectedDirRef = useRef<string | null>(null)

  const toggleExpanded = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }, [])

  // Auto-expand path and scroll to selected file when selectedFileId changes
  useEffect(() => {
    if (selectedFileId && nodes.length > 0) {
      const filePath = findFilePathById(nodes, selectedFileId)
      if (filePath) {
        const parentPaths = getParentPaths(filePath)
        // Expand all parent directories
        setExpandedPaths((prev) => {
          const next = new Set(prev)
          parentPaths.forEach((p) => next.add(p))
          return next
        })
        // Scroll into view after a short delay to allow expansion animation
        fileScrollTimerRef.current = setTimeout(() => {
          if (typeof selectedFileRef.current?.scrollIntoView === 'function') {
            selectedFileRef.current.scrollIntoView({
              behavior: 'smooth',
              block: 'center',
            })
          }
        }, 100)
      }
    }
    return () => clearTimeout(fileScrollTimerRef.current)
  }, [selectedFileId, nodes])

  // Directory row click: open it in the main pane and toggle it in the tree
  const handleDirectoryClick = useCallback(
    (path: string) => {
      toggleExpanded(path)
      if (onDirectorySelect && path !== selectedDirectoryPath) {
        treeSelectedDirRef.current = path
        onDirectorySelect(path)
      }
    },
    [toggleExpanded, onDirectorySelect, selectedDirectoryPath]
  )

  // Auto-expand to selected directory path (from breadcrumb navigation)
  useEffect(() => {
    if (selectedDirectoryPath && nodes.length > 0) {
      const fromTreeClick = treeSelectedDirRef.current === selectedDirectoryPath
      treeSelectedDirRef.current = null
      const parentPaths = getParentPaths(selectedDirectoryPath)
      setExpandedPaths((prev) => {
        const next = new Set(prev)
        // Expand the directory itself (unless the tree click just set it) and all its parents
        if (!fromTreeClick) next.add(selectedDirectoryPath)
        parentPaths.forEach((p) => next.add(p))
        return next
      })
      // The clicked row is already on screen
      if (fromTreeClick) return
      // Scroll into view after expansion
      dirScrollTimerRef.current = setTimeout(() => {
        if (typeof selectedDirRef.current?.scrollIntoView === 'function') {
          selectedDirRef.current.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
          })
        }
      }, 100)
    }
    return () => clearTimeout(dirScrollTimerRef.current)
  }, [selectedDirectoryPath, nodes])

  const handleFilterFileSelect = useCallback(
    (path: string) => {
      setFilterText('')
      onFileSelect?.(path)
    },
    [onFileSelect]
  )

  const handleFilterDirectorySelect = useCallback((path: string) => {
    setFilterText('')
    // Expand the directory and all its parents
    const parentPaths = getParentPaths(path)
    setExpandedPaths((prev) => {
      const next = new Set(prev)
      // Add the directory itself and all parents
      next.add(path)
      parentPaths.forEach((p) => next.add(p))
      return next
    })
  }, [])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    )
  }

  if (nodes.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          No files found
        </Typography>
      </Box>
    )
  }

  const isFiltering = filterText.trim().length > 0

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <FileTreeFilter
        nodes={nodes}
        filterText={filterText}
        onFilterChange={setFilterText}
        onFileSelect={handleFilterFileSelect}
        onDirectorySelect={handleFilterDirectorySelect}
      />
      {!isFiltering && (
        <List dense disablePadding sx={{ overflow: 'auto', flex: 1 }}>
          {nodes.map((node) => (
            <TreeNodeItem
              key={node.path}
              node={node}
              level={0}
              selectedFileId={selectedFileId}
              selectedDirectoryPath={selectedDirectoryPath}
              onFileSelect={onFileSelect}
              onDirectoryClick={handleDirectoryClick}
              expandedPaths={expandedPaths}
              toggleExpanded={toggleExpanded}
              selectedFileRef={selectedFileRef}
              selectedDirRef={selectedDirRef}
            />
          ))}
        </List>
      )}
    </Box>
  )
}

export default FileTree
