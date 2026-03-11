import { useState, useEffect, useLayoutEffect, useCallback, useMemo, useRef } from 'react'
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
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff'
import TagIcon from '@mui/icons-material/Tag'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import ClearIcon from '@mui/icons-material/Clear'
import RestartAltIcon from '@mui/icons-material/RestartAlt'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import IconButton from '@mui/material/IconButton'
import { CodeHeader } from '@/components/CodeHeader'
import type { TabValue } from '@/components/CodeHeader'
import { SymbolContextMenu, type SymbolContextMenuState } from '@/components/SymbolContextMenu'
import { useSelectionToolbar } from '@/hooks/useSelectionToolbar'
import { SelectionToolbar } from '@/components/SelectionToolbar'
import {
  getSymbolTree,
  searchSymbols,
  getRepositoryByName,
  getCommits,
  type Symbol as ApiSymbol,
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
  variable: <FieldIcon fontSize="small" sx={{ color: '#abb2bf' }} />,
  class_variable: <FieldIcon fontSize="small" sx={{ color: '#d19a66' }} />,
  instance_variable: <FieldIcon fontSize="small" sx={{ color: '#abb2bf' }} />,
  constant: <FieldIcon fontSize="small" sx={{ color: '#d19a66' }} />,
}

const KIND_COLORS: Record<string, string> = {
  class: '#e5c07b',
  interface: '#56b6c2',
  struct: '#d19a66',
  record: '#d19a66',
  enum: '#c678dd',
  function: '#61afef',
  method: '#61afef',
  staticmethod: '#61afef',
  classmethod: '#61afef',
  constant: '#d19a66',
  variable: '#abb2bf',
  class_variable: '#d19a66',
  instance_variable: '#abb2bf',
  field: '#abb2bf',
  property: '#abb2bf',
}

function getKindColor(kind: string): string {
  return KIND_COLORS[kind] ?? '#abb2bf'
}

function getKindIcon(kind: string): React.ReactNode {
  return KIND_ICONS[kind] ?? <FieldIcon fontSize="small" sx={{ color: '#abb2bf' }} />
}

function getKindLabel(kind: string, plural = false): string {
  const label = kind.replace(/_/g, ' ')
  if (!plural) return label
  if (label.endsWith('y') && !label.endsWith('ay')) return label.slice(0, -1) + 'ies'
  if (label.endsWith('s')) return label + 'es'
  return label + 's'
}

