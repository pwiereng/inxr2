import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
  Typography,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Collapse,
  CircularProgress,
  Alert,
  TextField,
  InputAdornment,
  Chip,
  Tooltip,
} from '@mui/material'
import FolderIcon from '@mui/icons-material/Folder'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import ClassIcon from '@mui/icons-material/Category'
import FunctionIcon from '@mui/icons-material/Functions'
import FieldIcon from '@mui/icons-material/DataObject'
import SearchIcon from '@mui/icons-material/Search'
import BlockIcon from '@mui/icons-material/Block'
import { CodeHeader } from '@/components/CodeHeader'
import type { TabValue } from '@/components/CodeHeader'
import {
  getSymbolTree,
  type SymbolTreeFile,
  type SymbolTreeSymbol,
  type SymbolTreeInheritance,
  type SymbolTreeResponse,
} from '@/lib/api'

// Symbol kind groupings for display
const KIND_ICONS: Record<string, React.ReactNode> = {
  class: <ClassIcon fontSize="small" sx={{ color: '#e5c07b' }} />,
  interface: <ClassIcon fontSize="small" sx={{ color: '#56b6c2' }} />,
  struct: <ClassIcon fontSize="small" sx={{ color: '#d19a66' }} />,
  record: <ClassIcon fontSize="small" sx={{ color: '#d19a66' }} />,
  enum: <ClassIcon fontSize="small" sx={{ color: '#c678dd' }} />,
  function: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  method: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  staticmethod: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  classmethod: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  constructor: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  getter: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  setter: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
}

function getKindIcon(kind: string): React.ReactNode {
  return KIND_ICONS[kind] ?? <FieldIcon fontSize="small" sx={{ color: '#abb2bf' }} />
}

function getKindLabel(kind: string): string {
  return kind.replace(/_/g, ' ')
}

interface ExpandedState {
  files: Set<number>
  symbols: Set<number>
}

interface SymbolChildren {
  [parentId: number]: SymbolTreeSymbol[]
}

