import { useState, useEffect } from 'react'
import {
  Box,
  AppBar,
  Toolbar,
  Tabs,
  Tab,
  Select,
  MenuItem,
  FormControl,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material'
import HomeIcon from '@mui/icons-material/Home'
import CodeIcon from '@mui/icons-material/Code'
import SearchIcon from '@mui/icons-material/Search'
import HistoryIcon from '@mui/icons-material/History'
import FolderIcon from '@mui/icons-material/Folder'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import LightModeIcon from '@mui/icons-material/LightMode'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import { useNavigate } from 'react-router-dom'
import { useApp } from '@/contexts/AppContext'
import {
  getRepositories,
  getRepositoryBranches,
  getCommits,
  type Repository,
  type BranchInfo,
  type CommitInfo,
} from '@/lib/api'

import { parseAsUTC } from '@/lib/dateUtils'

/**
 * Format a commit date string as yyyy-mm-dd for display.
 * Uses parseAsUTC to handle dates with or without timezone indicators.
 */
export function formatCommitDate(dateStr: string): string {
  if (!dateStr) return ''
  const date = parseAsUTC(dateStr)
  if (isNaN(date.getTime())) return ''
  const y = date.getUTCFullYear()
  const m = String(date.getUTCMonth() + 1).padStart(2, '0')
  const d = String(date.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export type TabValue = 'browse' | 'search' | 'history'

interface CodeHeaderProps {
  currentTab: TabValue
  repoName: string | null
  branch: string | null
  commit: string | null
  onRepoChange: (repoName: string) => void
  onBranchChange: (branch: string) => void
  onCommitChange: (commit: string) => void
  onTabChange: (tab: TabValue) => void
}

export function CodeHeader({
  currentTab,
  repoName,
  branch,
  commit,
  onRepoChange,
  onBranchChange,
  onCommitChange,
  onTabChange,
}: CodeHeaderProps) {
  const navigate = useNavigate()
  const { themeMode, toggleThemeMode } = useApp()

  // Data state
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [branches, setBranches] = useState<BranchInfo[]>([])
  const [commits, setCommits] = useState<CommitInfo[]>([])

  // Loading state
  const [loadingRepos, setLoadingRepos] = useState(true)
  const [loadingBranches, setLoadingBranches] = useState(false)
  const [loadingCommits, setLoadingCommits] = useState(false)

  // Load repositories on mount
  useEffect(() => {
    const loadRepos = async () => {
      setLoadingRepos(true)
      try {
        const repos = await getRepositories()
        setRepositories(repos)
      } catch (error) {
        console.error('Failed to load repositories:', error)
      } finally {
        setLoadingRepos(false)
      }
    }
    loadRepos()
  }, [])

  // Load branches when repository changes
  useEffect(() => {
    if (!repoName) {
      setBranches([])
      return
    }

    const loadBranches = async () => {
      setLoadingBranches(true)
      try {
        const repo = repositories.find((r) => r.name === repoName)
        if (!repo) return

        const response = await getRepositoryBranches(repo.id)
        // Only show indexed branches
        const indexedBranches = response.branches.filter(
          (b) => b.commit_count && b.commit_count > 0
        )
        setBranches(indexedBranches)
      } catch (error) {
        console.error('Failed to load branches:', error)
        setBranches([])
      } finally {
        setLoadingBranches(false)
      }
    }

    loadBranches()
  }, [repoName, repositories])

  // Load commits when repository or branch changes
  useEffect(() => {
    if (!repoName) {
      setCommits([])
      return
    }

    const loadCommits = async () => {
      setLoadingCommits(true)
      try {
        const response = await getCommits(repoName, branch || undefined, 50)
        setCommits(response.commits)
      } catch (error) {
        console.error('Failed to load commits:', error)
        setCommits([])
      } finally {
        setLoadingCommits(false)
      }
    }

    loadCommits()
  }, [repoName, branch])

  const handleHomeClick = () => {
    navigate('/')
  }

  const handleTabChange = (_event: React.SyntheticEvent, newValue: TabValue) => {
    onTabChange(newValue)
  }

  const currentRepo = repositories.find((r) => r.name === repoName)
  const defaultBranch = currentRepo?.default_branch || 'main'

  // Get short hash for commit display
  const getShortHash = (hash: string) => hash.substring(0, 7)

  // Find commit display value
  const commitDisplayValue = commit || (commits[0]?.hash ?? '')

  return (
    <AppBar
      position="static"
      sx={{
        bgcolor: 'background.paper',
        borderBottom: 1,
        borderColor: 'divider',
      }}
      elevation={0}
    >
      {/* Row 1: Home icon, Repository dropdown, Branch dropdown, Commit dropdown */}
      <Toolbar
        sx={{ gap: 2, minHeight: '48px !important', borderBottom: 1, borderColor: 'divider' }}
      >
        <Tooltip title="Home">
          <IconButton
            edge="start"
            onClick={handleHomeClick}
            size="small"
            sx={{
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              '&:hover': {
                bgcolor: 'primary.dark',
              },
              borderRadius: 1,
              p: 0.75,
            }}
          >
            <HomeIcon />
          </IconButton>
        </Tooltip>

        {/* Repository Selector */}
        {loadingRepos ? (
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <CircularProgress size={20} />
          </Box>
        ) : repositories.length > 1 ? (
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <Select
              value={repoName || ''}
              onChange={(e) => onRepoChange(e.target.value as string)}
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
              {repositories.map((repo) => (
                <MenuItem key={repo.id} value={repo.name}>
                  <FolderIcon fontSize="small" sx={{ mr: 1 }} />
                  {repo.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        ) : (
          repositories.length === 1 &&
          repositories[0] && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 1 }}>
              <FolderIcon fontSize="small" />
              {repositories[0].name}
            </Box>
          )
        )}

        {/* Branch Selector */}
        {repoName && (
          <>
            {loadingBranches ? (
              <CircularProgress size={20} />
            ) : branches.length > 0 ? (
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <Select
                  value={branch || defaultBranch}
                  onChange={(e) => onBranchChange(e.target.value as string)}
                  displayEmpty
                  sx={{
                    '& .MuiSelect-select': {
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      py: 0.5,
                      fontSize: '0.875rem',
                    },
                  }}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <AccountTreeIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                      {selected}
                    </Box>
                  )}
                >
                  {branches.map((branchInfo) => (
                    <MenuItem key={branchInfo.name} value={branchInfo.name}>
                      {branchInfo.name}
                      {branchInfo.name === defaultBranch && ' (default)'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            ) : null}

            {/* Commit Selector */}
            {loadingCommits ? (
              <CircularProgress size={20} />
            ) : commits.length > 0 ? (
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <Select
                  value={commitDisplayValue}
                  onChange={(e) => onCommitChange(e.target.value as string)}
                  displayEmpty
                  sx={{
                    '& .MuiSelect-select': {
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      py: 0.5,
                      fontSize: '0.875rem',
                      fontFamily: 'monospace',
                    },
                  }}
                  renderValue={(selected) => {
                    if (!selected) return 'latest'
                    const selectedCommitObj = commits.find((c) => c.hash === selected)
                    return selectedCommitObj ? getShortHash(selectedCommitObj.hash) : 'latest'
                  }}
                >
                  {commits.map((commitInfo) => {
                    const formattedDate = commitInfo.commit_date
                      ? formatCommitDate(commitInfo.commit_date)
                      : ''
                    return (
                    <MenuItem key={commitInfo.hash} value={commitInfo.hash}>
                      <Tooltip title={commitInfo.message} placement="left">
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Box
                            component="span"
                            sx={{
                              fontFamily: 'monospace',
                              fontSize: '0.8rem',
                            }}
                          >
                            {getShortHash(commitInfo.hash)}
                          </Box>
                          {formattedDate && (
                              <Box
                                component="span"
                                sx={{
                                  fontSize: '0.75rem',
                                  color: 'text.secondary',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                {formattedDate}
                              </Box>
                            )}
                          <Box
                            component="span"
                            sx={{
                              fontSize: '0.75rem',
                              color: 'text.secondary',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              maxWidth: 200,
                            }}
                          >
                            {commitInfo.message}
                          </Box>
                        </Box>
                      </Tooltip>
                    </MenuItem>
                    )
                  })}
                </Select>
              </FormControl>
            ) : null}
          </>
        )}

        <Box sx={{ flex: 1 }} />

        <Tooltip title={themeMode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
          <IconButton
            size="small"
            onClick={toggleThemeMode}
            sx={{ color: 'text.secondary' }}
            aria-label={themeMode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {themeMode === 'dark' ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
        </Tooltip>
      </Toolbar>

      {/* Row 2: Tabs */}
      <Toolbar sx={{ minHeight: '48px !important', px: 2 }}>
        <Tabs
          value={currentTab}
          onChange={handleTabChange}
          sx={{
            minHeight: 48,
            '& .MuiTab-root': {
              minHeight: 48,
              textTransform: 'none',
              fontWeight: 500,
            },
          }}
        >
          <Tab
            value="browse"
            label="Browse"
            icon={<CodeIcon fontSize="small" />}
            iconPosition="start"
          />
          <Tab
            value="search"
            label="Search"
            icon={<SearchIcon fontSize="small" />}
            iconPosition="start"
          />
          <Tab
            value="history"
            label="History"
            icon={<HistoryIcon fontSize="small" />}
            iconPosition="start"
          />
        </Tabs>
      </Toolbar>
    </AppBar>
  )
}
