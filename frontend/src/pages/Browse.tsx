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
import VerticalAlignTopIcon from '@mui/icons-material/VerticalAlignTop'

import { BranchSelector } from '@/components/BranchSelector'
import { CodeViewer } from '@/components/CodeViewer'
import { DiffCodeViewer } from '@/components/DiffCodeViewer'
import { FileTree } from '@/components/FileTree'
import { SymbolSearch } from '@/components/SymbolSearch'
import { ReferencesPanel } from '@/components/ReferencesPanel'
import { VersionSelector } from '@/components/VersionSelector'
import { useBrowseState } from '@/hooks/useBrowseState'

interface BrowseProps {
  /** If true, renders without AppBar (for use in tabs) */
  noAppBar?: boolean
  /** Repository name (overrides URL param) */
  repoName?: string
}

export default function Browse({ noAppBar = false, repoName: repoNameProp }: BrowseProps) {
  const { urlState, dataState, diffState, uiState, refsState, computedState, actions } =
    useBrowseState(repoNameProp)

  // Destructure for convenience
  const { repoName, filePath, highlightLine, diffMode, diffCommit, diffBranch, selectedBranch } =
    urlState
  const { allRepositories, repository, treeNodes, fileContent, fileSymbols, fileReferences } =
    dataState
  const { diffContent, diffSymbols, diffReferences, activePanel, treePanel, refPanel } = diffState
  const { drawerOpen, refsPanelOpen, loading, fileLoading, diffLoading, error } = uiState
  const { selectedSymbol, isDirectDefinition, searchByName } = refsState
  const { leftCommit, rightCommit } = computedState

  // Get short hash for display
  const getShortHash = (hash: string | null | undefined) => {
    if (!hash) return 'latest'
    return hash.substring(0, 7)
  }

  // Get display text for left panel version in refs dropdown
  const getLeftVersionDisplay = () => {
    return leftCommit ? leftCommit.substring(0, 7) : '...'
  }

  // Get display text for right panel version in refs dropdown
  const getRightVersionDisplay = () => {
    return rightCommit ? rightCommit.substring(0, 7) : '...'
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
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

  const appBarContent = !noAppBar && (
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

        {/* Symbol Search - uncontrolled, just triggers navigation */}
        <SymbolSearch repositoryId={repository?.id} onSymbolSelect={actions.navigateToSymbol} />
      </Toolbar>
    </AppBar>
  )

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: noAppBar ? '100%' : '100vh' }}>
      {appBarContent}

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
                          {getLeftVersionDisplay()} (left)
                        </Typography>
                      </MenuItem>
                      <MenuItem value="right">
                        <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                          {getRightVersionDisplay()} (right)
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
                <Tooltip title="Jump to top of file">
                  <IconButton size="small" onClick={() => actions.navigateToLine(1)}>
                    <VerticalAlignTopIcon fontSize="small" />
                  </IconButton>
                </Tooltip>

                {/* Branch + Version controls (only when NOT in diff mode) */}
                {repoName && filePath && repository && !diffMode && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <BranchSelector
                      repositoryId={repository.id}
                      selectedBranch={selectedBranch}
                      defaultBranch={repository.default_branch}
                      onBranchChange={actions.changeBranch}
                      repoName={repoName}
                      filePath={filePath}
                    />
                    <VersionSelector
                      repoName={repoName}
                      filePath={filePath}
                      selectedCommit={urlState.selectedCommit}
                      onVersionChange={actions.changeVersion}
                      selectedBranch={selectedBranch}
                      defaultBranch={repository.default_branch}
                    />
                    <Tooltip title="Compare versions or branches">
                      <IconButton size="small" onClick={actions.enterDiffMode}>
                        <CompareArrowsIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                )}

                {/* Exit diff mode button (only when in diff mode) */}
                {diffMode && (
                  <Tooltip title="Exit compare mode">
                    <IconButton size="small" onClick={actions.exitDiffMode}>
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>

              {/* Code Viewer or Diff Viewer */}
              <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
                {diffMode && diffContent && repository ? (
                  <DiffCodeViewer
                    leftContent={fileContent.content}
                    rightContent={diffContent.content}
                    leftHeader={
                      <>
                        <BranchSelector
                          repositoryId={repository.id}
                          selectedBranch={selectedBranch}
                          defaultBranch={repository.default_branch}
                          onBranchChange={actions.changeBranch}
                          repoName={repoName!}
                          filePath={filePath!}
                        />
                        <VersionSelector
                          repoName={repoName!}
                          filePath={filePath!}
                          selectedCommit={urlState.selectedCommit}
                          onVersionChange={actions.changeVersion}
                          selectedBranch={selectedBranch}
                          defaultBranch={repository.default_branch}
                        />
                      </>
                    }
                    rightHeader={
                      <>
                        <BranchSelector
                          repositoryId={repository.id}
                          selectedBranch={diffBranch}
                          defaultBranch={repository.default_branch}
                          onBranchChange={actions.changeDiffBranch}
                          repoName={repoName!}
                          filePath={filePath!}
                        />
                        <VersionSelector
                          repoName={repoName!}
                          filePath={filePath!}
                          selectedCommit={diffCommit}
                          onVersionChange={actions.changeDiffVersion}
                          selectedBranch={diffBranch || selectedBranch}
                          defaultBranch={repository.default_branch}
                        />
                      </>
                    }
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
                ) : diffMode && !diffContent && repository ? (
                  /* Diff mode but content failed to load - show side-by-side with error message */
                  <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
                    {/* Left pane - current file */}
                    <Box
                      sx={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        borderRight: 1,
                        borderColor: 'divider',
                        overflow: 'hidden',
                      }}
                    >
                      <Box
                        sx={{
                          px: 1,
                          py: 0.5,
                          bgcolor: 'background.paper',
                          borderBottom: 1,
                          borderColor: 'divider',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                        }}
                      >
                        <BranchSelector
                          repositoryId={repository.id}
                          selectedBranch={selectedBranch}
                          defaultBranch={repository.default_branch}
                          onBranchChange={actions.changeBranch}
                          repoName={repoName!}
                          filePath={filePath!}
                        />
                        <VersionSelector
                          repoName={repoName!}
                          filePath={filePath!}
                          selectedCommit={urlState.selectedCommit}
                          onVersionChange={actions.changeVersion}
                          selectedBranch={selectedBranch}
                          defaultBranch={repository.default_branch}
                        />
                      </Box>
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
                    </Box>
                    {/* Right pane - error/select prompt */}
                    <Box
                      sx={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        overflow: 'hidden',
                      }}
                    >
                      <Box
                        sx={{
                          px: 1,
                          py: 0.5,
                          bgcolor: 'background.paper',
                          borderBottom: 1,
                          borderColor: 'divider',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                        }}
                      >
                        <BranchSelector
                          repositoryId={repository.id}
                          selectedBranch={diffBranch}
                          defaultBranch={repository.default_branch}
                          onBranchChange={actions.changeDiffBranch}
                          repoName={repoName!}
                          filePath={filePath!}
                        />
                        <VersionSelector
                          repoName={repoName!}
                          filePath={filePath!}
                          selectedCommit={diffCommit}
                          onVersionChange={actions.changeDiffVersion}
                          selectedBranch={diffBranch || selectedBranch}
                          defaultBranch={repository.default_branch}
                        />
                      </Box>
                      <Box
                        sx={{
                          flex: 1,
                          display: 'flex',
                          justifyContent: 'center',
                          alignItems: 'center',
                          color: 'text.secondary',
                          p: 2,
                          textAlign: 'center',
                        }}
                      >
                        <Typography>
                          File not found at selected version.
                          <br />
                          Select a different branch or version to compare.
                        </Typography>
                      </Box>
                    </Box>
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
                          {getLeftVersionDisplay()} (left)
                        </Typography>
                      </MenuItem>
                      <MenuItem value="right">
                        <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                          {getRightVersionDisplay()} (right)
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
                  selectedBranch={
                    diffMode
                      ? refPanel === 'right'
                        ? diffBranch
                        : selectedBranch
                      : selectedBranch
                  }
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
