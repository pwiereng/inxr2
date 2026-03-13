import { useMemo } from 'react'
import { useTheme } from '@mui/material/styles'
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Typography,
} from '@mui/material'
import FolderIcon from '@mui/icons-material/Folder'
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'

import type { TreeNode } from '@/lib/api'
import { FileTypeIcon } from '@/components/FileTree/file-icons'

interface DirectoryListingProps {
  /** All tree nodes from the repository */
  treeNodes: TreeNode[]
  /** Current directory path — null/empty for root */
  directoryPath: string | null
  /** Called when a file is clicked */
  onFileSelect: (path: string) => void
  /** Called when a directory is clicked */
  onDirectorySelect: (path: string) => void
  /** Called when ".." is clicked to go to parent (root if no parent) */
  onParentClick: () => void
}

/**
 * Find the children of a directory path within the tree.
 * Returns root nodes if directoryPath is null/empty.
 */
function findDirectoryChildren(nodes: TreeNode[], directoryPath: string | null): TreeNode[] {
  if (!directoryPath) return nodes

  // Walk the tree to find the target directory
  const parts = directoryPath.split('/')
  let current = nodes

  for (const part of parts) {
    const found = current.find((n) => n.name === part && n.type === 'directory')
    if (!found?.children) return []
    current = found.children
  }

  return current
}

export function DirectoryListing({
  treeNodes,
  directoryPath,
  onFileSelect,
  onDirectorySelect,
  onParentClick,
}: DirectoryListingProps): React.ReactElement {
  const theme = useTheme()

  const children = useMemo(
    () => findDirectoryChildren(treeNodes, directoryPath),
    [treeNodes, directoryPath]
  )

  // Group directories first, then files (each group's order comes from the tree API)
  const sorted = useMemo(() => {
    const dirs = children.filter((n) => n.type === 'directory')
    const files = children.filter((n) => n.type === 'file')
    return [...dirs, ...files]
  }, [children])

  if (sorted.length === 0 && !directoryPath) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">This directory is empty</Typography>
      </Box>
    )
  }

  return (
    <TableContainer sx={{ flex: 1, overflow: 'auto' }}>
      <Table size="small" sx={{ tableLayout: 'auto' }}>
        <TableBody>
          {directoryPath && (
            <TableRow hover onClick={onParentClick} sx={{ cursor: 'pointer' }}>
              <TableCell sx={{ width: 32, px: 1.5, py: 0.75 }}>
                <FolderIcon
                  fontSize="small"
                  sx={{ color: theme.palette.fileTree.folder, verticalAlign: 'middle' }}
                />
              </TableCell>
              <TableCell sx={{ px: 1, py: 0.75 }}>
                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '13px',
                    color: 'primary.main',
                  }}
                >
                  ..
                </Typography>
              </TableCell>
            </TableRow>
          )}
          {sorted.length === 0 && (
            <TableRow>
              <TableCell colSpan={2} sx={{ px: 1.5, py: 2, textAlign: 'center' }}>
                <Typography color="text.secondary">This directory is empty</Typography>
              </TableCell>
            </TableRow>
          )}
          {sorted.map((node) => {
            const isDirectory = node.type === 'directory'
            return (
              <TableRow
                key={node.path}
                hover
                onClick={() =>
                  isDirectory ? onDirectorySelect(node.path) : onFileSelect(node.path)
                }
                sx={{
                  cursor: 'pointer',
                  '&:last-child td': { borderBottom: 0 },
                }}
              >
                <TableCell sx={{ width: 32, px: 1.5, py: 0.75 }}>
                  {isDirectory ? (
                    <FolderIcon
                      fontSize="small"
                      sx={{ color: theme.palette.fileTree.folder, verticalAlign: 'middle' }}
                    />
                  ) : (
                    <FileTypeIcon
                      filename={node.name}
                      language={node.language}
                      fontSize="small"
                      fallback={
                        <InsertDriveFileIcon
                          fontSize="small"
                          sx={{
                            color: theme.palette.fileTree.defaultFile,
                            verticalAlign: 'middle',
                          }}
                        />
                      }
                    />
                  )}
                </TableCell>
                <TableCell sx={{ px: 1, py: 0.75 }}>
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: 'monospace',
                      fontSize: '13px',
                      color: isDirectory ? 'primary.main' : 'text.primary',
                    }}
                  >
                    {node.name}
                    {isDirectory ? '/' : ''}
                  </Typography>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
