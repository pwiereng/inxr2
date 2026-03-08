import { useState, useEffect, useMemo } from 'react'
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
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import SearchIcon from '@mui/icons-material/Search'
import { CodeHeader } from '@/components/CodeHeader'
import type { TabValue } from '@/components/CodeHeader'
import { getRepositoryDependencies, type DependencyItem } from '@/lib/api'

// Language colors (One Dark Pro palette, consistent with LogicalView)
const LANGUAGE_COLORS: Record<string, string> = {
  python: '#61afef',
  javascript: '#e5c07b',
  java: '#d19a66',
  csharp: '#c678dd',
}

// Dependency type colors
const TYPE_COLORS: Record<string, string> = {
  runtime: '#98c379',
  dev: '#61afef',
  optional: '#e5c07b',
  build: '#d19a66',
  peer: '#c678dd',
}

interface FileGroup {
  filePath: string
  fileId: number
  language: string
  items: DependencyItem[]
}

export default function Dependencies(): React.ReactElement {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const repoName = searchParams.get('repo')
  const branch = searchParams.get('branch')
  const commit = searchParams.get('commit')

  // Data state
  const [items, setItems] = useState<DependencyItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [commitHash, setCommitHash] = useState<string | null>(null)

  // UI state
  const [expandedFiles, setExpandedFiles] = useState<Set<number>>(new Set())
  const [filterText, setFilterText] = useState('')
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [selectedDirect, setSelectedDirect] = useState<boolean | null>(null)

  // Derive available languages and types from loaded items
  const availableLanguages = useMemo(() => {
    const langs = new Set<string>()
    for (const item of items) {
      langs.add(item.language)
    }
    return [...langs].sort()
  }, [items])

  const availableTypes = useMemo(() => {
    const types = new Set<string>()
    for (const item of items) {
      types.add(item.dependency_type)
    }
    return [...types].sort()
  }, [items])

  // Load dependencies when repo/branch/commit changes
  useEffect(() => {
    if (!repoName) {
      setItems([])
      setCommitHash(null)
      return
    }

    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      setItems([])
      setExpandedFiles(new Set())

      try {
        const result = await getRepositoryDependencies(repoName, {
          branch: branch ?? undefined,
          commit: commit ?? undefined,
        })
        if (!cancelled) {
          setItems(result.items)
          setCommitHash(result.commit_hash)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load dependencies')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [repoName, branch, commit])

  // Filter items
  const filteredItems = useMemo(() => {
    let result = items
    if (selectedLanguage) {
      result = result.filter((d) => d.language === selectedLanguage)
    }
    if (selectedType) {
      result = result.filter((d) => d.dependency_type === selectedType)
    }
    if (selectedDirect !== null) {
      result = result.filter((d) => d.is_direct === selectedDirect)
    }
    if (filterText) {
      const lower = filterText.toLowerCase()
      result = result.filter(
        (d) =>
          d.package_name.toLowerCase().includes(lower) ||
          (d.file_path ?? '').toLowerCase().includes(lower)
      )
    }
    return result
  }, [items, selectedLanguage, selectedType, selectedDirect, filterText])

  // Group filtered items by manifest file
  const fileGroups = useMemo(() => {
    const groupMap = new Map<number, FileGroup>()
    for (const item of filteredItems) {
      let group = groupMap.get(item.file_id)
      if (!group) {
        group = {
          filePath: item.file_path ?? `file:${item.file_id}`,
          fileId: item.file_id,
          language: item.language,
          items: [],
        }
        groupMap.set(item.file_id, group)
      }
      group.items.push(item)
    }
    return [...groupMap.values()].sort((a, b) => a.filePath.localeCompare(b.filePath))
  }, [filteredItems])

  // Toggle file expansion
  const toggleFile = (fileId: number) => {
    const next = new Set(expandedFiles)
    if (next.has(fileId)) {
      next.delete(fileId)
    } else {
      next.add(fileId)
    }
    setExpandedFiles(next)
  }

  // Navigate to manifest file in browse view
  const handleFileClick = (filePath: string) => {
    if (!repoName) return
    const params = new URLSearchParams()
    if (branch) params.set('branch', branch)
    if (commit) params.set('commit', commit)
    const encodedRepoName = encodeURIComponent(repoName)
    const encodedFilePath = filePath
      .split('/')
      .map((segment) => encodeURIComponent(segment))
      .join('/')
    navigate(`/browse/${encodedRepoName}/${encodedFilePath}?${params.toString()}`)
  }

  // Header handlers
  const handleRepoChange = (newRepo: string) => {
    const params = new URLSearchParams()
    params.set('repo', newRepo)
    navigate(`/dependencies?${params.toString()}`)
  }

  const handleBranchChange = (newBranch: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('branch', newBranch)
    params.delete('commit')
    navigate(`/dependencies?${params.toString()}`)
  }

  const handleCommitChange = (newCommit: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('commit', newCommit)
    navigate(`/dependencies?${params.toString()}`)
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

  // Count summary
  const directCount = filteredItems.filter((d) => d.is_direct).length
  const transitiveCount = filteredItems.filter((d) => !d.is_direct).length

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <CodeHeader
        currentTab="dependencies"
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
        {repoName && items.length > 0 && (
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
              placeholder="Filter packages..."
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

            {/* Language filter */}
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

            {/* Type filter */}
            {availableTypes.length > 1 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
                  Type:
                </Typography>
                <Chip
                  label="All"
                  size="small"
                  variant={selectedType === null ? 'filled' : 'outlined'}
                  color={selectedType === null ? 'primary' : 'default'}
                  onClick={() => setSelectedType(null)}
                  sx={{ height: 24 }}
                />
                {availableTypes.map((type) => (
                  <Chip
                    key={type}
                    label={type}
                    size="small"
                    variant={selectedType === type ? 'filled' : 'outlined'}
                    color={selectedType === type ? 'primary' : 'default'}
                    onClick={() => setSelectedType(selectedType === type ? null : type)}
                    sx={{ height: 24 }}
                  />
                ))}
              </Box>
            )}

            {/* Direct/transitive toggle */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
                Scope:
              </Typography>
              <Chip
                label="All"
                size="small"
                variant={selectedDirect === null ? 'filled' : 'outlined'}
                color={selectedDirect === null ? 'primary' : 'default'}
                onClick={() => setSelectedDirect(null)}
                sx={{ height: 24 }}
              />
              <Chip
                label={`Direct (${directCount})`}
                size="small"
                variant={selectedDirect === true ? 'filled' : 'outlined'}
                color={selectedDirect === true ? 'primary' : 'default'}
                onClick={() => setSelectedDirect(selectedDirect === true ? null : true)}
                sx={{ height: 24 }}
              />
              <Chip
                label={`Transitive (${transitiveCount})`}
                size="small"
                variant={selectedDirect === false ? 'filled' : 'outlined'}
                color={selectedDirect === false ? 'primary' : 'default'}
                onClick={() => setSelectedDirect(selectedDirect === false ? null : false)}
                sx={{ height: 24 }}
              />
            </Box>

            {/* Summary */}
            <Typography variant="caption" color="text.secondary">
              {filteredItems.length} packages in {fileGroups.length} files
              {commitHash && (
                <>
                  {' '}
                  @ <code>{commitHash.slice(0, 7)}</code>
                </>
              )}
            </Typography>
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
                Select a repository to browse its dependencies
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

          {repoName && !loading && !error && items.length === 0 && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
              }}
            >
              <Typography color="text.secondary">
                No dependencies found in this repository
              </Typography>
            </Box>
          )}

          {fileGroups.length > 0 && (
            <List dense disablePadding>
              {fileGroups.map((group) => (
                <FileGroupNode
                  key={group.fileId}
                  group={group}
                  isExpanded={expandedFiles.has(group.fileId)}
                  onToggle={toggleFile}
                  onFileClick={handleFileClick}
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

interface FileGroupNodeProps {
  group: FileGroup
  isExpanded: boolean
  onToggle: (fileId: number) => void
  onFileClick: (filePath: string) => void
}

function FileGroupNode({
  group,
  isExpanded,
  onToggle,
  onFileClick,
}: FileGroupNodeProps): React.ReactElement {
  const fileName = (path: string) => {
    const parts = path.split('/')
    return parts[parts.length - 1] ?? path
  }

  const fileDir = (path: string) => {
    const parts = path.split('/')
    if (parts.length <= 1) return ''
    return parts.slice(0, -1).join('/') + '/'
  }

  const dir = fileDir(group.filePath)
  const name = fileName(group.filePath)

  return (
    <>
      <ListItemButton onClick={() => onToggle(group.fileId)} sx={{ py: 0.5 }}>
        <ListItemIcon sx={{ minWidth: 28 }}>
          {isExpanded ? <ExpandMoreIcon fontSize="small" /> : <ChevronRightIcon fontSize="small" />}
        </ListItemIcon>
        <ListItemIcon sx={{ minWidth: 28 }}>
          {isExpanded ? (
            <FolderOpenIcon fontSize="small" color="primary" />
          ) : (
            <InsertDriveFileIcon fontSize="small" color="primary" />
          )}
        </ListItemIcon>
        <ListItemText
          primary={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Tooltip title="Open in Browse view" arrow>
                <Typography
                  variant="body2"
                  component="span"
                  sx={{
                    fontFamily: 'monospace',
                    cursor: 'pointer',
                    '&:hover': { textDecoration: 'underline' },
                  }}
                  onClick={(e) => {
                    e.stopPropagation()
                    onFileClick(group.filePath)
                  }}
                >
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
              </Tooltip>
              <Chip
                label={group.items.length}
                size="small"
                variant="outlined"
                sx={{ height: 18, fontSize: '0.7rem' }}
              />
              <Chip
                label={group.language}
                size="small"
                variant="outlined"
                sx={{
                  height: 18,
                  fontSize: '0.65rem',
                  color: LANGUAGE_COLORS[group.language] ?? '#abb2bf',
                  borderColor: LANGUAGE_COLORS[group.language] ?? '#abb2bf',
                }}
              />
            </Box>
          }
        />
      </ListItemButton>

      <Collapse in={isExpanded} timeout="auto">
        {group.items.map((item) => (
          <DependencyNode key={item.id} item={item} />
        ))}
      </Collapse>
    </>
  )
}

interface DependencyNodeProps {
  item: DependencyItem
}

function DependencyNode({ item }: DependencyNodeProps): React.ReactElement {
  return (
    <ListItemButton
      sx={{
        pl: `${24 + 16}px`,
        py: 0.25,
      }}
      disableRipple
    >
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
            <Typography
              variant="body2"
              component="span"
              sx={{ fontFamily: 'monospace', fontWeight: 500 }}
            >
              {item.package_name}
            </Typography>

            {item.version_spec && (
              <Typography variant="caption" color="text.disabled" sx={{ fontFamily: 'monospace' }}>
                {item.version_spec}
              </Typography>
            )}

            {item.resolved_version && item.resolved_version !== item.version_spec && (
              <Chip
                label={item.resolved_version}
                size="small"
                variant="outlined"
                color="success"
                sx={{ height: 18, fontSize: '0.65rem' }}
              />
            )}

            <Chip
              label={item.dependency_type}
              size="small"
              variant="outlined"
              sx={{
                height: 18,
                fontSize: '0.65rem',
                color: TYPE_COLORS[item.dependency_type] ?? '#abb2bf',
                borderColor: TYPE_COLORS[item.dependency_type] ?? '#abb2bf',
              }}
            />

            {!item.is_direct && (
              <Chip
                label="transitive"
                size="small"
                variant="outlined"
                color="warning"
                sx={{ height: 18, fontSize: '0.65rem' }}
              />
            )}
          </Box>
        }
      />
    </ListItemButton>
  )
}
