import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Button,
  Toolbar,
  Typography,
  IconButton,
  CircularProgress,
  Alert,
  Chip,
  Select,
  MenuItem,
  FormControl,
  Tooltip,
  FormControlLabel,
  Checkbox,
} from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import CloseIcon from '@mui/icons-material/Close'
import HistoryToggleOffIcon from '@mui/icons-material/HistoryToggleOff'
import CodeIcon from '@mui/icons-material/Code'
import DescriptionIcon from '@mui/icons-material/Description'
import VerticalAlignTopIcon from '@mui/icons-material/VerticalAlignTop'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'

import { BranchSelector } from '@/components/BranchSelector'
import { CodeViewer } from '@/components/CodeViewer'
import { DiffCodeViewer } from '@/components/DiffCodeViewer'
import { ImageViewer } from '@/components/ImageViewer'
import { MarkdownViewer } from '@/components/MarkdownViewer'
import { FileTree } from '@/components/FileTree'
import { SymbolSearch } from '@/components/SymbolSearch'
import { ReferencesPanel } from '@/components/ReferencesPanel'
import { VersionSelector } from '@/components/VersionSelector'
import { CodeHeader, type TabValue } from '@/components/CodeHeader'
import { useBrowseState } from '@/hooks/useBrowseState'
import { getFileBlame, type BlameLine } from '@/lib/api'
import { isMarkdownFile, detectLanguage } from '@/lib/fileUtils'

interface BrowseProps {
  /** Repository name (overrides URL param) */
  repoName?: string
}