const KIND_PAGE_SIZE = 100

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
  const fileParam = searchParams.get('file')
  const kindParam = searchParams.get('kind')

  // Resolve default branch and latest commit when missing from URL
  useEffect(() => {
    if (!repoName || (branch && commit)) return
    let cancelled = false
    const resolve = async () => {
      try {
        const repo = await getRepositoryByName(repoName)
        if (cancelled) return
        const effectiveBranch = branch ?? repo.default_branch
        let effectiveCommit = commit
        if (!effectiveCommit) {
          const commits = await getCommits(repoName, effectiveBranch, 1)
          if (cancelled) return
          if (commits.commits.length > 0) {
            effectiveCommit = commits.commits[0]!.hash
          }
        }
        if (cancelled) return
        const params = new URLSearchParams(searchParams)
        if (!branch) params.set('branch', effectiveBranch)
        if (!commit && effectiveCommit) params.set('commit', effectiveCommit)
        navigate(`/logical-view?${params.toString()}`, { replace: true })
      } catch {
        // Silently fail — page will work without defaults, just slower
      }
    }
    resolve()
    return () => {
      cancelled = true
    }
  }, [repoName, branch, commit, searchParams, navigate])

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
  const [activeKind, setActiveKind] = useState<string | null>(kindParam)

  // Sync activeKind with URL on browser back/forward navigation
  useEffect(() => {
    setActiveKind(kindParam ?? null)
  }, [kindParam])
  const [showKindCounts, setShowKindCounts] = useState(false)
  const [symbolSearch, setSymbolSearch] = useState('')
  const [symbolSearchMatchFileIds, setSymbolSearchMatchFileIds] = useState<Set<number> | null>(null)
  const [symbolSearchMatchIds, setSymbolSearchMatchIds] = useState<Set<number>>(new Set())
  const [symbolSearchLoading, setSymbolSearchLoading] = useState(false)
  const [repositoryId, setRepositoryId] = useState<number | null>(null)

  // Kind mode state
  const [kindSymbols, setKindSymbols] = useState<ApiSymbol[]>([])
  const [kindSymbolsLoading, setKindSymbolsLoading] = useState(false)
  const [kindSymbolsHasMore, setKindSymbolsHasMore] = useState(false)
  const [kindSymbolsOffset, setKindSymbolsOffset] = useState(0)
  const [kindExpandedSymbols, setKindExpandedSymbols] = useState<Set<number>>(new Set())
  const [kindSymbolChildren, setKindSymbolChildren] = useState<SymbolChildren>({})
  const [kindExpandingSymbol, setKindExpandingSymbol] = useState<number | null>(null)

  const symbolSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const savedScrollTop = useRef(0)
  const initialFileExpanded = useRef(false)

  // Derive available languages from loaded files
  const availableLanguages = useMemo(() => {
    const langs = new Set<string>()
    for (const f of files) {
      if (f.language) langs.add(f.language)
    }
    return [...langs].sort()
  }, [files])

  // Available kinds and total counts from backend (tier 1 response)
  const [availableKinds, setAvailableKinds] = useState<string[]>([])
  const [totalKindCounts, setTotalKindCounts] = useState<Record<string, number>>({})

  // Load tier 1 (files) when repo/branch/commit changes
  useEffect(() => {
    if (!repoName || !branch) {
      setFiles([])
      setAvailableKinds([])
      setTotalKindCounts({})
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
      initialFileExpanded.current = false

      try {
        const result = await getSymbolTree(repoName, {
          branch: branch ?? undefined,
          commit: commit ?? undefined,
        })
        if (!cancelled) {
          if (result.files) setFiles(result.files)
          if (result.available_kinds) setAvailableKinds(result.available_kinds)
          if (result.total_kind_counts) setTotalKindCounts(result.total_kind_counts)
          setRepositoryId(result.repository_id)
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

  // Debounced symbol search
  useEffect(() => {
    if (symbolSearchTimer.current) clearTimeout(symbolSearchTimer.current)

    if (!symbolSearch.trim() || !repositoryId) {
      setSymbolSearchMatchFileIds(null)
      setSymbolSearchMatchIds(new Set())
      setSymbolSearchLoading(false)
      return
    }

    setSymbolSearchLoading(true)
    symbolSearchTimer.current = setTimeout(async () => {
      try {
        const result = await searchSymbols({
          q: symbolSearch.trim(),
          repository_id: repositoryId,
          branch: branch ?? undefined,
          commit: commit ?? undefined,
          case_sensitive: false,
          kind: activeKind ?? undefined,
          limit: 200,
        })
        const fileIds = new Set(result.items.map((s) => s.file_id))
        const ids = new Set(result.items.map((s) => s.id))
        setSymbolSearchMatchFileIds(fileIds)
        setSymbolSearchMatchIds(ids)
      } catch {
        setSymbolSearchMatchFileIds(null)
        setSymbolSearchMatchIds(new Set())
      } finally {
        setSymbolSearchLoading(false)
      }
    }, 300)

    return () => {
      if (symbolSearchTimer.current) clearTimeout(symbolSearchTimer.current)
    }
  }, [symbolSearch, repositoryId, branch, commit, activeKind])

  // Update URL to reflect current browsing state
  const updateUrlState = useCallback(
    (updates: { file?: string | null; kind?: string | null }) => {
      const params = new URLSearchParams(searchParams)
      if ('file' in updates) {
        if (updates.file) {
          params.set('file', updates.file)
        } else {
          params.delete('file')
        }
      }
      if ('kind' in updates) {
        if (updates.kind) {
          params.set('kind', updates.kind)
        } else {
          params.delete('kind')
        }
      }
      navigate(`/logical-view?${params.toString()}`, { replace: true })
    },
    [searchParams, navigate]
  )

  // Expand/collapse a file (tier 2)
  const toggleFile = useCallback(
    async (fileId: number) => {
      if (expanded.files.has(fileId)) {
        setExpanded((prev) => {
          const newFiles = new Set(prev.files)
          newFiles.delete(fileId)
          return { ...prev, files: newFiles }
        })
        return
      }

      // Fetch symbols if not cached
      let symbols = fileSymbols[fileId]
      if (!symbols && repoName) {
        setExpandingFile(fileId)
        try {
          const result: SymbolTreeResponse = await getSymbolTree(repoName, {
            branch: branch ?? undefined,
            commit: commit ?? undefined,
            file_id: fileId,
          })
          if (result.symbols) {
            symbols = result.symbols
            setFileSymbols((prev) => ({ ...prev, [fileId]: result.symbols! }))
          }
        } catch {
          // Silently fail — file just won't expand
        } finally {
          setExpandingFile(null)
        }
      }

      // Auto-expand all symbols with children under this file
      const autoExpandIds: number[] = []
      if (symbols && repoName) {
        for (const s of symbols) {
          if (s.has_children) {
            if (!symbolChildren[s.id]) {
              try {
                const childResult = await getSymbolTree(repoName, {
                  branch: branch ?? undefined,
                  commit: commit ?? undefined,
                  parent_symbol_id: s.id,
                })
                if (childResult.symbols) {
                  setSymbolChildren((prev) => ({ ...prev, [s.id]: childResult.symbols! }))
                }
              } catch {
                // Silently fail
              }
            }
            autoExpandIds.push(s.id)
          }
        }
      }

      setExpanded((prev) => {
        const newFiles = new Set(prev.files)
        newFiles.add(fileId)
        const newSyms = new Set(prev.symbols)
        for (const id of autoExpandIds) newSyms.add(id)
        return { files: newFiles, symbols: newSyms }
      })

      const file = files.find((f) => f.file_id === fileId)
      if (file) updateUrlState({ file: file.path })
    },
    [expanded.files, fileSymbols, symbolChildren, repoName, branch, commit, updateUrlState, files]
  )

  // Expand/collapse a symbol (tier 3)
  const toggleSymbol = useCallback(
    async (symbolId: number) => {
      if (expanded.symbols.has(symbolId)) {
        setExpanded((prev) => {
          const newSymbols = new Set(prev.symbols)
          newSymbols.delete(symbolId)
          return { ...prev, symbols: newSymbols }
        })
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

      setExpanded((prev) => {
        const newSymbols = new Set(prev.symbols)
        newSymbols.add(symbolId)
        return { ...prev, symbols: newSymbols }
      })
    },
    [expanded.symbols, symbolChildren, repoName, branch, commit]
  )

  // Fetch symbols when entering kind mode
  useEffect(() => {
    if (!activeKind || !repositoryId || !branch) {
      setKindSymbols([])
      setKindExpandedSymbols(new Set())
      setKindSymbolChildren({})
      return
    }

    let cancelled = false
    const loadKindSymbols = async () => {
      setKindSymbolsLoading(true)
      setKindSymbols([])
      setKindSymbolsHasMore(false)
      setKindSymbolsOffset(0)
      setKindExpandedSymbols(new Set())
      setKindSymbolChildren({})

      try {
        const result = await searchSymbols({
          kind: activeKind,
          repository_id: repositoryId,
          branch: branch ?? undefined,
          commit: commit ?? undefined,
          top_level_only: false,
          limit: KIND_PAGE_SIZE,
          offset: 0,
        })
        if (cancelled) return
        setKindSymbols(result.items)
        setKindSymbolsHasMore(result.items.length === KIND_PAGE_SIZE)
        setKindSymbolsOffset(KIND_PAGE_SIZE)
      } catch {
        // Silently fail
      } finally {
        if (!cancelled) setKindSymbolsLoading(false)
      }
    }
    loadKindSymbols()
    return () => {
      cancelled = true
    }
  }, [activeKind, repositoryId, branch, commit])

  // Load more symbols in kind mode
  const loadMoreKindSymbols = useCallback(async () => {
    if (!activeKind || !repositoryId || kindSymbolsLoading) return
    setKindSymbolsLoading(true)
    try {
      const result = await searchSymbols({
        kind: activeKind,
        repository_id: repositoryId,
        branch: branch ?? undefined,
        commit: commit ?? undefined,
        top_level_only: false,
        limit: KIND_PAGE_SIZE,
        offset: kindSymbolsOffset,
      })
      setKindSymbols((prev) => [...prev, ...result.items])
      setKindSymbolsHasMore(result.items.length === KIND_PAGE_SIZE)
      setKindSymbolsOffset((prev) => prev + KIND_PAGE_SIZE)
    } catch {
      // Silently fail
    } finally {
      setKindSymbolsLoading(false)
    }
  }, [activeKind, repositoryId, branch, commit, kindSymbolsOffset, kindSymbolsLoading])

  // Expand/collapse a symbol in kind mode (fetch children via symbol tree)
  const toggleKindSymbol = useCallback(
    async (symbolId: number) => {
      if (kindExpandedSymbols.has(symbolId)) {
        setKindExpandedSymbols((prev) => {
          const next = new Set(prev)
          next.delete(symbolId)
          return next
        })
        return
      }

      if (!kindSymbolChildren[symbolId] && repoName) {
        setKindExpandingSymbol(symbolId)
        try {
          const result: SymbolTreeResponse = await getSymbolTree(repoName, {
            branch: branch ?? undefined,
            commit: commit ?? undefined,
            parent_symbol_id: symbolId,
          })
          if (result.symbols) {
            setKindSymbolChildren((prev) => ({ ...prev, [symbolId]: result.symbols! }))
          }
        } catch {
          // Silently fail
        } finally {
          setKindExpandingSymbol(null)
        }
      }

      setKindExpandedSymbols((prev) => {
        const next = new Set(prev)
        next.add(symbolId)
        return next
      })
    },
    [kindExpandedSymbols, kindSymbolChildren, repoName, branch, commit]
  )

  // Switch from kind mode back to outline mode, expanding the file containing a symbol
  const switchToOutline = useCallback(
    (filePath: string) => {
      setActiveKind(null)
      updateUrlState({ file: filePath, kind: null })
      // Reset initialFileExpanded so the auto-expand effect triggers
      initialFileExpanded.current = false
    },
    [updateUrlState]
  )

  // Auto-expand file from URL param on initial load / bookmark navigation
  useEffect(() => {
    if (initialFileExpanded.current || !fileParam || !repoName || files.length === 0 || activeKind)
      return
    const file = files.find((f) => f.path === fileParam)
    if (!file) return
    initialFileExpanded.current = true

    let cancelled = false
    const expandFromUrl = async () => {
      const fileId = file.file_id

      // Fetch tier 2 symbols
      let symbols: SymbolTreeSymbol[] | undefined
      try {
        const result = await getSymbolTree(repoName, {
          branch: branch ?? undefined,
          commit: commit ?? undefined,
          file_id: fileId,
        })
        if (cancelled) return
        if (result.symbols) {
          symbols = result.symbols
          setFileSymbols((prev) => ({ ...prev, [fileId]: result.symbols! }))
        }
      } catch {
        return
      }

      if (!symbols || cancelled) return

      // Fetch tier 3 children for symbols that have them
      const autoExpandIds: number[] = []
      for (const s of symbols) {
        if (s.has_children) {
          try {
            const childResult = await getSymbolTree(repoName, {
              branch: branch ?? undefined,
              commit: commit ?? undefined,
              parent_symbol_id: s.id,
            })
            if (cancelled) return
            if (childResult.symbols) {
              setSymbolChildren((prev) => ({ ...prev, [s.id]: childResult.symbols! }))
            }
          } catch {
            // continue with other symbols
          }
          autoExpandIds.push(s.id)
        }
      }

      if (cancelled) return

      setExpanded((prev) => {
        const newFiles = new Set(prev.files)
        newFiles.add(fileId)
        const newSyms = new Set(prev.symbols)
        for (const id of autoExpandIds) newSyms.add(id)
        return { files: newFiles, symbols: newSyms }
      })

      // Scroll into view after render
      setTimeout(() => {
        const el = document.querySelector(`[data-file-id="${fileId}"]`)
        el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 300)
    }

    expandFromUrl()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileParam, files.length, repoName, branch, commit])

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

  // Symbol context menu state
  const [symbolContextMenu, setSymbolContextMenu] = useState<SymbolContextMenuState | null>(null)
  const symbolContextMenuRef = useRef<{
    symbol: SymbolTreeSymbol | null
  }>({ symbol: null })

  // Selection toolbar for copy + search on any selected text
  const {
    toolbar,
    containerRef: toolbarContainerRef,
    handleClose: handleToolbarClose,
  } = useSelectionToolbar()

  const handleSymbolContextMenu = useCallback(
    (symbol: SymbolTreeSymbol, event: React.MouseEvent) => {
      event.preventDefault()
      event.stopPropagation()
      symbolContextMenuRef.current.symbol = symbol
      setSymbolContextMenu({
        mouseX: event.clientX,
        mouseY: event.clientY,
        symbolName: symbol.name,
        hasDefinition: !!symbol.file_path,
      })
    },
    []
  )

  const handleSymbolContextMenuClose = useCallback(() => {
    setSymbolContextMenu(null)
  }, [])

  const handleCopySymbolName = useCallback(() => {
    const name = symbolContextMenuRef.current.symbol?.name
    if (name) {
      navigator.clipboard?.writeText(name)
    }
  }, [])

  const handleSearchSymbol = useCallback(() => {
    const name = symbolContextMenuRef.current.symbol?.name
    if (!name || !repoName) return
    const params = new URLSearchParams()
    params.set('repo', repoName)
    if (branch) params.set('branch', branch)
    if (commit) params.set('commit', commit)
    params.set('query', name)
    navigate(`/search?${params.toString()}`)
  }, [repoName, branch, commit, navigate])

  const handleGoToDefinition = useCallback(() => {
    const symbol = symbolContextMenuRef.current.symbol
    if (symbol) {
      handleSymbolClick(symbol)
    }
  }, [handleSymbolClick])

  // Header handlers
  const handleRepoChange = (newRepo: string) => {
    // Reset all UI state when switching repos
    setSymbolSearch('')
    setFilterText('')
    setExcludeText('')
    setSelectedLanguage(null)
    setActiveKind(null)
    setShowKindCounts(false)
    setExpanded({ files: new Set(), symbols: new Set() })
    setKindExpandedSymbols(new Set())
    setKindSymbolChildren({})
    setKindSymbols([])
    savedScrollTop.current = 0
    initialFileExpanded.current = false
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
    if (symbolSearchMatchFileIds) {
      result = result.filter((f) => symbolSearchMatchFileIds.has(f.file_id))
    }
    return result
  }, [files, selectedLanguage, filterText, excludeText, fileSymbols, symbolSearchMatchFileIds])

  // Filter kind-mode symbols by text, language, and symbol search
  const filteredKindSymbols = useMemo(() => {
    let result = kindSymbols
    if (selectedLanguage) {
      result = result.filter((s) => {
        // Match language from file extension
        const ext = s.file_path?.split('.').pop()?.toLowerCase()
        const langMap: Record<string, string> = {
          py: 'python',
          ts: 'typescript',
          tsx: 'typescript',
          js: 'javascript',
          jsx: 'javascript',
          rb: 'ruby',
          go: 'go',
          rs: 'rust',
          java: 'java',
          cs: 'csharp',
          cpp: 'cpp',
          c: 'c',
          h: 'cpp',
          sh: 'bash',
          bash: 'bash',
        }
        return ext ? langMap[ext] === selectedLanguage : false
      })
    }
    if (filterText) {
      const lower = filterText.toLowerCase()
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(lower) ||
          (s.file_path?.toLowerCase().includes(lower) ?? false)
      )
    }
    if (excludeText) {
      const lower = excludeText.toLowerCase()
      result = result.filter(
        (s) =>
          !s.name.toLowerCase().includes(lower) &&
          !(s.file_path?.toLowerCase().includes(lower) ?? false)
      )
    }
    if (symbolSearch.trim()) {
      const lower = symbolSearch.trim().toLowerCase()
      result = result.filter((s) => s.name.toLowerCase().includes(lower))
    }
    return result
  }, [kindSymbols, selectedLanguage, filterText, excludeText, symbolSearch])

  // Group kind mode symbols by parent class (from qualified_name)
  const groupedKindSymbols = useMemo(() => {
    const groups: {
      groupKey: string
      className: string | null
      filePath: string | null
      symbols: ApiSymbol[]
    }[] = []
    const groupMap = new Map<string, { filePath: string | null; symbols: ApiSymbol[] }>()
    const ungrouped: ApiSymbol[] = []

    for (const sym of filteredKindSymbols) {
      // Extract parent class from qualified_name (e.g., "ClassName.method" -> "ClassName")
      const qn = sym.qualified_name
      const dotIdx = qn ? qn.lastIndexOf('.') : -1
      const parentName = dotIdx > 0 ? qn!.slice(0, dotIdx) : null

      if (parentName) {
        const key = `${parentName}::${sym.file_path ?? ''}`
        const existing = groupMap.get(key)
        if (existing) {
          existing.symbols.push(sym)
        } else {
          const group = { filePath: sym.file_path, symbols: [sym] }
          groupMap.set(key, group)
        }
      } else {
        ungrouped.push(sym)
      }
    }

    // Sort groups by class name, ungrouped items first
    if (ungrouped.length > 0) {
      groups.push({ groupKey: '__ungrouped', className: null, filePath: null, symbols: ungrouped })
    }
    const sortedEntries = [...groupMap.entries()].sort((a, b) => a[0].localeCompare(b[0]))
    for (const [key, group] of sortedEntries) {
      groups.push({
        groupKey: key,
        className: key.split('::')[0]!,
        filePath: group.filePath,
        symbols: group.symbols,
      })
    }

    return groups
  }, [filteredKindSymbols])

  // Summary stats — always total counts, but filter to active kind when in kind mode
  const summaryStats = useMemo(() => {
    if (activeKind) {
      const count = totalKindCounts[activeKind] ?? 0
      return { files: files.length, kinds: count > 0 ? { [activeKind]: count } : {} }
    }
    return { files: files.length, kinds: totalKindCounts }
  }, [activeKind, files, totalKindCounts])

  // Restore scroll position after filter/search changes re-render the list
  useLayoutEffect(() => {
    if (scrollRef.current && savedScrollTop.current > 0) {
      scrollRef.current.scrollTop = savedScrollTop.current
    }
  }, [filteredFiles])

  const handleScroll = useCallback(() => {
    if (scrollRef.current) {
      savedScrollTop.current = scrollRef.current.scrollTop
    }
  }, [])

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
              placeholder="Find symbol..."
              value={symbolSearch}
              onChange={(e) => setSymbolSearch(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" color="primary" />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end" sx={{ gap: 0.5 }}>
                    {symbolSearchLoading && <CircularProgress size={14} />}
                    {!symbolSearchLoading && symbolSearch && symbolSearchMatchFileIds && (
                      <Typography variant="caption" color="text.secondary">
                        {symbolSearchMatchFileIds.size}
                      </Typography>
                    )}
                    {symbolSearch && (
                      <IconButton size="small" onClick={() => setSymbolSearch('')} edge="end">
                        <ClearIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    )}
                  </InputAdornment>
                ),
              }}
              sx={{ maxWidth: 250 }}
            />
            <TextField
              size="small"
              placeholder="Include files..."
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
                endAdornment: filterText ? (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setFilterText('')} edge="end">
                      <ClearIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </InputAdornment>
                ) : undefined,
              }}
              sx={{ maxWidth: 250 }}
            />
            <TextField
              size="small"
              placeholder="Exclude files..."
              value={excludeText}
              onChange={(e) => setExcludeText(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <BlockIcon fontSize="small" color="error" />
                  </InputAdornment>
                ),
                endAdornment: excludeText ? (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setExcludeText('')} edge="end">
                      <ClearIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </InputAdornment>
                ) : undefined,
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
            <Tooltip title="Reset view" arrow>
              <IconButton
                size="small"
                onClick={() => {
                  setSymbolSearch('')
                  setFilterText('')
                  setExcludeText('')
                  setSelectedLanguage(null)
                  setActiveKind(null)
                  setShowKindCounts(false)
                  setExpanded({ files: new Set(), symbols: new Set() })
                  setKindExpandedSymbols(new Set())
                  setKindSymbolChildren({})
                  updateUrlState({ file: null, kind: null })
                  savedScrollTop.current = 0
                  if (scrollRef.current) scrollRef.current.scrollTop = 0
                }}
                color="warning"
              >
                <RestartAltIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {availableKinds.length > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
                <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
                  View:
                </Typography>
                <Chip
                  label="Outline"
                  size="small"
                  icon={<AccountTreeIcon sx={{ fontSize: 14 }} />}
                  variant={activeKind === null ? 'filled' : 'outlined'}
                  color={activeKind === null ? 'primary' : 'default'}
                  onClick={() => {
                    setActiveKind(null)
                    updateUrlState({ kind: null })
                  }}
                  sx={{ height: 24 }}
                />
                {availableKinds.map((kind) => (
                  <Chip
                    key={kind}
                    label={getKindLabel(kind)}
                    size="small"
                    icon={<>{getKindIcon(kind)}</>}
                    variant={activeKind === kind ? 'filled' : 'outlined'}
                    color={activeKind === kind ? 'primary' : 'default'}
                    onClick={() => {
                      const newKind = activeKind === kind ? null : kind
                      setActiveKind(newKind)
                      updateUrlState({ kind: newKind })
                    }}
                    sx={{ height: 24 }}
                  />
                ))}
                {activeKind === null && (
                  <Tooltip title={showKindCounts ? 'Hide kind counts' : 'Show kind counts'} arrow>
                    <IconButton
                      size="small"
                      onClick={() => setShowKindCounts((prev) => !prev)}
                      sx={{ ml: 0.5 }}
                    >
                      {showKindCounts ? (
                        <TagIcon fontSize="small" />
                      ) : (
                        <VisibilityOffIcon fontSize="small" />
                      )}
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            )}
          </Box>
        )}

        {/* Summary stats */}
        {repoName && !loading && !error && summaryStats.files > 0 && (
          <Box
            sx={{
              px: 2,
              py: 0.5,
              borderBottom: 1,
              borderColor: 'divider',
              display: 'flex',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 1.5,
              rowGap: 0.25,
              bgcolor: 'action.hover',
            }}
          >
            {summaryStats.files > 0 && (
              <Typography variant="caption" color="text.secondary">
                <strong>{summaryStats.files}</strong> files
              </Typography>
            )}
            {Object.entries(summaryStats.kinds)
              .sort(([, a], [, b]) => b - a)
              .map(([kind, count]) => (
                <Typography
                  key={kind}
                  variant="caption"
                  sx={{
                    color: getKindColor(kind),
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.3,
                  }}
                >
                  {getKindIcon(kind)}
                  <strong>{count}</strong> {getKindLabel(kind, count !== 1)}
                </Typography>
              ))}
          </Box>
        )}

        {/* Content */}
        <Box
          ref={(el: HTMLDivElement | null) => {
            ;(scrollRef as React.MutableRefObject<HTMLDivElement | null>).current = el
            toolbarContainerRef.current = el
          }}
          onScroll={handleScroll}
          sx={{ flex: 1, overflow: 'auto' }}
        >
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

          {/* Kind mode view */}
          {activeKind && !loading && !error && (
            <>
              {kindSymbolsLoading && (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 4 }}>
                  <CircularProgress size={24} />
                  <Typography color="text.secondary" sx={{ ml: 1 }}>
                    Loading {getKindLabel(activeKind)} symbols...
                  </Typography>
                </Box>
              )}
              {!kindSymbolsLoading && filteredKindSymbols.length === 0 && (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 4 }}>
                  <Typography color="text.secondary">
                    No {getKindLabel(activeKind)} symbols found
                  </Typography>
                </Box>
              )}
              {!kindSymbolsLoading && filteredKindSymbols.length > 0 && (
                <List dense disablePadding>
                  <Box sx={{ px: 2, py: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      {filteredKindSymbols.length}
                      {kindSymbolsHasMore ? '+' : ''}{' '}
                      {getKindLabel(activeKind, filteredKindSymbols.length !== 1)}
                    </Typography>
                  </Box>
                  {groupedKindSymbols.map((group) => (
                    <Box key={group.groupKey}>
                      {group.className && (
                        <ListItemButton
                          sx={{ pl: 2, py: 0.25, opacity: 0.8, cursor: 'default' }}
                          disableRipple
                        >
                          <ListItemIcon sx={{ minWidth: 28 }}>{getKindIcon('class')}</ListItemIcon>
                          <ListItemText
                            primary={
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Typography
                                  variant="body2"
                                  sx={{ fontWeight: 600, fontFamily: 'monospace' }}
                                >
                                  {group.className}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {group.filePath
                                    ? fileDir(group.filePath) + fileName(group.filePath)
                                    : ''}
                                </Typography>
                                <Chip
                                  label={group.symbols.length}
                                  size="small"
                                  sx={{ height: 18, fontSize: '0.7rem' }}
                                />
                              </Box>
                            }
                          />
                        </ListItemButton>
                      )}
                      {group.symbols.map((sym) => (
                        <KindSymbolNode
                          key={sym.id}
                          symbol={sym}
                          isExpanded={kindExpandedSymbols.has(sym.id)}
                          isExpanding={kindExpandingSymbol === sym.id}
                          children={kindSymbolChildren[sym.id]}
                          symbolChildren={kindSymbolChildren}
                          expandedSymbols={kindExpandedSymbols}
                          expandingSymbol={kindExpandingSymbol}
                          onToggle={toggleKindSymbol}
                          onSymbolClick={handleSymbolClick}
                          onInheritanceClick={handleInheritanceClick}
                          onSymbolContextMenu={handleSymbolContextMenu}
                          onSwitchToOutline={switchToOutline}
                          fileName={fileName}
                          fileDir={fileDir}
                          indent={group.className ? 1 : 0}
                        />
                      ))}
                    </Box>
                  ))}
                  {kindSymbolsHasMore && (
                    <Box sx={{ px: 2, py: 1, textAlign: 'center' }}>
                      <Chip
                        label={kindSymbolsLoading ? 'Loading...' : 'Load more'}
                        onClick={kindSymbolsLoading ? undefined : loadMoreKindSymbols}
                        variant="outlined"
                        size="small"
                        disabled={kindSymbolsLoading}
                      />
                    </Box>
                  )}
                </List>
              )}
            </>
          )}

          {/* Outline mode view */}
          {!activeKind && filteredFiles.length > 0 && (
            <List dense disablePadding>
              {filteredFiles.map((file) => (
                <FileNode
                  key={file.file_id}
                  file={file}
                  isExpanded={expanded.files.has(file.file_id)}
                  isExpanding={expandingFile === file.file_id}
                  symbols={fileSymbols[file.file_id]}
                  showKindCounts={showKindCounts}
                  highlightedSymbolIds={symbolSearchMatchIds}
                  symbolChildren={symbolChildren}
                  expandedSymbols={expanded.symbols}
                  expandingSymbol={expandingSymbol}
                  onToggle={toggleFile}
                  onToggleSymbol={toggleSymbol}
                  onSymbolClick={handleSymbolClick}
                  onInheritanceClick={handleInheritanceClick}
                  onSymbolContextMenu={handleSymbolContextMenu}
                  fileName={fileName}
                  fileDir={fileDir}
                />
              ))}
            </List>
          )}
        </Box>
      </Box>
      <SymbolContextMenu
        contextMenu={symbolContextMenu}
        onCopyName={handleCopySymbolName}
        onSearchSymbol={handleSearchSymbol}
        onGoToDefinition={handleGoToDefinition}
        onClose={handleSymbolContextMenuClose}
      />
      <SelectionToolbar
        toolbar={toolbar}
        onCopy={() => {
          const text = toolbar?.selectedText
          if (text) navigator.clipboard?.writeText(text)
        }}
        onSearch={() => {
          const text = toolbar?.selectedText
          if (!text || !repoName) return
          const params = new URLSearchParams()
          params.set('repo', repoName)
          if (branch) params.set('branch', branch)
          if (commit) params.set('commit', commit)
          params.set('query', text)
          navigate(`/search?${params.toString()}`)
        }}
        onClose={handleToolbarClose}
      />
    </Box>
  )
}