export default function LogicalView(): React.ReactElement {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const repoName = searchParams.get('repo')
  const branch = searchParams.get('branch')
  const commit = searchParams.get('commit')

  // Data state
  const [files, setFiles] = useState<SymbolTreeFile[]>([])
  const [fileSymbols, setFileSymbols] = useState<Record<number, SymbolTreeSymbol[]>>({})
  const [symbolChildren, setSymbolChildren] = useState<SymbolChildren>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // UI state
  const [expanded, setExpanded] = useState<ExpandedState>({
    files: new Set(),
    symbols: new Set(),
  })
  const [expandingFile, setExpandingFile] = useState<number | null>(null)
  const [expandingSymbol, setExpandingSymbol] = useState<number | null>(null)
  const [filterText, setFilterText] = useState('')
  const [excludeText, setExcludeText] = useState('')
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null)

  // Derive available languages from loaded files
  const availableLanguages = useMemo(() => {
    const langs = new Set<string>()
    for (const f of files) {
      if (f.language) langs.add(f.language)
    }
    return [...langs].sort()
  }, [files])

  // Load tier 1 (files) when repo/branch/commit changes
  useEffect(() => {
    if (!repoName) {
      setFiles([])
      return
    }

    let cancelled = false
    const loadFiles = async () => {
      setLoading(true)
      setError(null)
      setFiles([])
      setFileSymbols({})
      setSymbolChildren({})
      setExpanded({ files: new Set(), symbols: new Set() })

      try {
        const result = await getSymbolTree(repoName, {
          branch: branch ?? undefined,
          commit: commit ?? undefined,
        })
        if (!cancelled && result.files) {
          setFiles(result.files)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load symbol tree')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadFiles()
    return () => {
      cancelled = true
    }
  }, [repoName, branch, commit])

  // Expand/collapse a file (tier 2)
  const toggleFile = useCallback(
    async (fileId: number) => {
      const newExpanded = { ...expanded }
      const newFiles = new Set(expanded.files)

      if (newFiles.has(fileId)) {
        newFiles.delete(fileId)
        setExpanded({ ...newExpanded, files: newFiles })
        return
      }

      // Fetch symbols if not cached
      if (!fileSymbols[fileId] && repoName) {
        setExpandingFile(fileId)
        try {
          const result: SymbolTreeResponse = await getSymbolTree(repoName, {
            branch: branch ?? undefined,
            commit: commit ?? undefined,
            file_id: fileId,
          })
          if (result.symbols) {
            setFileSymbols((prev) => ({ ...prev, [fileId]: result.symbols! }))
          }
        } catch {
          // Silently fail — file just won't expand
        } finally {
          setExpandingFile(null)
        }
      }

      newFiles.add(fileId)
      setExpanded({ ...newExpanded, files: newFiles })
    },
    [expanded, fileSymbols, repoName, branch, commit]
  )

  // Expand/collapse a symbol (tier 3)
  const toggleSymbol = useCallback(
    async (symbolId: number) => {
      const newSymbols = new Set(expanded.symbols)

      if (newSymbols.has(symbolId)) {
        newSymbols.delete(symbolId)
        setExpanded({ ...expanded, symbols: newSymbols })
        return
      }

      // Fetch children if not cached
      if (!symbolChildren[symbolId] && repoName) {
        setExpandingSymbol(symbolId)
        try {
          const result: SymbolTreeResponse = await getSymbolTree(repoName, {
            branch: branch ?? undefined,
            commit: commit ?? undefined,
            parent_symbol_id: symbolId,
          })
          if (result.symbols) {
            setSymbolChildren((prev) => ({ ...prev, [symbolId]: result.symbols! }))
          }
        } catch {
          // Silently fail
        } finally {
          setExpandingSymbol(null)
        }
      }

      newSymbols.add(symbolId)
      setExpanded({ ...expanded, symbols: newSymbols })
    },
    [expanded, symbolChildren, repoName, branch, commit]
  )

  // Navigate to symbol in browse view
  const handleSymbolClick = useCallback(
    (symbol: SymbolTreeSymbol) => {
      if (!repoName || !symbol.file_path) return
      const params = new URLSearchParams()
      if (branch) params.set('branch', branch)
      if (commit) params.set('commit', commit)
      params.set('line', symbol.start_line.toString())
      navigate(`/browse/${repoName}/${symbol.file_path}?${params.toString()}`)
    },
    [repoName, branch, commit, navigate]
  )

  // Navigate to inheritance target: click → Browse, Cmd/Ctrl+click → locate in tree
  const handleInheritanceClick = useCallback(
    async (inh: SymbolTreeInheritance, e: React.MouseEvent) => {
      if (!repoName || !inh.target_file_path) return

      if (e.metaKey || e.ctrlKey) {
        // Cmd/Ctrl+click: locate in logical view tree
        const targetFileId = inh.target_file_id
        if (targetFileId == null) return

        // Expand the file if not already expanded
        if (!expanded.files.has(targetFileId)) {
          await toggleFile(targetFileId)
        }

        // Scroll to the file node after a short delay for render
        setTimeout(() => {
          const el = document.querySelector(`[data-file-id="${targetFileId}"]`)
          el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 200)
      } else {
        // Regular click: navigate to Browse view
        const params = new URLSearchParams()
        if (branch) params.set('branch', branch)
        if (commit) params.set('commit', commit)
        if (inh.target_line) params.set('line', inh.target_line.toString())
        navigate(`/browse/${repoName}/${inh.target_file_path}?${params.toString()}`)
      }
    },
    [repoName, branch, commit, navigate, expanded.files, toggleFile]
  )

  // Header handlers
  const handleRepoChange = (newRepo: string) => {
    const params = new URLSearchParams()
    params.set('repo', newRepo)
    navigate(`/logical-view?${params.toString()}`)
  }

  const handleBranchChange = (newBranch: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('branch', newBranch)
    params.delete('commit')
    navigate(`/logical-view?${params.toString()}`)
  }

  const handleCommitChange = (newCommit: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('commit', newCommit)
    navigate(`/logical-view?${params.toString()}`)
  }

  const handleTabChange = (newTab: TabValue) => {
    const params = new URLSearchParams()
    if (repoName) params.set('repo', repoName)
    if (branch) params.set('branch', branch)
    if (commit) params.set('commit', commit)

    switch (newTab) {
      case 'browse':
        if (repoName) {
          navigate(`/browse/${repoName}?${params.toString()}`)
        } else {
          navigate('/')
        }
        break
      case 'search':
        navigate(`/search?${params.toString()}`)
        break
      case 'history':
        navigate(`/history?${params.toString()}`)
        break
      case 'logical-view':
        navigate(`/logical-view?${params.toString()}`)
        break
      case 'dependencies':
        navigate(`/dependencies?${params.toString()}`)
        break
      case 'help':
        navigate(`/help?${params.toString()}`)
        break
    }
  }

  // Filter files by language and text
  const filteredFiles = useMemo(() => {
    let result = files
    if (selectedLanguage) {
      result = result.filter((f) => f.language === selectedLanguage)
    }
    if (filterText) {
      const lower = filterText.toLowerCase()
      result = result.filter(
        (f) =>
          f.path.toLowerCase().includes(lower) ||
          (fileSymbols[f.file_id] ?? []).some((s) => s.name.toLowerCase().includes(lower))
      )
    }
    if (excludeText) {
      const lower = excludeText.toLowerCase()
      result = result.filter(
        (f) =>
          !f.path.toLowerCase().includes(lower) &&
          !(fileSymbols[f.file_id] ?? []).some((s) => s.name.toLowerCase().includes(lower))
      )
    }
    return result
  }, [files, selectedLanguage, filterText, excludeText, fileSymbols])

  const fileName = (path: string) => {
    const parts = path.split('/')
    return parts[parts.length - 1] ?? path
  }

  const fileDir = (path: string) => {
    const parts = path.split('/')
    if (parts.length <= 1) return ''
    return parts.slice(0, -1).join('/') + '/'
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <CodeHeader
        currentTab="logical-view"
        repoName={repoName}
        branch={branch}
        commit={commit}
        onRepoChange={handleRepoChange}
        onBranchChange={handleBranchChange}
        onCommitChange={handleCommitChange}
        onTabChange={handleTabChange}
      />

      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Filter bar */}
        {repoName && files.length > 0 && (
          <Box
            sx={{
              px: 2,
              py: 1,
              borderBottom: 1,
              borderColor: 'divider',
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              flexWrap: 'wrap',
            }}
          >
            <TextField
              size="small"
              placeholder="Include..."
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ maxWidth: 250 }}
            />
            <TextField
              size="small"
              placeholder="Exclude..."
              value={excludeText}
              onChange={(e) => setExcludeText(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <BlockIcon fontSize="small" color="error" />
                  </InputAdornment>
                ),
              }}
              sx={{ maxWidth: 250 }}
            />
            {availableLanguages.length > 1 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
                  Language:
                </Typography>
                <Chip
                  label="All"
                  size="small"
                  variant={selectedLanguage === null ? 'filled' : 'outlined'}
                  color={selectedLanguage === null ? 'primary' : 'default'}
                  onClick={() => setSelectedLanguage(null)}
                  sx={{ height: 24 }}
                />
                {availableLanguages.map((lang) => (
                  <Chip
                    key={lang}
                    label={lang}
                    size="small"
                    variant={selectedLanguage === lang ? 'filled' : 'outlined'}
                    color={selectedLanguage === lang ? 'primary' : 'default'}
                    onClick={() => setSelectedLanguage(selectedLanguage === lang ? null : lang)}
                    sx={{ height: 24 }}
                  />
                ))}
              </Box>
            )}
          </Box>
        )}

        {/* Content */}
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          {!repoName && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
              }}
            >
              <Typography color="text.secondary">
                Select a repository to browse its symbol hierarchy
              </Typography>
            </Box>
          )}

          {loading && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
              }}
            >
              <CircularProgress />
            </Box>
          )}

          {error && (
            <Box sx={{ p: 2 }}>
              <Alert severity="error">{error}</Alert>
            </Box>
          )}

          {repoName && !loading && !error && files.length === 0 && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
              }}
            >
              <Typography color="text.secondary">No symbols found in this repository</Typography>
            </Box>
          )}

          {filteredFiles.length > 0 && (
            <List dense disablePadding>
              {filteredFiles.map((file) => (
                <FileNode
                  key={file.file_id}
                  file={file}
                  isExpanded={expanded.files.has(file.file_id)}
                  isExpanding={expandingFile === file.file_id}
                  symbols={fileSymbols[file.file_id]}
                  symbolChildren={symbolChildren}
                  expandedSymbols={expanded.symbols}
                  expandingSymbol={expandingSymbol}
                  onToggle={toggleFile}
                  onToggleSymbol={toggleSymbol}
                  onSymbolClick={handleSymbolClick}
                  onInheritanceClick={handleInheritanceClick}
                  fileName={fileName}
                  fileDir={fileDir}
                />
              ))}
            </List>
          )}
        </Box>
      </Box>
    </Box>
  )
}

