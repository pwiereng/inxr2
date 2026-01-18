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
  Tooltip,
} from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import HomeIcon from '@mui/icons-material/Home'
import FolderIcon from '@mui/icons-material/Folder'
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import CloseIcon from '@mui/icons-material/Close'
import EditIcon from '@mui/icons-material/Edit'

import { CodeViewer } from '@/components/CodeViewer'
import { DiffCodeViewer } from '@/components/DiffCodeViewer'
import { FileTree } from '@/components/FileTree'
import { SymbolSearch } from '@/components/SymbolSearch'
import { ReferencesPanel } from '@/components/ReferencesPanel'
import { VersionSelector } from '@/components/VersionSelector'
import {
  getRepositories,
  getRepositoryByName,
  getRepositoryTreeByName,
  getFileContentByPathAtCommit,
  getFileSymbolsByPath,
  getFileReferencesByPath,
  getSymbol,
  getFileHistory,
  type Repository,
  type TreeNode,
  type FileContent,
  type FileSymbol,
  type FileReference,
  type Symbol,
  type FileVersion,
} from '@/lib/api'

export default function Browse() {
  const { repoName, '*': splatPath } = useParams<{ repoName: string; '*': string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // Get file path from URL path (splat param) and line/commit from query params
  const filePath = splatPath || null
  const highlightLine = searchParams.get('line')
    ? parseInt(searchParams.get('line')!, 10)
    : undefined
  const selectedCommit = searchParams.get('commit')

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

  // Diff mode state
  const [diffMode, setDiffMode] = useState(false)
  const [diffCommit, setDiffCommit] = useState<string | null>(null)
  const [diffContent, setDiffContent] = useState<FileContent | null>(null)
  const [diffSymbols, setDiffSymbols] = useState<FileSymbol[]>([])
  const [diffReferences, setDiffReferences] = useState<FileReference[]>([])
  const [activePanel, setActivePanel] = useState<'left' | 'right'>('left')
  const [fileVersions, setFileVersions] = useState<FileVersion[]>([])
  const [treePanel, setTreePanel] = useState<'left' | 'right'>('left')
  const [refPanel, setRefPanel] = useState<'left' | 'right'>('left')

  // UI state
  const [drawerOpen, setDrawerOpen] = useState(true)
  const [refsPanelOpen, setRefsPanelOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [fileLoading, setFileLoading] = useState(false)
  const [diffLoading, setDiffLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // The commit that the file tree is showing (based on selected panel in diff mode)
  const leftCommit = selectedCommit || fileVersions[0]?.commit_hash
  const rightCommit = diffCommit
  const treeCommit = diffMode ? (treePanel === 'left' ? leftCommit : rightCommit) : selectedCommit

  // The commit for the references panel
  const refCommit = diffMode ? (refPanel === 'left' ? leftCommit : rightCommit) : selectedCommit

  // Load all repositories (for selector dropdown)
  useEffect(() => {
    getRepositories().then(setAllRepositories).catch(console.error)
  }, [])

  // Handle repository switch
  const handleRepositoryChange = (newRepoName: string) => {
    navigate(`/browse/${encodeURIComponent(newRepoName)}`)
  }

  // Load repository by name (only when repo changes)
  useEffect(() => {
    if (!repoName) return

    const loadRepository = async () => {
      setLoading(true)
      setError(null)
      try {
        const repo = await getRepositoryByName(repoName)
        setRepository(repo)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load repository')
      } finally {
        setLoading(false)
      }
    }

    loadRepository()
  }, [repoName])

  // Load tree (commit-aware for time travel) - separate from repository loading
  useEffect(() => {
    if (!repoName) return

    const loadTree = async () => {
      try {
        const tree = await getRepositoryTreeByName(repoName, treeCommit || undefined)
        setTreeNodes(tree.root)
      } catch (err) {
        console.error('Failed to load tree:', err)
      }
    }

    loadTree()
  }, [repoName, treeCommit])

  // Load file versions when file changes
  useEffect(() => {
    if (!filePath || !repoName) {
      setFileVersions([])
      return
    }

    getFileHistory(repoName, filePath)
      .then((response) => setFileVersions(response.versions))
      .catch(() => setFileVersions([]))
  }, [repoName, filePath])

  // Load file content when file path or commit changes
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
          getFileContentByPathAtCommit(repoName, filePath, selectedCommit || undefined),
          getFileSymbolsByPath(repoName, filePath, selectedCommit || undefined),
          getFileReferencesByPath(repoName, filePath, selectedCommit || undefined),
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
  }, [repoName, filePath, selectedCommit])

  // Load diff content when diff commit changes
  useEffect(() => {
    if (!diffMode || !diffCommit || !filePath || !repoName) {
      setDiffContent(null)
      setDiffSymbols([])
      setDiffReferences([])
      return
    }

    const loadDiffFile = async () => {
      setDiffLoading(true)
      try {
        const [content, symbols, references] = await Promise.all([
          getFileContentByPathAtCommit(repoName, filePath, diffCommit),
          getFileSymbolsByPath(repoName, filePath, diffCommit),
          getFileReferencesByPath(repoName, filePath, diffCommit),
        ])
        setDiffContent(content)
        setDiffSymbols(symbols.symbols)
        setDiffReferences(references.references)
      } catch (err) {
        console.error('Failed to load diff file:', err)
        setDiffContent(null)
        setDiffSymbols([])
        setDiffReferences([])
      } finally {
        setDiffLoading(false)
      }
    }

    loadDiffFile()
  }, [repoName, filePath, diffMode, diffCommit])

  // Handle file selection from tree
  const handleFileSelect = (path: string) => {
    const params = new URLSearchParams()
    // Preserve commit when navigating to a different file (same vintage)
    if (selectedCommit) params.set('commit', selectedCommit)
    const query = params.toString()
    // Exit diff mode when selecting a new file
    setDiffMode(false)
    setDiffCommit(null)
    navigate(`/browse/${encodeURIComponent(repoName!)}/${path}${query ? `?${query}` : ''}`)
  }

  // Handle symbol selection from search
  const handleSymbolSelect = async (symbol: Symbol) => {
    if (symbol.file_path) {
      const params = new URLSearchParams()
      params.set('line', symbol.start_line.toString())
      // Preserve commit when navigating to a symbol (same vintage)
      if (selectedCommit) params.set('commit', selectedCommit)
      // Exit diff mode when selecting a symbol
      setDiffMode(false)
      setDiffCommit(null)
      navigate(`/browse/${encodeURIComponent(repoName!)}/${symbol.file_path}?${params}`)
    }
  }

  // Handle symbol click in code viewer (clicking on a definition)
  const handleSymbolClick = async (fileSymbol: FileSymbol) => {
    try {
      const symbol = await getSymbol(fileSymbol.id)
      setSelectedSymbol(symbol)
      setSearchByName(null)
      setIsDirectDefinition(true)
      setRefsPanelOpen(true)
      setSearchQuery(symbol.name)
    } catch (err) {
      console.error('Failed to get symbol:', err)
    }
  }

  // Handle symbol click in diff mode
  const handleDiffSymbolClick = async (fileSymbol: FileSymbol, panel: 'left' | 'right') => {
    setActivePanel(panel)
    setRefPanel(panel) // Sync refs panel to show references for the clicked panel's version
    await handleSymbolClick(fileSymbol)
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
      setIsDirectDefinition(false)
      setRefsPanelOpen(true)
      setSearchQuery(symbol.name)
    } catch (err) {
      console.error('Failed to get symbol for reference:', err)
    }
  }

  // Handle reference click in diff mode
  const handleDiffReferenceClick = async (ref: FileReference, panel: 'left' | 'right') => {
    setActivePanel(panel)
    setRefPanel(panel) // Sync refs panel to show references for the clicked panel's version
    await handleCodeReferenceClick(ref)
  }

  // Handle click in references panel (jump to reference location)
  const handleRefPanelClick = (reference: {
    source_file_path: string | null
    source_line: number
  }) => {
    if (reference.source_file_path) {
      const params = new URLSearchParams()
      params.set('line', reference.source_line.toString())
      // Use the commit from the active panel in diff mode
      const commitToUse = diffMode && activePanel === 'right' ? diffCommit : selectedCommit
      if (commitToUse) params.set('commit', commitToUse)
      // Exit diff mode when navigating
      setDiffMode(false)
      setDiffCommit(null)
      navigate(`/browse/${encodeURIComponent(repoName!)}/${reference.source_file_path}?${params}`)
    }
  }

  // Handle click on definition in references panel
  const handleDefinitionClick = (sym: Symbol) => {
    if (sym.file_path) {
      const params = new URLSearchParams()
      params.set('line', sym.start_line.toString())
      // Use the commit from the active panel in diff mode
      const commitToUse = diffMode && activePanel === 'right' ? diffCommit : selectedCommit
      if (commitToUse) params.set('commit', commitToUse)
      // Exit diff mode when navigating
      setDiffMode(false)
      setDiffCommit(null)
      navigate(`/browse/${encodeURIComponent(repoName!)}/${sym.file_path}?${params}`)
    }
  }

  // Handle line click (update URL)
  const handleLineClick = (line: number) => {
    if (filePath) {
      const params = new URLSearchParams()
      params.set('line', line.toString())
      if (selectedCommit) params.set('commit', selectedCommit)
      navigate(`/browse/${encodeURIComponent(repoName!)}/${filePath}?${params}`, {
        replace: true,
      })
    }
  }

  // Handle line click in diff mode
  const handleDiffLineClick = (line: number, panel: 'left' | 'right') => {
    setActivePanel(panel)
    handleLineClick(line)
  }

  // Handle version change (time travel)
  const handleVersionChange = (commitHash: string | null) => {
    if (filePath) {
      const params = new URLSearchParams()
      if (highlightLine) params.set('line', highlightLine.toString())
      if (commitHash) params.set('commit', commitHash)
      navigate(`/browse/${encodeURIComponent(repoName!)}/${filePath}?${params}`)
    }
  }

  // Enter diff mode
  const handleEnterDiffMode = () => {
    setDiffMode(true)
    // Default to comparing with the previous version if available
    const currentIndex = fileVersions.findIndex(
      (v) => v.commit_hash === (selectedCommit || fileVersions[0]?.commit_hash)
    )
    if (currentIndex >= 0 && currentIndex < fileVersions.length - 1) {
      setDiffCommit(fileVersions[currentIndex + 1]?.commit_hash || null)
    } else if (fileVersions.length > 1) {
      // Default to second version
      setDiffCommit(fileVersions[1]?.commit_hash || null)
    }
  }

  // Exit diff mode
  const handleExitDiffMode = () => {
    setDiffMode(false)
    setDiffCommit(null)
    setDiffContent(null)
    setDiffSymbols([])
    setDiffReferences([])
    setTreePanel('left')
    setRefPanel('left')
  }

  // Handle closing a panel in diff view
  const handleClosePanel = (panel: 'left' | 'right') => {
    if (panel === 'left') {
      // Keep the right panel's version
      if (diffCommit) {
        const params = new URLSearchParams()
        if (highlightLine) params.set('line', highlightLine.toString())
        params.set('commit', diffCommit)
        navigate(`/browse/${encodeURIComponent(repoName!)}/${filePath}?${params}`)
      }
    }
    // Closing right panel just exits diff mode keeping current version
    handleExitDiffMode()
  }

  // Handle diff version change
  const handleDiffVersionChange = (commitHash: string | null) => {
    setDiffCommit(commitHash)
  }

  // Get short hash for display
  const getShortHash = (hash: string | null | undefined) => {
    if (!hash) return 'latest'
    return hash.substring(0, 7)
  }

  // Parse date as UTC
  const parseAsUTC = (dateString: string): Date => {
    if (!dateString.endsWith('Z') && !dateString.includes('+') && !dateString.includes('-', 10)) {
      return new Date(dateString + 'Z')
    }
    return new Date(dateString)
  }

  // Format commit date for display
  const formatCommitDate = (dateString: string): string => {
    const date = parseAsUTC(dateString)
    const year = date.getUTCFullYear()
    const month = String(date.getUTCMonth() + 1).padStart(2, '0')
    const day = String(date.getUTCDate()).padStart(2, '0')
    const dateStr = `${year}${month}${day}`

    // Check if there are other commits on the same day
    const allDates = fileVersions.map((v) => v.commit_date)
    const sameDayCount = allDates.filter((d) => {
      const other = parseAsUTC(d)
      return (
        other.getUTCFullYear() === date.getUTCFullYear() &&
        other.getUTCMonth() === date.getUTCMonth() &&
        other.getUTCDate() === date.getUTCDate()
      )
    }).length

    if (sameDayCount > 1) {
      const hours = String(date.getUTCHours()).padStart(2, '0')
      const minutes = String(date.getUTCMinutes()).padStart(2, '0')
      return `${dateStr} ${hours}:${minutes} UTC`
    }

    return dateStr
  }

  // Check if a version has content changes from the previous version
  const hasContentChange = (version: FileVersion, index: number): boolean => {
    const prevVersion = fileVersions[index + 1]
    return !prevVersion || version.content_hash !== prevVersion.content_hash
  }

  // Get the current commit hash (selected or latest)
  const currentCommitHash = selectedCommit || fileVersions[0]?.commit_hash

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
              overflow: 'hidden',
              borderRight: 1,
              borderColor: 'divider',
              flexShrink: 0,
              resize: 'horizontal',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Tree version indicator / selector */}
            {(treeCommit || diffMode) && (
              <Box
                sx={{
                  px: 1,
                  py: 0.5,
                  bgcolor: 'action.selected',
                  borderBottom: 1,
                  borderColor: 'divider',
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                }}
              >
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Tree @
                </Typography>
                {diffMode ? (
                  <FormControl size="small" sx={{ minWidth: 80 }}>
                    <Select
                      value={treePanel}
                      onChange={(e) => setTreePanel(e.target.value as 'left' | 'right')}
                      sx={{
                        '& .MuiSelect-select': {
                          py: 0,
                          px: 0.5,
                          fontSize: '0.75rem',
                          fontFamily: 'monospace',
                        },
                        '& .MuiOutlinedInput-notchedOutline': {
                          border: 'none',
                        },
                      }}
                    >
                      <MenuItem value="left">
                        <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                          {getShortHash(leftCommit)} (left)
                        </Typography>
                      </MenuItem>
                      <MenuItem value="right">
                        <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                          {getShortHash(rightCommit)} (right)
                        </Typography>
                      </MenuItem>
                    </Select>
                  </FormControl>
                ) : (
                  <Typography
                    variant="caption"
                    sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                  >
                    {getShortHash(treeCommit)}
                  </Typography>
                )}
              </Box>
            )}
            <Box sx={{ flex: 1, overflow: 'auto' }}>
              <FileTree
                nodes={treeNodes}
                selectedFileId={fileContent?.id ?? null}
                onFileSelect={handleFileSelect}
              />
            </Box>
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
                  flexWrap: 'wrap',
                }}
              >
                <Typography variant="body2" sx={{ fontFamily: 'monospace', flex: 1 }}>
                  {fileContent.path}
                </Typography>
                {fileContent.language && <Chip label={fileContent.language} size="small" />}
                <Typography variant="caption" color="text.secondary">
                  {fileContent.line_count} lines
                </Typography>

                {/* Version selector and diff controls */}
                {repoName && filePath && (
                  <>
                    <VersionSelector
                      repoName={repoName}
                      filePath={filePath}
                      selectedCommit={selectedCommit}
                      onVersionChange={handleVersionChange}
                    />

                    {/* Diff controls */}
                    {!diffMode ? (
                      <Tooltip title="Compare versions">
                        <IconButton
                          size="small"
                          onClick={handleEnterDiffMode}
                          disabled={fileVersions.length < 2}
                          sx={{ ml: 0.5 }}
                        >
                          <CompareArrowsIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    ) : (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Typography variant="caption" color="text.secondary">
                          vs
                        </Typography>
                        <FormControl size="small">
                          <Select
                            value={diffCommit || ''}
                            onChange={(e) => handleDiffVersionChange(e.target.value || null)}
                            displayEmpty
                            sx={{
                              minWidth: 180,
                              '& .MuiSelect-select': {
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
                                py: 0.5,
                                fontSize: '0.875rem',
                              },
                            }}
                          >
                            {fileVersions
                              .filter((v) => v.commit_hash !== currentCommitHash)
                              .map((version) => {
                                const originalIndex = fileVersions.findIndex(
                                  (v) => v.commit_hash === version.commit_hash
                                )
                                const hasChange = hasContentChange(version, originalIndex)
                                const isSelected = version.commit_hash === diffCommit

                                return (
                                  <MenuItem
                                    key={version.commit_hash}
                                    value={version.commit_hash}
                                    sx={{
                                      bgcolor: isSelected ? 'action.selected' : 'transparent',
                                      borderLeft: isSelected ? 3 : 0,
                                      borderColor: 'primary.main',
                                      '&.Mui-selected': {
                                        bgcolor: 'action.selected',
                                      },
                                    }}
                                  >
                                    <Tooltip title={version.message} placement="left">
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        {hasChange && (
                                          <EditIcon
                                            sx={{ fontSize: '0.9rem', color: 'warning.main' }}
                                          />
                                        )}
                                        <Typography
                                          component="span"
                                          sx={{
                                            fontFamily: 'monospace',
                                            fontSize: '0.8rem',
                                            fontWeight: isSelected ? 600 : 400,
                                            color: isSelected ? 'primary.main' : 'text.primary',
                                          }}
                                        >
                                          {version.short_hash}
                                        </Typography>
                                        <Typography
                                          component="span"
                                          variant="caption"
                                          color="text.secondary"
                                        >
                                          {formatCommitDate(version.commit_date)}
                                        </Typography>
                                      </Box>
                                    </Tooltip>
                                  </MenuItem>
                                )
                              })}
                          </Select>
                        </FormControl>
                        <Tooltip title="Exit compare mode">
                          <IconButton size="small" onClick={handleExitDiffMode}>
                            <CloseIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    )}
                  </>
                )}
              </Box>

              {/* Code Viewer or Diff Viewer */}
              <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
                {diffMode && diffContent ? (
                  <DiffCodeViewer
                    leftContent={fileContent.content}
                    rightContent={diffContent.content}
                    leftLabel={`${getShortHash(selectedCommit || fileVersions[0]?.commit_hash)} (current)`}
                    rightLabel={`${getShortHash(diffCommit)} (compare)`}
                    language={fileContent.language}
                    leftSymbols={fileSymbols}
                    rightSymbols={diffSymbols}
                    leftReferences={fileReferences}
                    rightReferences={diffReferences}
                    highlightLine={highlightLine}
                    activePanel={activePanel}
                    onPanelClick={setActivePanel}
                    onSymbolClick={handleDiffSymbolClick}
                    onReferenceClick={handleDiffReferenceClick}
                    onLineClick={handleDiffLineClick}
                    onClosePanel={handleClosePanel}
                  />
                ) : diffMode && diffLoading ? (
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      flex: 1,
                    }}
                  >
                    <CircularProgress />
                  </Box>
                ) : (
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
                )}
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
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Box
              sx={{ direction: 'ltr', height: '100%', display: 'flex', flexDirection: 'column' }}
            >
              {/* Version selector for references in diff mode */}
              {diffMode && (
                <Box
                  sx={{
                    px: 1,
                    py: 0.5,
                    bgcolor: 'action.selected',
                    borderBottom: 1,
                    borderColor: 'divider',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                  }}
                >
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Refs @
                  </Typography>
                  <FormControl size="small" sx={{ minWidth: 80 }}>
                    <Select
                      value={refPanel}
                      onChange={(e) => setRefPanel(e.target.value as 'left' | 'right')}
                      sx={{
                        '& .MuiSelect-select': {
                          py: 0,
                          px: 0.5,
                          fontSize: '0.75rem',
                          fontFamily: 'monospace',
                        },
                        '& .MuiOutlinedInput-notchedOutline': {
                          border: 'none',
                        },
                      }}
                    >
                      <MenuItem value="left">
                        <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                          {getShortHash(leftCommit)} (left)
                        </Typography>
                      </MenuItem>
                      <MenuItem value="right">
                        <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                          {getShortHash(rightCommit)} (right)
                        </Typography>
                      </MenuItem>
                    </Select>
                  </FormControl>
                </Box>
              )}
              <Box sx={{ flex: 1, overflow: 'hidden' }}>
                <ReferencesPanel
                  symbol={selectedSymbol}
                  isDirectDefinition={isDirectDefinition}
                  searchByName={searchByName}
                  selectedCommit={refCommit}
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
          </Box>
        )}
      </Box>
    </Box>
  )
}
