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
import { useBrowseState } from '@/hooks/useBrowseState'
import { formatCommitDate } from '@/lib/dateUtils'

export default function Browse() {
  const { urlState, dataState, diffState, uiState, refsState, computedState, actions } =
    useBrowseState()

  // Destructure for convenience
  const { repoName, filePath, highlightLine, diffMode, diffCommit } = urlState
  const {
    allRepositories,
    repository,
    treeNodes,
    fileContent,
    fileSymbols,
    fileReferences,
    fileVersions,
  } = dataState
  const { diffContent, diffSymbols, diffReferences, activePanel, treePanel, refPanel } = diffState
  const { drawerOpen, refsPanelOpen, loading, fileLoading, diffLoading, error, searchQuery } =
    uiState
  const { selectedSymbol, isDirectDefinition, searchByName } = refsState
  const { leftCommit, rightCommit, currentCommitHash } = computedState

  // Get short hash for display
  const getShortHash = (hash: string | null | undefined) => {
    if (!hash) return 'latest'
    return hash.substring(0, 7)
  }

  // All commit dates for formatting (used by formatCommitDate to detect same-day commits)
  const allCommitDates = fileVersions.map((v) => v.commit_date)

  // Check if a version has content changes from the previous version
  const hasContentChange = (version: { content_hash: string }, index: number): boolean => {
    const prevVersion = fileVersions[index + 1]
    return !prevVersion || version.content_hash !== prevVersion.content_hash
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
          <IconButton edge="start" color="inherit" onClick={actions.toggleDrawer}>
            {drawerOpen ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>

          {/* Repository Selector */}
          {allRepositories.length > 1 ? (
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <Select
                value={repoName || ''}
                onChange={(e) => actions.navigateToRepository(e.target.value as string)}
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
            onSymbolSelect={actions.navigateToSymbol}
            value={searchQuery}
            onValueChange={actions.setSearchQuery}
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
            {(computedState.treeCommit || diffMode) && (
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
                      onChange={(e) => actions.setTreePanel(e.target.value as 'left' | 'right')}
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
                    {getShortHash(computedState.treeCommit)}
                  </Typography>
                )}
              </Box>
            )}
            <Box sx={{ flex: 1, overflow: 'auto' }}>
              <FileTree
                nodes={treeNodes}
                selectedFileId={fileContent?.id ?? null}
                onFileSelect={actions.navigateToFile}
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
                      selectedCommit={urlState.selectedCommit}
                      onVersionChange={actions.changeVersion}
                    />

                    {/* Diff controls */}
                    {!diffMode ? (
                      <Tooltip title="Compare versions">
                        <IconButton
                          size="small"
                          onClick={actions.enterDiffMode}
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
                            onChange={(e) => actions.changeDiffVersion(e.target.value || null)}
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
                                          {formatCommitDate(version.commit_date, allCommitDates)}
                                        </Typography>
                                      </Box>
                                    </Tooltip>
                                  </MenuItem>
                                )
                              })}
                          </Select>
                        </FormControl>
                        <Tooltip title="Exit compare mode">
                          <IconButton size="small" onClick={actions.exitDiffMode}>
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
                    leftLabel={`${getShortHash(urlState.selectedCommit || fileVersions[0]?.commit_hash)} (current)`}
                    rightLabel={`${getShortHash(diffCommit)} (compare)`}
                    language={fileContent.language}
                    leftSymbols={fileSymbols}
                    rightSymbols={diffSymbols}
                    leftReferences={fileReferences}
                    rightReferences={diffReferences}
                    highlightLine={highlightLine}
                    activePanel={activePanel}
                    onPanelClick={actions.setActivePanel}
                    onSymbolClick={actions.handleDiffSymbolClick}
                    onReferenceClick={actions.handleDiffReferenceClick}
                    onLineClick={actions.handleDiffLineClick}
                    onClosePanel={actions.closePanel}
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
                      onSymbolClick={actions.handleSymbolClick}
                      onReferenceClick={actions.handleCodeReferenceClick}
                      onLineClick={actions.navigateToLine}
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
                      onChange={(e) =>
                        actions.handleRefPanelChange(e.target.value as 'left' | 'right')
                      }
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
                  selectedCommit={computedState.refCommit}
                  onReferenceClick={actions.handleRefPanelClick}
                  onDefinitionClick={actions.handleDefinitionClick}
                  onClose={actions.closeRefsPanel}
                />
              </Box>
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  )
}
