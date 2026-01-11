import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  Breadcrumbs,
  Link,
  CircularProgress,
  Alert,
  Chip,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import HomeIcon from '@mui/icons-material/Home';
import FolderIcon from '@mui/icons-material/Folder';

import { CodeViewer } from '@/components/CodeViewer';
import { FileTree } from '@/components/FileTree';
import { SymbolSearch } from '@/components/SymbolSearch';
import { ReferencesPanel } from '@/components/ReferencesPanel';
import {
  getRepository,
  getRepositoryTree,
  getFileContent,
  getFileSymbols,
  getSymbol,
  type Repository,
  type TreeNode,
  type FileContent,
  type FileSymbol,
  type Symbol,
} from '@/lib/api';

const DRAWER_WIDTH = 280;
const REFS_PANEL_WIDTH = 300;

export default function Browse() {
  const { repositoryId, fileId } = useParams<{ repositoryId: string; fileId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // State
  const [repository, setRepository] = useState<Repository | null>(null);
  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([]);
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [fileSymbols, setFileSymbols] = useState<FileSymbol[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<Symbol | null>(null);

  // UI state
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [refsPanelOpen, setRefsPanelOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [fileLoading, setFileLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get highlight line from URL
  const highlightLine = searchParams.get('line') ? parseInt(searchParams.get('line')!, 10) : undefined;

  // Load repository and tree
  useEffect(() => {
    if (!repositoryId) return;

    const loadRepository = async () => {
      setLoading(true);
      setError(null);
      try {
        const [repo, tree] = await Promise.all([
          getRepository(parseInt(repositoryId, 10)),
          getRepositoryTree(parseInt(repositoryId, 10)),
        ]);
        setRepository(repo);
        setTreeNodes(tree.root);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load repository');
      } finally {
        setLoading(false);
      }
    };

    loadRepository();
  }, [repositoryId]);

  // Load file content when fileId changes
  useEffect(() => {
    if (!fileId) {
      setFileContent(null);
      setFileSymbols([]);
      return;
    }

    const loadFile = async () => {
      setFileLoading(true);
      try {
        const [content, symbols] = await Promise.all([
          getFileContent(parseInt(fileId, 10)),
          getFileSymbols(parseInt(fileId, 10)),
        ]);
        setFileContent(content);
        setFileSymbols(symbols.symbols);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load file');
      } finally {
        setFileLoading(false);
      }
    };

    loadFile();
  }, [fileId]);

  // Handle file selection from tree
  const handleFileSelect = (selectedFileId: number, _path: string) => {
    navigate(`/browse/${repositoryId}/file/${selectedFileId}`);
  };

  // Handle symbol selection from search
  const handleSymbolSelect = async (symbol: Symbol) => {
    // Navigate to the file containing the symbol
    navigate(`/browse/${repositoryId}/file/${symbol.file_id}?line=${symbol.start_line}`);
  };

  // Handle symbol click in code viewer (find references)
  const handleSymbolClick = async (fileSymbol: FileSymbol) => {
    try {
      const symbol = await getSymbol(fileSymbol.id);
      setSelectedSymbol(symbol);
      setRefsPanelOpen(true);
    } catch (err) {
      console.error('Failed to get symbol:', err);
    }
  };

  // Handle reference click
  const handleReferenceClick = (reference: { source_file_id: number; source_line: number }) => {
    navigate(`/browse/${repositoryId}/file/${reference.source_file_id}?line=${reference.source_line}`);
  };

  // Handle line click (update URL)
  const handleLineClick = (line: number) => {
    navigate(`/browse/${repositoryId}/file/${fileId}?line=${line}`, { replace: true });
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          bgcolor: 'background.paper',
          borderBottom: 1,
          borderColor: 'divider',
        }}
        elevation={0}
      >
        <Toolbar sx={{ gap: 2 }}>
          <IconButton
            edge="start"
            color="inherit"
            onClick={() => setDrawerOpen(!drawerOpen)}
          >
            {drawerOpen ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>

          {/* Breadcrumbs */}
          <Breadcrumbs sx={{ flex: 1 }}>
            <Link
              href="/"
              underline="hover"
              color="inherit"
              sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
            >
              <HomeIcon fontSize="small" />
              Home
            </Link>
            {repository && (
              <Link
                href={`/browse/${repositoryId}`}
                underline="hover"
                color="inherit"
                sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
              >
                <FolderIcon fontSize="small" />
                {repository.name}
              </Link>
            )}
            {fileContent && (
              <Typography color="text.primary" sx={{ fontFamily: 'monospace' }}>
                {fileContent.path.split('/').pop()}
              </Typography>
            )}
          </Breadcrumbs>

          {/* Symbol Search */}
          <SymbolSearch
            repositoryId={repositoryId ? parseInt(repositoryId, 10) : undefined}
            onSymbolSelect={handleSymbolSelect}
          />
        </Toolbar>
      </AppBar>

      {/* File Tree Drawer */}
      <Drawer
        variant="persistent"
        anchor="left"
        open={drawerOpen}
        sx={{
          width: drawerOpen ? DRAWER_WIDTH : 0,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
            top: 64,
            height: 'calc(100% - 64px)',
          },
        }}
      >
        <Box sx={{ overflow: 'auto', height: '100%' }}>
          <FileTree
            nodes={treeNodes}
            selectedFileId={fileId ? parseInt(fileId, 10) : null}
            onFileSelect={handleFileSelect}
          />
        </Box>
      </Drawer>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          mt: 8,
          ml: drawerOpen ? `${DRAWER_WIDTH}px` : 0,
          mr: refsPanelOpen ? `${REFS_PANEL_WIDTH}px` : 0,
          transition: (theme) =>
            theme.transitions.create(['margin'], {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.leavingScreen,
            }),
          height: 'calc(100vh - 64px)',
          overflow: 'auto',
        }}
      >
        {fileLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <CircularProgress />
          </Box>
        ) : fileContent ? (
          <Box sx={{ height: '100%' }}>
            {/* File header */}
            <Box
              sx={{
                px: 2,
                py: 1,
                bgcolor: 'background.paper',
                borderBottom: 1,
                borderColor: 'divider',
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}
            >
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {fileContent.path}
              </Typography>
              {fileContent.language && (
                <Chip label={fileContent.language} size="small" />
              )}
              <Typography variant="caption" color="text.secondary">
                {fileContent.line_count} lines
              </Typography>
            </Box>

            {/* Code Viewer */}
            <Box sx={{ height: 'calc(100% - 48px)', overflow: 'auto' }}>
              <CodeViewer
                content={fileContent.content}
                language={fileContent.language}
                symbols={fileSymbols}
                highlightLine={highlightLine}
                onSymbolClick={handleSymbolClick}
                onLineClick={handleLineClick}
              />
            </Box>
          </Box>
        ) : (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '100%',
              color: 'text.secondary',
            }}
          >
            <Typography>Select a file from the tree to view its contents</Typography>
          </Box>
        )}
      </Box>

      {/* References Panel */}
      <Drawer
        variant="persistent"
        anchor="right"
        open={refsPanelOpen}
        sx={{
          width: refsPanelOpen ? REFS_PANEL_WIDTH : 0,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: REFS_PANEL_WIDTH,
            boxSizing: 'border-box',
            top: 64,
            height: 'calc(100% - 64px)',
          },
        }}
      >
        <ReferencesPanel
          symbol={selectedSymbol}
          onReferenceClick={handleReferenceClick}
          onClose={() => {
            setRefsPanelOpen(false);
            setSelectedSymbol(null);
          }}
        />
      </Drawer>
    </Box>
  );
}
