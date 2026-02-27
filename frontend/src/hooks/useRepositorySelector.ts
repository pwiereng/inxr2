import { useState, useEffect } from 'react'
import {
  getRepositories,
  getRepositoryBranches,
  getCommits,
  type Repository,
  type BranchInfo,
  type CommitInfo,
} from '@/lib/api'
import { formatDateTimeUTC } from '@/lib/dateUtils'

interface UseRepositorySelectorParams {
  repoName: string | null
  branch: string | null
  commit: string | null
}

interface UseRepositorySelectorResult {
  repositories: Repository[]
  branches: BranchInfo[]
  commits: CommitInfo[]
  loadingRepos: boolean
  loadingBranches: boolean
  loadingCommits: boolean
  currentRepo: Repository | undefined
  defaultBranch: string
  commitDisplayValue: string
  currentCommitDate: string
  isIndexStale: boolean
}

export function useRepositorySelector({
  repoName,
  branch,
  commit,
}: UseRepositorySelectorParams): UseRepositorySelectorResult {
  // Data state
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [branches, setBranches] = useState<BranchInfo[]>([])
  const [commits, setCommits] = useState<CommitInfo[]>([])
  const [isIndexStale, setIsIndexStale] = useState(false)

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
        // Only show indexed branches (those with a last_indexed_commit)
        const indexedBranches = response.branches.filter((b) => b.last_indexed_commit)
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
      setIsIndexStale(false)
      return
    }

    const loadCommits = async () => {
      setLoadingCommits(true)
      try {
        const response = await getCommits(repoName, branch || undefined, 500)
        // Check if latest git commit is unindexed (stale index)
        const firstCommit = response.commits[0]
        setIsIndexStale(
          firstCommit !== undefined && !firstCommit.is_indexed
        )
        // Only show indexed commits in the version dropdown (browsable)
        setCommits(response.commits.filter((c) => c.is_indexed))
      } catch (error) {
        console.error('Failed to load commits:', error)
        setCommits([])
      } finally {
        setLoadingCommits(false)
      }
    }

    loadCommits()
  }, [repoName, branch])

  // Computed values
  const currentRepo = repositories.find((r) => r.name === repoName)
  const defaultBranch = currentRepo?.default_branch || 'main'
  const commitDisplayValue = commit || (commits[0]?.hash ?? '')
  const currentCommitObj = commit ? commits.find((c) => c.hash === commit) : commits[0]
  const currentCommitDate = currentCommitObj?.commit_date
    ? formatDateTimeUTC(currentCommitObj.commit_date)
    : ''

  return {
    repositories,
    branches,
    commits,
    loadingRepos,
    loadingBranches,
    loadingCommits,
    currentRepo,
    defaultBranch,
    commitDisplayValue,
    currentCommitDate,
    isIndexStale,
  }
}
