import { useEffect, useState } from 'react'
import { Box, CircularProgress } from '@mui/material'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CodeHeader } from '@/components/CodeHeader/CodeHeader'
import type { TabValue } from '@/components/CodeHeader/CodeHeader'
import { MarkdownViewer } from '@/components/MarkdownViewer'

export default function Help(): React.ReactElement {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [content, setContent] = useState<string | null>(null)

  const repoName = searchParams.get('repo')
  const branch = searchParams.get('branch')
  const commit = searchParams.get('commit')

  useEffect(() => {
    fetch('/HELP.md')
      .then((res) => res.text())
      .then(setContent)
  }, [])

  const handleRepoChange = (newRepo: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('repo', newRepo)
    params.delete('branch')
    params.delete('commit')
    navigate(`/help?${params.toString()}`)
  }

  const handleBranchChange = (newBranch: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('branch', newBranch)
    params.delete('commit')
    navigate(`/help?${params.toString()}`)
  }

  const handleCommitChange = (newCommit: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('commit', newCommit)
    navigate(`/help?${params.toString()}`)
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
      case 'mcp-help':
        // Already on help
        break
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <CodeHeader
        currentTab="mcp-help"
        repoName={repoName}
        branch={branch}
        commit={commit}
        onRepoChange={handleRepoChange}
        onBranchChange={handleBranchChange}
        onCommitChange={handleCommitChange}
        onTabChange={handleTabChange}
      />

      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {content === null ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 6 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box sx={{ maxWidth: 900, mx: 'auto', py: 2 }}>
            <MarkdownViewer content={content} />
          </Box>
        )}
      </Box>
    </Box>
  )
}
