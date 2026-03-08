import { Box, AppBar, Toolbar, IconButton, Tooltip, Alert } from '@mui/material'
import HomeIcon from '@mui/icons-material/Home'
import LightModeIcon from '@mui/icons-material/LightMode'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import { useNavigate } from 'react-router-dom'
import { useApp } from '@/contexts/AppContext'
import { useRepositorySelector } from '@/hooks/useRepositorySelector'
import { RepositorySelect } from './RepositorySelect'
import { BranchSelect } from './BranchSelect'
import { CommitSelect } from './CommitSelect'
import { CommitDateIndicator } from './CommitDateIndicator'
import { NavigationTabs } from './NavigationTabs'

export type TabValue = 'browse' | 'search' | 'history' | 'logical-view' | 'dependencies' | 'help'

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
}: CodeHeaderProps): React.ReactElement {
  const navigate = useNavigate()
  const { themeMode, toggleThemeMode } = useApp()

  const {
    repositories,
    branches,
    commits,
    loadingRepos,
    loadingBranches,
    loadingCommits,
    defaultBranch,
    commitDisplayValue,
    currentCommitDate,
    isIndexStale,
  } = useRepositorySelector({ repoName, branch, commit })

  const handleHomeClick = () => {
    navigate('/')
  }

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

        <RepositorySelect
          repositories={repositories}
          loading={loadingRepos}
          repoName={repoName}
          currentTab={currentTab}
          onRepoChange={onRepoChange}
        />

        {repoName && (
          <>
            <BranchSelect
              branches={branches}
              loading={loadingBranches}
              branch={branch}
              defaultBranch={defaultBranch}
              onBranchChange={onBranchChange}
            />

            <CommitSelect
              commits={commits}
              loading={loadingCommits}
              commitDisplayValue={commitDisplayValue}
              onCommitChange={onCommitChange}
            />
          </>
        )}

        {repoName && !loadingCommits && currentCommitDate && (
          <CommitDateIndicator currentCommitDate={currentCommitDate} />
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

      {/* Stale index warning */}
      {isIndexStale && (
        <Alert severity="warning" sx={{ py: 0 }}>
          Index is outdated — some recent commits may not be browsable
        </Alert>
      )}

      {/* Row 2: Tabs */}
      <NavigationTabs currentTab={currentTab} onTabChange={onTabChange} />
    </AppBar>
  )
}