// --- Sub-components ---

interface FileNodeProps {
  file: SymbolTreeFile
  isExpanded: boolean
  isExpanding: boolean
  symbols: SymbolTreeSymbol[] | undefined
  symbolChildren: SymbolChildren
  expandedSymbols: Set<number>
  expandingSymbol: number | null
  onToggle: (fileId: number) => void
  onToggleSymbol: (symbolId: number) => void
  onSymbolClick: (symbol: SymbolTreeSymbol) => void
  onInheritanceClick: (inh: SymbolTreeInheritance, e: React.MouseEvent) => void
  fileName: (path: string) => string
  fileDir: (path: string) => string
}

function FileNode({
  file,
  isExpanded,
  isExpanding,
  symbols,
  symbolChildren,
  expandedSymbols,
  expandingSymbol,
  onToggle,
  onToggleSymbol,
  onSymbolClick,
  onInheritanceClick,
  fileName,
  fileDir,
}: FileNodeProps): React.ReactElement {
  const dir = fileDir(file.path)
  const name = fileName(file.path)

  return (
    <>
      <ListItemButton
        data-file-id={file.file_id}
        onClick={() => onToggle(file.file_id)}
        sx={{ py: 0.5 }}
      >
        <ListItemIcon sx={{ minWidth: 28 }}>
          {isExpanding ? (
            <CircularProgress size={16} />
          ) : isExpanded ? (
            <ExpandMoreIcon fontSize="small" />
          ) : (
            <ChevronRightIcon fontSize="small" />
          )}
        </ListItemIcon>
        <ListItemIcon sx={{ minWidth: 28 }}>
          {isExpanded ? (
            <FolderOpenIcon fontSize="small" color="primary" />
          ) : (
            <FolderIcon fontSize="small" color="primary" />
          )}
        </ListItemIcon>
        <ListItemText
          primary={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" component="span" sx={{ fontFamily: 'monospace' }}>
                <Typography
                  variant="body2"
                  component="span"
                  color="text.secondary"
                  sx={{ fontFamily: 'monospace' }}
                >
                  {dir}
                </Typography>
                {name}
              </Typography>
              <Chip
                label={file.symbol_count}
                size="small"
                variant="outlined"
                sx={{ height: 18, fontSize: '0.7rem' }}
              />
            </Box>
          }
        />
      </ListItemButton>

      <Collapse in={isExpanded} timeout="auto">
        {symbols?.map((symbol) => (
          <SymbolNode
            key={symbol.id}
            symbol={symbol}
            level={1}
            children={symbolChildren[symbol.id]}
            expandedSymbols={expandedSymbols}
            expandingSymbol={expandingSymbol}
            symbolChildren={symbolChildren}
            onToggle={onToggleSymbol}
            onClick={onSymbolClick}
            onInheritanceClick={onInheritanceClick}
          />
        ))}
      </Collapse>
    </>
  )
}