// --- Sub-components ---

interface FileNodeProps {
  file: SymbolTreeFile
  isExpanded: boolean
  isExpanding: boolean
  symbols: SymbolTreeSymbol[] | undefined
  showKindCounts: boolean
  highlightedSymbolIds: Set<number>
  symbolChildren: SymbolChildren
  expandedSymbols: Set<number>
  expandingSymbol: number | null
  onToggle: (fileId: number) => void
  onToggleSymbol: (symbolId: number) => void
  onSymbolClick: (symbol: SymbolTreeSymbol) => void
  onInheritanceClick: (inh: SymbolTreeInheritance, e: React.MouseEvent) => void
  onSymbolContextMenu: (symbol: SymbolTreeSymbol, e: React.MouseEvent) => void
  fileName: (path: string) => string
  fileDir: (path: string) => string
}

function FileNode({
  file,
  isExpanded,
  isExpanding,
  symbols,
  showKindCounts,
  highlightedSymbolIds,
  symbolChildren,
  expandedSymbols,
  expandingSymbol,
  onToggle,
  onToggleSymbol,
  onSymbolClick,
  onInheritanceClick,
  onSymbolContextMenu,
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
              {showKindCounts &&
                Object.entries(file.all_kind_counts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([kind, count]) => (
                    <Chip
                      key={kind}
                      label={`${count} ${getKindLabel(kind, count !== 1)}`}
                      size="small"
                      sx={{
                        height: 18,
                        fontSize: '0.65rem',
                        backgroundColor: getKindColor(kind) + '22',
                        color: getKindColor(kind),
                        borderColor: getKindColor(kind) + '44',
                        border: '1px solid',
                      }}
                    />
                  ))}
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
            highlightedSymbolIds={highlightedSymbolIds}
            onToggle={onToggleSymbol}
            onClick={onSymbolClick}
            onInheritanceClick={onInheritanceClick}
            onContextMenuAction={onSymbolContextMenu}
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
  highlightedSymbolIds: Set<number>
  onToggle: (symbolId: number) => void
  onClick: (symbol: SymbolTreeSymbol) => void
  onInheritanceClick: (inh: SymbolTreeInheritance, e: React.MouseEvent) => void
  onContextMenuAction: (symbol: SymbolTreeSymbol, e: React.MouseEvent) => void
}

function SymbolNode({
  symbol,
  level,
  children,
  expandedSymbols,
  expandingSymbol,
  symbolChildren,
  highlightedSymbolIds,
  onToggle,
  onClick,
  onInheritanceClick,
  onContextMenuAction,
}: SymbolNodeProps): React.ReactElement {
  const isExpanded = expandedSymbols.has(symbol.id)
  const isExpanding = expandingSymbol === symbol.id
  const indent = level * 24
  const isHighlighted = highlightedSymbolIds.size > 0 && highlightedSymbolIds.has(symbol.id)

  const handleClick = () => {
    if (symbol.has_children) {
      onToggle(symbol.id)
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
        onContextMenu={(e) => onContextMenuAction(symbol, e)}
        sx={{
          pl: `${indent + 16}px`,
          py: 0.25,
          cursor: symbol.has_children ? 'pointer' : 'default',
          ...(isHighlighted && {
            backgroundColor: 'rgba(97, 175, 239, 0.12)',
          }),
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
              <Typography
                variant="body2"
                component="span"
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: symbol.has_children || isHighlighted ? 500 : 400,
                  userSelect: 'text',
                  ...(isHighlighted && {
                    color: '#61afef',
                  }),
                }}
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
              <Tooltip title={`Go to line ${symbol.start_line}`} arrow>
                <IconButton
                  size="small"
                  onClick={handleNavigate}
                  sx={{ p: 0.25 }}
                  aria-label={`Go to line ${symbol.start_line}`}
                >
                  <ArrowForwardIcon sx={{ fontSize: 14 }} />
                </IconButton>
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
              highlightedSymbolIds={highlightedSymbolIds}
              onToggle={onToggle}
              onClick={onClick}
              onInheritanceClick={onInheritanceClick}
              onContextMenuAction={onContextMenuAction}
            />
          ))}
        </Collapse>
      )}
    </>
  )
}

