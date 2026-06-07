import { useState, useEffect, useLayoutEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
  Typography,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  Alert,
  TextField,
  InputAdornment,
  Chip,
  Tooltip,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import BlockIcon from '@mui/icons-material/Block'
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff'
import TagIcon from '@mui/icons-material/Tag'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import ClearIcon from '@mui/icons-material/Clear'
import RestartAltIcon from '@mui/icons-material/RestartAlt'
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
import {
  getKindColor,
  getKindLabel,
  getAvailableLanguages,
  filterFiles,
  filterKindSymbols,
  groupKindSymbols,
  computeSummaryStats,
  fileName,
  fileDir,
  type SymbolChildren,
} from '@/lib/logicalView'
import { getKindIcon } from '@/components/logicalView/kindIcons'
import { FileNode } from '@/components/logicalView/FileNode'
import { KindSymbolNode } from '@/components/logicalView/KindSymbolNode'

const KIND_PAGE_SIZE = 100

interface ExpandedState {
  files: Set<number>
  symbols: Set<number>
}

export default function LogicalView(): React.ReactElement {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const repoName = searchParams.get('repo')
  const branch = searchParams.get('branch')
  const commit = searchParams.get('commit')
  const fileParam = searchParams.get('file')
  const kindParam = searchParams.get('kind')
  const languageParam = searchParams.get('language')?.trim().toLowerCase() || null

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
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(languageParam)
  const [activeKind, setActiveKind] = useState<string | null>(kindParam)

  // Sync activeKind and selectedLanguage with URL on browser back/forward navigation
  useEffect(() => {
    setActiveKind(kindParam ?? null)
  }, [kindParam])
  useEffect(() => {
    setSelectedLanguage(languageParam)
  }, [languageParam])
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
  const availableLanguages = useMemo(() => getAvailableLanguages(files), [files])

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
    (updates: { file?: string | null; kind?: string | null; language?: string | null }) => {
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
      if ('language' in updates) {
        if (updates.language) {
          params.set('language', updates.language)
        } else {
          params.delete('language')
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
          language: selectedLanguage ?? undefined,
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
  }, [activeKind, repositoryId, branch, commit, selectedLanguage])

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
        language: selectedLanguage ?? undefined,
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
  }, [
    activeKind,
    repositoryId,
    branch,
    commit,
    kindSymbolsOffset,
    kindSymbolsLoading,
    selectedLanguage,
  ])

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
  const filteredFiles = useMemo(
    () =>
      filterFiles(files, {
        selectedLanguage,
        filterText,
        excludeText,
        fileSymbols,
        symbolSearchMatchFileIds,
      }),
    [files, selectedLanguage, filterText, excludeText, fileSymbols, symbolSearchMatchFileIds]
  )

  // Filter kind-mode symbols by text, language, and symbol search
  const filteredKindSymbols = useMemo(
    () =>
      filterKindSymbols(kindSymbols, {
        selectedLanguage,
        filterText,
        excludeText,
        symbolSearch,
      }),
    [kindSymbols, selectedLanguage, filterText, excludeText, symbolSearch]
  )

  // Group kind mode symbols by parent class (from qualified_name)
  const groupedKindSymbols = useMemo(
    () => groupKindSymbols(filteredKindSymbols),
    [filteredKindSymbols]
  )

  // Summary stats — use filtered file count, filter to active kind when in kind mode
  const summaryStats = useMemo(
    () =>
      computeSummaryStats({
        activeKind,
        filteredFilesCount: filteredFiles.length,
        filteredKindSymbolsCount: filteredKindSymbols.length,
        totalKindCounts,
      }),
    [activeKind, filteredFiles, filteredKindSymbols, totalKindCounts]
  )

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
                  onClick={() => updateUrlState({ language: null })}
                  sx={{ height: 24 }}
                />
                {availableLanguages.map((lang) => (
                  <Chip
                    key={lang}
                    label={lang}
                    size="small"
                    variant={selectedLanguage === lang ? 'filled' : 'outlined'}
                    color={selectedLanguage === lang ? 'primary' : 'default'}
                    onClick={() =>
                      updateUrlState({ language: selectedLanguage === lang ? null : lang })
                    }
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
                  setActiveKind(null)
                  setShowKindCounts(false)
                  setExpanded({ files: new Set(), symbols: new Set() })
                  setKindExpandedSymbols(new Set())
                  setKindSymbolChildren({})
                  updateUrlState({ file: null, kind: null, language: null })
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