export default function Browse({ repoName: repoNameProp }: BrowseProps) {
  const navigate = useNavigate()
  const { urlState, dataState, diffState, uiState, refsState, computedState, actions } =
    useBrowseState(repoNameProp)

  // Destructure for convenience
  // Blame state
  const [blameEnabled, setBlameEnabled] = useState(false)
  const [blameData, setBlameData] = useState<BlameLine[]>([])
  const [blameLoading, setBlameLoading] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const { repoName, filePath, highlightLine, diffMode, diffCommit, diffBranch, selectedBranch } =
    urlState
  const { repository, treeNodes, fileContent, fileSymbols, fileReferences, rawContent } = dataState
  const { diffContent, diffSymbols, diffReferences, activePanel, treePanel, refPanel } = diffState
  const { drawerOpen, refsPanelOpen, loading, fileLoading, diffLoading, error } = uiState
  const { selectedSymbol, isDirectDefinition, searchByName } = refsState
  const { leftCommit, rightCommit, fileChangedInCommit } = computedState

  // Fetch blame data when enabled and file is loaded
  useEffect(() => {
    if (!blameEnabled || !repoName || !filePath || !fileContent) {
      setBlameData([])
      return
    }

    const loadBlame = async () => {
      setBlameLoading(true)
      try {
        const result = await getFileBlame(
          repoName,
          filePath,
          urlState.selectedCommit || undefined,
          selectedBranch || undefined
        )
        setBlameData(result.lines)
      } catch (err) {
        console.error('Failed to load blame:', err)
        setBlameData([])
      } finally {
        setBlameLoading(false)
      }
    }

    loadBlame()
  }, [blameEnabled, repoName, filePath, fileContent, urlState.selectedCommit, selectedBranch])

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

  // CodeHeader handlers
  const handleRepoChange = (newRepoName: string) => {
    // Navigate to new repo, resetting to default branch and HEAD
    navigate(`/browse/${newRepoName}`)
  }

  const handleBranchChange = (newBranch: string) => {
    actions.changeBranch(newBranch)
  }

  const handleCommitChange = (newCommit: string) => {
    actions.changeVersion(newCommit)
  }

  const handleTabChange = (tab: TabValue) => {
    const params = new URLSearchParams()
    if (repoName) params.set('repo', repoName)
    if (selectedBranch) params.set('branch', selectedBranch)
    if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)

    switch (tab) {
      case 'browse':
        // Already on browse
        break
      case 'search':
        navigate(`/search?${params.toString()}`)
        break
      case 'history':
        navigate(`/history?${params.toString()}`)
        break
    }
  }

  const handleBlameCommitClick = (commitHash: string) => {
    const params = new URLSearchParams()
    if (repoName) params.set('repo', repoName)
    if (selectedBranch) params.set('branch', selectedBranch)
    params.set('commit', commitHash)
    navigate(`/history?${params.toString()}`)
  }

  const handleSearchText = useCallback(
    (text: string) => {
      if (!text) return
      const params = new URLSearchParams()
      if (repoName) params.set('repo', repoName)
      if (selectedBranch) params.set('branch', selectedBranch)
      if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
      params.set('query', text)
      navigate(`/search?${params.toString()}`)
    },
    [repoName, selectedBranch, urlState.selectedCommit, navigate]
  )

  const handleJumpToTop = useCallback(() => {
    const isRenderedMarkdown =
      fileContent &&
      isMarkdownFile(fileContent.path, fileContent.language) &&
      urlState.viewMode !== 'raw'
    const isImage = !!rawContent

    if (isRenderedMarkdown || isImage) {
      scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      actions.navigateToLine(1)
    }
  }, [fileContent, rawContent, urlState.viewMode, actions])

  // Keyboard shortcut: Cmd+Shift+F (Mac) / Ctrl+Shift+F (Win/Linux)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      const isMod = e.metaKey || e.ctrlKey
      if (isMod && e.shiftKey && e.key === 'F') {
        e.preventDefault()
        const selection = window.getSelection()
        const selectedText = selection?.toString().trim() ?? ''
        if (selectedText) {
          handleSearchText(selectedText)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSearchText])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error && !filePath) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Global Header with tabs */}
      <CodeHeader
        currentTab="browse"
        repoName={repoName ?? null}
        branch={selectedBranch ?? null}
        commit={urlState.selectedCommit ?? null}
        onRepoChange={handleRepoChange}
        onBranchChange={handleBranchChange}
        onCommitChange={handleCommitChange}
        onTabChange={handleTabChange}
      />

      {/* Browse-specific toolbar */}
      <Toolbar
        variant="dense"
        sx={{
          gap: 1,
          minHeight: '40px !important',
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <IconButton size="small" onClick={actions.toggleDrawer}>
          {drawerOpen ? <ChevronLeftIcon fontSize="small" /> : <MenuIcon fontSize="small" />}
        </IconButton>

        {/* Changed Only toggle */}
        <FormControlLabel
          control={
            <Checkbox
              checked={urlState.changedOnly}
              onChange={actions.toggleChangedOnly}
              size="small"
            />
          }
          label="Changed files only"
          sx={{
            ml: 0,
            '& .MuiFormControlLabel-label': {
              fontSize: '0.875rem',
            },
          }}
        />

        {/* File path and info */}
        {fileContent && (
          <>
            <Typography
              variant="body2"
              sx={{
                fontFamily: 'monospace',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                minWidth: 0,
              }}
            >
              {fileContent.path}
            </Typography>
            {detectLanguage(fileContent.path, fileContent.language) && (
              <Chip label={detectLanguage(fileContent.path, fileContent.language)} size="small" />
            )}
            <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
              {fileContent.line_count} lines
            </Typography>
          </>
        )}

        {/* Jump to top of file - visible for all file types */}
        {(fileContent || rawContent) && (
          <Tooltip title="Jump to top of file">
            <IconButton size="small" onClick={handleJumpToTop}>
              <VerticalAlignTopIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}

        {/* Back to file browser (show when file is loaded or file-level error) */}
        {(fileContent || rawContent || (error && filePath)) && (
          <Tooltip title="Back to file browser">
            <IconButton
              size="small"
              aria-label="Back to file browser"
              onClick={actions.resetToFileTree}
            >
              <ArrowBackIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}

        <Box sx={{ flex: 1 }} />

        {/* Markdown view toggle (only for markdown files, not in diff mode) */}
        {repoName &&
          filePath &&
          fileContent &&
          isMarkdownFile(fileContent.path, fileContent.language) &&
          !diffMode && (
            <Tooltip
              title={urlState.viewMode === 'raw' ? 'Show rendered markdown' : 'Show raw source'}
            >
              <IconButton
                size="small"
                onClick={() => actions.setViewMode(urlState.viewMode === 'raw' ? null : 'raw')}
                color={urlState.viewMode === 'raw' ? 'default' : 'primary'}
              >
                {urlState.viewMode === 'raw' ? (
                  <DescriptionIcon fontSize="small" />
                ) : (
                  <CodeIcon fontSize="small" />
                )}
              </IconButton>
            </Tooltip>
          )}

        {/* Blame toggle (only when file is loaded, NOT in diff mode, and NOT rendered markdown) */}
        {repoName &&
          filePath &&
          fileContent &&
          !diffMode &&
          !(
            isMarkdownFile(fileContent.path, fileContent.language) && urlState.viewMode !== 'raw'
          ) && (
            <Tooltip title={blameEnabled ? 'Hide blame annotations' : 'Show blame annotations'}>
              <IconButton
                size="small"
                onClick={() => setBlameEnabled(!blameEnabled)}
                color={blameEnabled ? 'primary' : 'default'}
              >
                <HistoryToggleOffIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}

        {/* Compare button (only when file is loaded and NOT in diff mode) */}
        {repoName && filePath && repository && fileContent && !diffMode && (
          <Tooltip title="Compare versions or branches">
            <IconButton size="small" onClick={actions.enterDiffMode}>
              <CompareArrowsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}

        {/* Exit diff mode button (only when in diff mode) */}
        {diffMode && (
          <Tooltip title="Exit compare mode">
            <IconButton size="small" onClick={actions.exitDiffMode}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}

        {/* Symbol Search */}
        <SymbolSearch repositoryId={repository?.id} onSymbolSelect={actions.navigateToSymbol} />
      </Toolbar>

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
          ) : error && filePath ? (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                flex: 1,
                p: 3,
                gap: 2,
              }}
            >
              <Alert severity="error" sx={{ maxWidth: 500 }}>
                {error}
              </Alert>
              <Button
                variant="outlined"
                startIcon={<ArrowBackIcon />}
                onClick={actions.resetToFileTree}
              >
                Back to file browser
              </Button>
            </Box>
          ) : rawContent ? (
            <Box ref={scrollContainerRef} sx={{ flex: 1, overflow: 'auto', display: 'flex' }}>
              <ImageViewer rawContent={rawContent} />
            </Box>
          ) : fileContent ? (
            <>
              {/* Code Viewer or Diff Viewer */}
              <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
                {diffMode && diffContent && repository ? (
                  <DiffCodeViewer
                    leftContent={fileContent.content}
                    rightContent={diffContent.content}
                    leftHeader={
                      <Typography
                        variant="caption"
                        sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                      >
                        {selectedBranch || repository.default_branch}@
                        {getShortHash(urlState.selectedCommit || leftCommit)}
                      </Typography>
                    }
                    rightHeader={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <BranchSelector
                          repositoryId={repository.id}
                          selectedBranch={diffBranch}
                          defaultBranch={repository.default_branch}
                          onBranchChange={actions.changeDiffBranch}
                          repoName={repoName!}
                          filePath={filePath!}
                          compact
                        />
                        <VersionSelector
                          repoName={repoName!}
                          filePath={filePath!}
                          selectedCommit={diffCommit}
                          onVersionChange={actions.changeDiffVersion}
                          selectedBranch={diffBranch || selectedBranch}
                          compact
                        />
                      </Box>
                    }
                    language={detectLanguage(fileContent.path, fileContent.language)}
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
                    onSearchText={handleSearchText}
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
                        <Typography
                          variant="caption"
                          sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                        >
                          {selectedBranch || repository.default_branch}@
                          {getShortHash(urlState.selectedCommit || leftCommit)}
                        </Typography>
                      </Box>
                      <Box sx={{ flex: 1, overflow: 'auto' }}>
                        <CodeViewer
                          content={fileContent.content}
                          language={detectLanguage(fileContent.path, fileContent.language)}
                          symbols={fileSymbols}
                          references={fileReferences}
                          highlightLine={highlightLine}
                          onSymbolClick={actions.handleSymbolClick}
                          onReferenceClick={actions.handleCodeReferenceClick}
                          onLineClick={actions.navigateToLine}
                          onSearchText={handleSearchText}
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
                          compact
                        />
                        <VersionSelector
                          repoName={repoName!}
                          filePath={filePath!}
                          selectedCommit={diffCommit}
                          onVersionChange={actions.changeDiffVersion}
                          selectedBranch={diffBranch || selectedBranch}
                          compact
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
                ) : urlState.changedOnly && urlState.selectedCommit && !fileChangedInCommit ? (
                  /* File not changed in this commit while "Changed files only" is active */
                  <Box
                    sx={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center',
                      alignItems: 'center',
                      color: 'text.secondary',
                      p: 3,
                      textAlign: 'center',
                    }}
                  >
                    <Typography variant="h6" gutterBottom>
                      File not changed in this revision
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {fileContent.path} was not modified in commit{' '}
                      <code style={{ fontFamily: 'monospace' }}>
                        {urlState.selectedCommit.substring(0, 7)}
                      </code>
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Uncheck &quot;Changed files only&quot; to view the file at this revision.
                    </Typography>
                  </Box>
                ) : isMarkdownFile(fileContent.path, fileContent.language) &&
                  urlState.viewMode !== 'raw' ? (
                  <Box ref={scrollContainerRef} sx={{ flex: 1, overflow: 'auto' }}>
                    <MarkdownViewer content={fileContent.content} />
                  </Box>
                ) : (
                  <Box sx={{ flex: 1, overflow: 'auto' }}>
                    {blameLoading ? (
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'center',
                          alignItems: 'center',
                          flex: 1,
                          p: 4,
                        }}
                      >
                        <CircularProgress size={24} />
                      </Box>
                    ) : (
                      <CodeViewer
                        content={fileContent.content}
                        language={detectLanguage(fileContent.path, fileContent.language)}
                        symbols={fileSymbols}
                        references={fileReferences}
                        blameData={blameEnabled ? blameData : undefined}
                        highlightLine={highlightLine}
                        onSymbolClick={actions.handleSymbolClick}
                        onReferenceClick={actions.handleCodeReferenceClick}
                        onLineClick={actions.navigateToLine}
                        onBlameCommitClick={handleBlameCommitClick}
                        onSearchText={handleSearchText}
                      />
                    )}
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
                    diffMode ? (refPanel === 'right' ? diffBranch : selectedBranch) : selectedBranch
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