// --- Kind mode symbol node ---

interface KindSymbolNodeProps {
  symbol: ApiSymbol
  isExpanded: boolean
  isExpanding: boolean
  children: SymbolTreeSymbol[] | undefined
  symbolChildren: SymbolChildren
  expandedSymbols: Set<number>
  expandingSymbol: number | null
  onToggle: (symbolId: number) => void
  onSymbolClick: (symbol: SymbolTreeSymbol) => void
  onInheritanceClick: (inh: SymbolTreeInheritance, e: React.MouseEvent) => void
  onSymbolContextMenu: (symbol: SymbolTreeSymbol, e: React.MouseEvent) => void
  onSwitchToOutline: (filePath: string) => void
  fileName: (path: string) => string
  fileDir: (path: string) => string
  indent?: number
}

function KindSymbolNode({
  symbol,
  isExpanded,
  isExpanding,
  children,
  symbolChildren,
  expandedSymbols,
  expandingSymbol,
  onToggle,
  onSymbolClick,
  onInheritanceClick,
  onSymbolContextMenu,
  onSwitchToOutline,
  fileName,
  fileDir,
  indent = 0,
}: KindSymbolNodeProps): React.ReactElement {
  const isCallable =
    symbol.kind === 'function' ||
    symbol.kind === 'method' ||
    symbol.kind === 'constructor' ||
    symbol.kind === 'staticmethod' ||
    symbol.kind === 'classmethod'

  const isContainer =
    symbol.kind === 'class' ||
    symbol.kind === 'interface' ||
    symbol.kind === 'struct' ||
    symbol.kind === 'record' ||
    symbol.kind === 'enum' ||
    symbol.kind === 'namespace'

  // Convert ApiSymbol to SymbolTreeSymbol shape for navigation
  const asTreeSymbol: SymbolTreeSymbol = useMemo(
    () => ({
      id: symbol.id,
      name: symbol.name,
      kind: symbol.kind,
      start_line: symbol.start_line,
      end_line: symbol.end_line,
      file_path: symbol.file_path,
      has_children: isContainer,
      signature: symbol.signature,
      inheritance: [],
    }),
    [symbol, isContainer]
  )

  return (
    <>
      <ListItemButton
        onClick={isContainer ? () => onToggle(symbol.id) : undefined}
        onContextMenu={(e) => onSymbolContextMenu(asTreeSymbol, e)}
        sx={{ py: 0.5, pl: 2 + indent * 3, cursor: isContainer ? 'pointer' : 'default' }}
      >
        {isContainer && (
          <ListItemIcon sx={{ minWidth: 28 }}>
            {isExpanding ? (
              <CircularProgress size={16} />
            ) : isExpanded ? (
              <ExpandMoreIcon fontSize="small" />
            ) : (
              <ChevronRightIcon fontSize="small" />
            )}
          </ListItemIcon>
        )}
        {!isContainer && <Box sx={{ width: 28 }} />}
        <ListItemIcon sx={{ minWidth: 24 }}>{getKindIcon(symbol.kind)}</ListItemIcon>
        <ListItemText
          primary={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography
                variant="body2"
                component="span"
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: 500,
                  userSelect: 'text',
                }}
              >
                {symbol.name}
                {isCallable ? '()' : ''}
              </Typography>
              <Tooltip title={`Go to line ${symbol.start_line}`} arrow>
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation()
                    onSymbolClick(asTreeSymbol)
                  }}
                  sx={{ p: 0.25 }}
                  aria-label={`Go to line ${symbol.start_line}`}
                >
                  <ArrowForwardIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
              {symbol.file_path && (
                <Tooltip title="View in Outline mode" arrow>
                  <Typography
                    variant="caption"
                    component="span"
                    sx={{
                      fontFamily: 'monospace',
                      color: 'text.secondary',
                      cursor: 'pointer',
                      '&:hover': { color: 'primary.main', textDecoration: 'underline' },
                    }}
                    onClick={(e) => {
                      e.stopPropagation()
                      onSwitchToOutline(symbol.file_path!)
                    }}
                  >
                    {fileDir(symbol.file_path)}
                    <Typography
                      variant="caption"
                      component="span"
                      sx={{ fontFamily: 'monospace', color: 'text.primary' }}
                    >
                      {fileName(symbol.file_path)}
                    </Typography>
                  </Typography>
                </Tooltip>
              )}
            </Box>
          }
        />
      </ListItemButton>

      {isContainer && (
        <Collapse in={isExpanded} timeout="auto">
          {children?.map((child) => (
            <SymbolNode
              key={child.id}
              symbol={child}
              level={1}
              children={symbolChildren[child.id]}
              expandedSymbols={expandedSymbols}
              expandingSymbol={expandingSymbol}
              symbolChildren={symbolChildren}
              highlightedSymbolIds={new Set()}
              onToggle={onToggle}
              onClick={onSymbolClick}
              onInheritanceClick={onInheritanceClick}
              onContextMenuAction={onSymbolContextMenu}
            />
          ))}
        </Collapse>
      )}
    </>
  )
}