interface SymbolNodeProps {
  symbol: SymbolTreeSymbol
  level: number
  children: SymbolTreeSymbol[] | undefined
  expandedSymbols: Set<number>
  expandingSymbol: number | null
  symbolChildren: SymbolChildren
  onToggle: (symbolId: number) => void
  onClick: (symbol: SymbolTreeSymbol) => void
  onInheritanceClick: (inh: SymbolTreeInheritance, e: React.MouseEvent) => void
}

function SymbolNode({
  symbol,
  level,
  children,
  expandedSymbols,
  expandingSymbol,
  symbolChildren,
  onToggle,
  onClick,
  onInheritanceClick,
}: SymbolNodeProps): React.ReactElement {
  const isExpanded = expandedSymbols.has(symbol.id)
  const isExpanding = expandingSymbol === symbol.id
  const indent = level * 24

  const handleClick = () => {
    if (symbol.has_children) {
      onToggle(symbol.id)
    } else {
      onClick(symbol)
    }
  }

  const handleNavigate = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClick(symbol)
  }

  return (
    <>
      <ListItemButton
        onClick={handleClick}
        onDoubleClick={handleNavigate}
        sx={{
          pl: `${indent + 16}px`,
          py: 0.25,
        }}
      >
        {symbol.has_children && (
          <ListItemIcon sx={{ minWidth: 20 }}>
            {isExpanding ? (
              <CircularProgress size={14} />
            ) : isExpanded ? (
              <ExpandMoreIcon sx={{ fontSize: 16 }} />
            ) : (
              <ChevronRightIcon sx={{ fontSize: 16 }} />
            )}
          </ListItemIcon>
        )}
        {!symbol.has_children && <Box sx={{ width: 20 }} />}

        <ListItemIcon sx={{ minWidth: 24 }}>{getKindIcon(symbol.kind)}</ListItemIcon>

        <ListItemText
          primary={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Tooltip title={`Go to line ${symbol.start_line}`} arrow>
                <Typography
                  variant="body2"
                  component="span"
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: symbol.has_children ? 500 : 400,
                    cursor: 'pointer',
                    '&:hover': { textDecoration: 'underline' },
                  }}
                  onClick={handleNavigate}
                >
                  {symbol.name}
                  {symbol.kind === 'function' ||
                  symbol.kind === 'method' ||
                  symbol.kind === 'constructor' ||
                  symbol.kind === 'staticmethod' ||
                  symbol.kind === 'classmethod'
                    ? '()'
                    : ''}
                </Typography>
              </Tooltip>

              <Typography variant="caption" color="text.disabled" sx={{ fontFamily: 'monospace' }}>
                {getKindLabel(symbol.kind)}
              </Typography>

              {symbol.inheritance.map((inh, i) => (
                <Tooltip
                  key={i}
                  title={
                    inh.target_file_path
                      ? `Click: go to source | ${navigator.platform.includes('Mac') ? 'Cmd' : 'Ctrl'}+Click: locate in tree`
                      : ''
                  }
                  arrow
                >
                  <Chip
                    label={`extends ${inh.reference_text}`}
                    size="small"
                    variant="outlined"
                    color="info"
                    sx={{
                      height: 18,
                      fontSize: '0.65rem',
                      cursor: inh.target_file_path ? 'pointer' : 'default',
                    }}
                    onClick={
                      inh.target_file_path
                        ? (e) => {
                            e.stopPropagation()
                            onInheritanceClick(inh, e)
                          }
                        : undefined
                    }
                  />
                </Tooltip>
              ))}
            </Box>
          }
        />
      </ListItemButton>

      {symbol.has_children && (
        <Collapse in={isExpanded} timeout="auto">
          {children?.map((child) => (
            <SymbolNode
              key={child.id}
              symbol={child}
              level={level + 1}
              children={symbolChildren[child.id]}
              expandedSymbols={expandedSymbols}
              expandingSymbol={expandingSymbol}
              symbolChildren={symbolChildren}
              onToggle={onToggle}
              onClick={onClick}
              onInheritanceClick={onInheritanceClick}
            />
          ))}
        </Collapse>
      )}
    </>
  )
}
