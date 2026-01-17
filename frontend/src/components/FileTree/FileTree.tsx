import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Typography,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Collapse,
  CircularProgress,
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

import type { TreeNode } from '@/lib/api';

// Find a file in the tree by its ID and return the path to it
function findFilePathById(nodes: TreeNode[], fileId: number): string | null {
  for (const node of nodes) {
    if (node.file_id === fileId) {
      return node.path;
    }
    if (node.children) {
      const found = findFilePathById(node.children, fileId);
      if (found) return found;
    }
  }
  return null;
}

// Get all parent directory paths for a given file path
function getParentPaths(filePath: string): string[] {
  const parts = filePath.split('/');
  const paths: string[] = [];
  for (let i = 1; i < parts.length; i++) {
    paths.push(parts.slice(0, i).join('/'));
  }
  return paths;
}

interface FileTreeProps {
  nodes: TreeNode[];
  selectedFileId?: number | null;
  onFileSelect?: (fileId: number, path: string) => void;
  loading?: boolean;
}

interface TreeNodeItemProps {
  node: TreeNode;
  level: number;
  selectedFileId?: number | null;
  onFileSelect?: (fileId: number, path: string) => void;
  expandedPaths: Set<string>;
  toggleExpanded: (path: string) => void;
  selectedRef?: React.RefObject<HTMLDivElement>;
}

// Get file icon color based on language
function getFileColor(language: string | null): string {
  const colors: Record<string, string> = {
    python: '#3572A5',
    typescript: '#3178C6',
    javascript: '#F7DF1E',
    tsx: '#3178C6',
    jsx: '#F7DF1E',
    json: '#292929',
    yaml: '#CB171E',
    markdown: '#083FA1',
    css: '#563D7C',
    html: '#E34F26',
  };
  return language ? colors[language.toLowerCase()] || '#6e7681' : '#6e7681';
}

function TreeNodeItem({
  node,
  level,
  selectedFileId,
  onFileSelect,
  expandedPaths,
  toggleExpanded,
  selectedRef,
}: TreeNodeItemProps) {
  const isExpanded = expandedPaths.has(node.path);
  const isDirectory = node.type === 'directory';
  const isSelected = node.file_id === selectedFileId;

  const handleClick = () => {
    if (isDirectory) {
      toggleExpanded(node.path);
    } else if (node.file_id && onFileSelect) {
      onFileSelect(node.file_id, node.path);
    }
  };

  return (
    <>
      <ListItemButton
        ref={isSelected ? selectedRef : undefined}
        onClick={handleClick}
        selected={isSelected}
        sx={{
          pl: 1 + level * 2,
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
        {/* Expand/collapse icon for directories */}
        {isDirectory && (
          <ListItemIcon sx={{ minWidth: 24 }}>
            {isExpanded ? (
              <ExpandMoreIcon fontSize="small" sx={{ color: 'text.secondary' }} />
            ) : (
              <ChevronRightIcon fontSize="small" sx={{ color: 'text.secondary' }} />
            )}
          </ListItemIcon>
        )}

        {/* File/folder icon */}
        <ListItemIcon sx={{ minWidth: 28 }}>
          {isDirectory ? (
            isExpanded ? (
              <FolderOpenIcon fontSize="small" sx={{ color: '#dcb67a' }} />
            ) : (
              <FolderIcon fontSize="small" sx={{ color: '#dcb67a' }} />
            )
          ) : (
            <InsertDriveFileIcon
              fontSize="small"
              sx={{ color: getFileColor(node.language) }}
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
                onFileSelect={onFileSelect}
                expandedPaths={expandedPaths}
                toggleExpanded={toggleExpanded}
                selectedRef={selectedRef}
              />
            ))}
          </List>
        </Collapse>
      )}
    </>
  );
}

export function FileTree({
  nodes,
  selectedFileId,
  onFileSelect,
  loading = false,
}: FileTreeProps) {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const selectedRef = useRef<HTMLDivElement>(null!);

  const toggleExpanded = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  // Auto-expand path and scroll to selected file when selectedFileId changes
  useEffect(() => {
    if (selectedFileId && nodes.length > 0) {
      const filePath = findFilePathById(nodes, selectedFileId);
      if (filePath) {
        const parentPaths = getParentPaths(filePath);
        // Expand all parent directories
        setExpandedPaths((prev) => {
          const next = new Set(prev);
          parentPaths.forEach((p) => next.add(p));
          return next;
        });
        // Scroll into view after a short delay to allow expansion animation
        setTimeout(() => {
          selectedRef.current?.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
          });
        }, 100);
      }
    }
  }, [selectedFileId, nodes]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (nodes.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          No files found
        </Typography>
      </Box>
    );
  }

  return (
    <List dense disablePadding sx={{ overflow: 'auto' }}>
      {nodes.map((node) => (
        <TreeNodeItem
          key={node.path}
          node={node}
          level={0}
          selectedFileId={selectedFileId}
          onFileSelect={onFileSelect}
          expandedPaths={expandedPaths}
          toggleExpanded={toggleExpanded}
          selectedRef={selectedRef}
        />
      ))}
    </List>
  );
}

export default FileTree;
