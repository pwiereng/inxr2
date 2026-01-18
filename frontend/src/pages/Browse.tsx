import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Breadcrumbs,
  Link,
  CircularProgress,
  Alert,
  Chip,
  Select,
  MenuItem,
  FormControl,
} from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import HomeIcon from '@mui/icons-material/Home'
import FolderIcon from '@mui/icons-material/Folder'

import { CodeViewer } from '@/components/CodeViewer'
import { FileTree } from '@/components/FileTree'
import { SymbolSearch } from '@/components/SymbolSearch'
import { ReferencesPanel } from '@/components/ReferencesPanel'
import {
  getRepositories,
  getRepositoryByName,
  getRepositoryTreeByName,
  getFileContentByPath,
  getFileSymbolsByPath,
  getFileReferencesByPath,
  getSymbol,
  type Repository,
  type TreeNode,
  type FileContent,
  type FileSymbol,
  type FileReference,
  type Symbol,
} from '@/lib/api'

export default function Browse() {
  const { repoName, '*': splatPath } = useParams<{ repoName: string; '*': string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // Get file path from URL path (splat param) and line from query params
  const filePath = splatPath || null
  const highlightLine = searchParams.get('line')
    ? parseInt(searchParams.get('line')!, 10)
    : undefined

  // State
  const [allRepositories, setAllRepositories] = useState<Repository[]>([])
  const [repository, setRepository] = useState<Repository | null>(null)
  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([])
  const [fileContent, setFileContent] = useState<FileContent | null>(null)
  const [fileSymbols, setFileSymbols] = useState<FileSymbol[]>([])
  const [fileReferences, setFileReferences] = useState<FileReference[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<Symbol | null>(null)
  const [isDirectDefinition, setIsDirectDefinition] = useState(false)
  const [searchByName, setSearchByName] = useState<{ name: string; repositoryId: number } | null>(
    null
  )

  // UI state
  const [drawerOpen, setDrawerOpen] = useState(true)
  const [refsPanelOpen, setRefsPanelOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [fileLoading, setFileLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Load all repositories (for selector dropdown)
  useEffect(() => {
    getRepositories().then(setAllRepositories).catch(console.error)
  }, [])

  // Handle repository switch
  const handleRepositoryChange = (newRepoName: string) => {
    navigate(`/browse/${encodeURIComponent(newRepoName)}`)
  }

  // Load repository and tree by name
  useEffect(() => {
    if (!repoName) return

    const loadRepository = async () => {
      setLoading(true)
      setError(null)
      try {
        const [repo, tree] = await Promise.all([
          getRepositoryByName(repoName),
          getRepositoryTreeByName(repoName),
        ])
        setRepository(repo)
        setTreeNodes(tree.root)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load repository')
      } finally {
        setLoading(false)
      }
    }

    loadRepository()
  }, [repoName])

  // Load file content when file path changes
  useEffect(() => {
    if (!filePath || !repoName) {
      setFileContent(null)
      setFileSymbols([])
      setFileReferences([])
      return
    }

    const loadFile = async () => {
      setFileLoading(true)
      try {
        const [content, symbols, references] = await Promise.all([
          getFileContentByPath(repoName, filePath),
          getFileSymbolsByPath(repoName, filePath),
          getFileReferencesByPath(repoName, filePath),
        ])
        setFileContent(content)
        setFileSymbols(symbols.symbols)
        setFileReferences(references.references)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load file')
      } finally {
        setFileLoading(false)
      }
    }

    loadFile()
  }, [repoName, filePath])

  // Handle file selection from tree
  const handleFileSelect = (path: string) => {
    navigate(`/browse/${encodeURIComponent(repoName!)}/${path}`)
  }

  // Handle symbol selection from search
  const handleSymbolSelect = async (symbol: Symbol) => {
    if (symbol.file_path) {
      navigate(
        `/browse/${encodeURIComponent(repoName!)}/${symbol.file_path}?line=${symbol.start_line}`
      )
    }
  }

  // Handle symbol click in code viewer (clicking on a definition)
  const handleSymbolClick = async (fileSymbol: FileSymbol) => {
    try {
      const symbol = await getSymbol(fileSymbol.id)
      setSelectedSymbol(symbol)
      setSearchByName(null)
      setIsDirectDefinition(true) // We clicked directly on the definition
      setRefsPanelOpen(true)
      setSearchQuery(symbol.name)
    } catch (err) {
      console.error('Failed to get symbol:', err)
    }
  }

  // Handle reference click in code viewer (clicking on a usage/reference)
  const handleCodeReferenceClick = async (ref: FileReference) => {
    if (!ref.target_symbol_id) {
      // Unresolved reference - search by name to find possible definitions
      if (repository?.id) {
        setSelectedSymbol(null)
        setSearchByName({ name: ref.reference_text, repositoryId: repository.id })
        setIsDirectDefinition(false)
        setRefsPanelOpen(true)
        setSearchQuery(ref.reference_text)
      }
      return
    }
    try {
      const symbol = await getSymbol(ref.target_symbol_id)
      setSelectedSymbol(symbol)
      setSearchByName(null)
      setIsDirectDefinition(false) // We clicked on a reference, show all possible definitions
      setRefsPanelOpen(true)
      setSearchQuery(symbol.name)
    } catch (err) {
      console.error('Failed to get symbol for reference:', err)
    }
  }

  // Handle click in references panel (jump to reference location)
  const handleRefPanelClick = (reference: {
    source_file_path: string | null
    source_line: number
  }) => {
    if (reference.source_file_path) {
      navigate(
        `/browse/${encodeURIComponent(repoName!)}/${reference.source_file_path}?line=${reference.source_line}`
      )
    }
  }

  // Handle click on definition in references panel
  const handleDefinitionClick = (sym: Symbol) => {
    if (sym.file_path) {
      navigate(`/browse/${encodeURIComponent(repoName!)}/${sym.file_path}?line=${sym.start_line}`)
    }
  }

  // Handle line click (update URL)
  const handleLineClick = (line: number) => {
    if (filePath) {
      navigate(`/browse/${encodeURIComponent(repoName!)}/${filePath}?line=${line}`, {
        replace: true,
      })
    }
  }

  if (loading) {
    return (
      <Box
        sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}
      >
        <CircularProgress />
      </Box>
    )
  }

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* App Bar */}
      <AppBar
        position="static"
        sx={{
          bgcolor: 'background.paper',
          borderBottom: 1,
          borderColor: 'divider',
        }}
        elevation={0}
      >
        <Toolbar sx={{ gap: 2 }}>
          <IconButton edge="start" color="inherit" onClick={() => setDrawerOpen(!drawerOpen)}>
            {drawerOpen ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>

          {/* Repository Selector */}
          {allRepositories.length > 1 ? (
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <Select
                value={repoName || ''}
                onChange={(e) => handleRepositoryChange(e.target.value as string)}
                displayEmpty
                sx={{
                  '& .MuiSelect-select': {
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    py: 0.5,
                  },
                }}
              >
                {allRepositories.map((repo) => (
                  <MenuItem key={repo.id} value={repo.name}>
                    <FolderIcon fontSize="small" sx={{ mr: 1 }} />
                    {repo.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          ) : (
            repository && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <FolderIcon fontSize="small" />
                <Typography variant="body1">{repository.name}</Typography>
              </Box>
            )
          )}

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
            {fileContent && (
              <Typography color="text.primary" sx={{ fontFamily: 'monospace' }}>
                {fileContent.path.split('/').pop()}
              </Typography>
            )}
          </Breadcrumbs>

          {/* Symbol Search */}
          <SymbolSearch
            repositoryId={repository?.id}
            onSymbolSelect={handleSymbolSelect}
            value={searchQuery}
            onValueChange={setSearchQuery}
          />
        </Toolbar>
      </AppBar>

      {/* Main Content with Flexbox Layout */}
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* File Tree Panel */}
        {drawerOpen && (
          <Box
            sx={{
              width: 220,
              minWidth: 150,
              maxWidth: 350,
              height: '100%',
              overflow: 'auto',
              borderRight: 1,
              borderColor: 'divider',
              flexShrink: 0,
              resize: 'horizontal',
            }}
          >
            <FileTree
              nodes={treeNodes}
              selectedFileId={fileContent?.id ?? null}
              onFileSelect={handleFileSelect}
            />
          </Box>
        )}

        {/* Code Viewer Panel */}
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
            overflow: 'hidden',
          }}
        >
          {fileLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
              <CircularProgress />
            </Box>
          ) : fileContent ? (
            <>
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
                  flexShrink: 0,
                }}
              >
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                  {fileContent.path}
                </Typography>
                {fileContent.language && <Chip label={fileContent.language} size="small" />}
                <Typography variant="caption" color="text.secondary">
                  {fileContent.line_count} lines
                </Typography>
              </Box>

              {/* Code Viewer */}
              <Box sx={{ flex: 1, overflow: 'auto' }}>
                <CodeViewer
                  content={fileContent.content}
                  language={fileContent.language}
                  symbols={fileSymbols}
                  references={fileReferences}
                  highlightLine={highlightLine}
                  onSymbolClick={handleSymbolClick}
                  onReferenceClick={handleCodeReferenceClick}
                  onLineClick={handleLineClick}
                />
              </Box>
            </>
          ) : (
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                flex: 1,
                color: 'text.secondary',
              }}
            >
              <Typography>Select a file from the tree to view its contents</Typography>
            </Box>
          )}
        </Box>

        {/* References Panel */}
        {refsPanelOpen && (
          <Box
            sx={{
              width: 280,
              minWidth: 200,
              maxWidth: 450,
              height: '100%',
              borderLeft: 1,
              borderColor: 'divider',
              flexShrink: 0,
              resize: 'horizontal',
              direction: 'rtl' /* Makes resize handle appear on left */,
            }}
          >
            <Box sx={{ direction: 'ltr', height: '100%' }}>
              <ReferencesPanel
                symbol={selectedSymbol}
                isDirectDefinition={isDirectDefinition}
                searchByName={searchByName}
                onReferenceClick={handleRefPanelClick}
                onDefinitionClick={handleDefinitionClick}
                onClose={() => {
                  setRefsPanelOpen(false)
                  setSelectedSymbol(null)
                  setIsDirectDefinition(false)
                  setSearchByName(null)
                }}
              />
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  )
}
