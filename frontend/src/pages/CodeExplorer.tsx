import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
  AppBar,
  Toolbar,
  Tabs,
  Tab,
  Select,
  MenuItem,
  FormControl,
  CircularProgress,
} from '@mui/material'
import CodeIcon from '@mui/icons-material/Code'
import SearchIcon from '@mui/icons-material/Search'
import HistoryIcon from '@mui/icons-material/History'
import FolderIcon from '@mui/icons-material/Folder'

import Browse from './Browse'
import Search from './Search'
import { getRepositories, type Repository } from '@/lib/api'

type TabValue = 'browse' | 'search' | 'history'

/**
 * CodeExplorer - Unified view with tabs for Browse, Search, and History
 * Maintains shared state (repository, branch) across tabs
 */
export default function CodeExplorer() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Get tab from URL, default to browse
  const urlTab = searchParams.get('tab') as TabValue | null
  const [activeTab, setActiveTab] = useState<TabValue>(urlTab || 'browse')

  // Get repo from URL
  const urlRepo = searchParams.get('repo')

  // Repository state
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<string | null>(urlRepo)
  const [loading, setLoading] = useState(true)

  // Load repositories
  useEffect(() => {
    const loadRepos = async () => {
      try {
        const repos = await getRepositories()
        setRepositories(repos)

        // If no repo selected but we have repos, select the first one
        if (!selectedRepo && repos.length > 0 && repos[0]) {
          setSelectedRepo(repos[0].name)
        }
      } catch (error) {
        console.error('Failed to load repositories:', error)
      } finally {
        setLoading(false)
      }
    }
    loadRepos()
  }, [selectedRepo])

  // Sync tab state with URL
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab') as TabValue | null
    if (tabFromUrl && tabFromUrl !== activeTab) {
      setActiveTab(tabFromUrl)
    }
  }, [searchParams, activeTab])

  // Sync repo state with URL
  useEffect(() => {
    const repoFromUrl = searchParams.get('repo')
    if (repoFromUrl && repoFromUrl !== selectedRepo) {
      setSelectedRepo(repoFromUrl)
    }
  }, [searchParams, selectedRepo])

  const handleTabChange = (_event: React.SyntheticEvent, newValue: TabValue) => {
    setActiveTab(newValue)

    // Update URL with tab parameter, preserving only repo and branch
    const newParams = new URLSearchParams()
    newParams.set('tab', newValue)
    if (selectedRepo) {
      newParams.set('repo', selectedRepo)
    }
    const branch = searchParams.get('branch')
    if (branch) {
      newParams.set('branch', branch)
    }

    // Navigate to new URL (clears search/browse-specific params for fresh start)
    navigate(`?${newParams.toString()}`, { replace: true })
  }

  const handleRepoChange = (repoName: string) => {
    setSelectedRepo(repoName)

    // When switching repos, set branch to new repo's default branch
    // and clear other tab-specific params for a clean start
    const newRepo = repositories.find((r) => r.name === repoName)
    const newParams = new URLSearchParams()
    newParams.set('tab', activeTab)
    newParams.set('repo', repoName)
    if (newRepo?.default_branch) {
      newParams.set('branch', newRepo.default_branch)
    }

    // Navigate to new URL
    navigate(`?${newParams.toString()}`, { replace: true })
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

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* App Bar with Tabs */}
      <AppBar
        position="static"
        sx={{
          bgcolor: 'background.paper',
          borderBottom: 1,
          borderColor: 'divider',
        }}
        elevation={0}
      >
        <Toolbar sx={{ gap: 2, minHeight: '48px !important' }}>
          <CodeIcon color="primary" />

          {/* Repository Selector */}
          {repositories.length > 1 ? (
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <Select
                value={selectedRepo || ''}
                onChange={(e) => handleRepoChange(e.target.value as string)}
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
            repositories.length === 1 && repositories[0] && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 1 }}>
                <FolderIcon fontSize="small" />
                {repositories[0].name}
              </Box>
            )
          )}

          {/* Tabs */}
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            sx={{
              flex: 1,
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
              disabled
              sx={{ opacity: 0.5 }}
            />
          </Tabs>
        </Toolbar>
      </AppBar>

      {/* Tab Content */}
      <Box sx={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {activeTab === 'browse' && selectedRepo && <Browse noAppBar repoName={selectedRepo} />}
        {activeTab === 'search' && <Search noAppBar repoName={selectedRepo || undefined} />}
        {activeTab === 'history' && (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              color: 'text.secondary',
            }}
          >
            History view coming soon...
          </Box>
        )}
      </Box>
    </Box>
  )
}
