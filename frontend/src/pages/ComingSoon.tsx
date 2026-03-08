import { Box, Typography } from '@mui/material'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CodeHeader } from '@/components/CodeHeader'
import type { TabValue } from '@/components/CodeHeader'

interface ComingSoonProps {
  title: string
  tab: TabValue
}

export default function ComingSoon({ title, tab }: ComingSoonProps): React.ReactElement {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const repoName = searchParams.get('repo')
  const branch = searchParams.get('branch')
  const commit = searchParams.get('commit')

  const handleRepoChange = (newRepo: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('repo', newRepo)
    params.delete('branch')
    params.delete('commit')
    navigate(`/${tab}?${params.toString()}`)
  }

  const handleBranchChange = (newBranch: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('branch', newBranch)
    params.delete('commit')
    navigate(`/${tab}?${params.toString()}`)
  }

  const handleCommitChange = (newCommit: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('commit', newCommit)
    navigate(`/${tab}?${params.toString()}`)
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

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <CodeHeader
        currentTab={tab}
        repoName={repoName}
        branch={branch}
        commit={commit}
        onRepoChange={handleRepoChange}
        onBranchChange={handleBranchChange}
        onCommitChange={handleCommitChange}
        onTabChange={handleTabChange}
      />

      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography variant="h4" color="text.secondary" gutterBottom>
          {title}
        </Typography>
        <Typography variant="h6" color="text.disabled">
          Coming Soon
        </Typography>
      </Box>
    </Box>
  )
}
