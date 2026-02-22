import { Toolbar, Tabs, Tab } from '@mui/material'
import CodeIcon from '@mui/icons-material/Code'
import SearchIcon from '@mui/icons-material/Search'
import HistoryIcon from '@mui/icons-material/History'
import type { TabValue } from './CodeHeader'

interface NavigationTabsProps {
  currentTab: TabValue
  onTabChange: (tab: TabValue) => void
}

export function NavigationTabs({ currentTab, onTabChange }: NavigationTabsProps) {
  const handleTabChange = (_event: React.SyntheticEvent, newValue: TabValue) => {
    onTabChange(newValue)
  }

  return (
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
  )
}
