import { useState, useEffect } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import {
  getRepositories,
  getRepositoryByName,
  getRepositoryTreeByName,
  getCommits,
  getFileContentByPathAtCommit,
  getFileSymbolsByPath,
  getFileReferencesByPath,
  getFileRawContent,
  getFileHistory,
  type Repository,
  type TreeNode,
  type FileContent,
  type FileSymbol,
  type FileReference,
  type FileVersion,
  type RawFileContent,
} from '@/lib/api'
import { isImageFile } from '@/lib/fileUtils'
import type { BrowseUrlState } from './useBrowseTypes'
import { computeTreeCommit } from './useBrowseTypes'

export interface UseBrowseDataParams {
  urlState: BrowseUrlState
  diffFileVersions: FileVersion[]
  navigate: NavigateFunction
  searchParams: URLSearchParams
}

export interface UseBrowseDataResult {
  allRepositories: Repository[]
  repository: Repository | null
  treeNodes: TreeNode[]
  fileContent: FileContent | null
  fileSymbols: FileSymbol[]
  fileReferences: FileReference[]
  fileVersions: FileVersion[]
  rawContent: RawFileContent | null
  latestBranchCommit: string | null | undefined
  loading: boolean
  fileLoading: boolean
  error: string | null
  setError: (error: string | null) => void
}

export function useBrowseData({
  urlState,
  diffFileVersions,
  navigate,
  searchParams,
}: UseBrowseDataParams): UseBrowseDataResult {
  // ========== Data state ==========
  const [allRepositories, setAllRepositories] = useState<Repository[]>([])
  const [repository, setRepository] = useState<Repository | null>(null)
  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([])
  const [fileContent, setFileContent] = useState<FileContent | null>(null)
  const [fileSymbols, setFileSymbols] = useState<FileSymbol[]>([])
  const [fileReferences, setFileReferences] = useState<FileReference[]>([])
  const [fileVersions, setFileVersions] = useState<FileVersion[]>([])
  const [rawContent, setRawContent] = useState<RawFileContent | null>(null)

  // Latest commit hash for the current branch (HEAD fallback for changedOnly)
  const [latestBranchCommit, setLatestBranchCommit] = useState<string | null | undefined>(undefined)

  // ========== UI state (loading/error only) ==========
  const [loading, setLoading] = useState(true)
  const [fileLoading, setFileLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Compute treeCommit using shared helper (same logic as orchestrator's computedState)
  const treeCommit = computeTreeCommit(urlState, fileVersions, diffFileVersions, latestBranchCommit)

  // ========== Data Loading Effects ==========

  // Load all repositories
  useEffect(() => {
    getRepositories().then(setAllRepositories).catch(console.error)
  }, [])

  // Load repository by name
  useEffect(() => {
    if (!urlState.repoName) return

    const loadRepository = async () => {
      setLoading(true)
      setError(null)
      try {
        const repo = await getRepositoryByName(urlState.repoName!)
        setRepository(repo)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load repository')
      } finally {
        setLoading(false)
      }
    }

    loadRepository()
  }, [urlState.repoName])

  // Fetch latest commit for the current branch (used as HEAD fallback)
  useEffect(() => {
    if (!urlState.repoName) return

    // Reset to pending so the tree-loading guard knows we're fetching
    setLatestBranchCommit(undefined)

    const branch = urlState.selectedBranch || repository?.default_branch
    getCommits(urlState.repoName, branch || undefined, 500)
      .then((res) => {
        // Find the newest indexed commit (commits are newest-first)
        const latest = res.commits.find((c) => c.is_indexed)
        setLatestBranchCommit(latest?.hash ?? null)
      })
      .catch(() => setLatestBranchCommit(null))
  }, [urlState.repoName, urlState.selectedBranch, repository?.default_branch])

  // Load tree
  useEffect(() => {
    if (!urlState.repoName) return

    // Determine which branch to use for tree (left or right panel in diff mode)
    const treeBranch = urlState.diffMode
      ? urlState.treePanel === 'left'
        ? urlState.selectedBranch
        : urlState.diffBranch
      : urlState.selectedBranch

    const loadTree = async () => {
      try {
        // When changedOnly is requested but latestBranchCommit is still pending
        // (undefined = not yet resolved), skip loading to avoid showing the full
        // unfiltered tree. Once it resolves (to a string or null), the effect
        // re-fires. If it resolved to null (no indexed commits), we fall through
        // and load the unfiltered tree rather than staying empty forever.
        if (urlState.changedOnly && !treeCommit && latestBranchCommit === undefined) return

        // changedOnly only applies when viewing a specific commit
        const shouldUseChangedOnly = urlState.changedOnly && !!treeCommit
        const tree = await getRepositoryTreeByName(
          urlState.repoName!,
          treeCommit || undefined,
          treeBranch || undefined,
          shouldUseChangedOnly
        )
        setTreeNodes(tree.root)
      } catch (err) {
        console.error('Failed to load tree:', err)
      }
    }

    loadTree()
  }, [
    urlState.repoName,
    treeCommit,
    urlState.selectedBranch,
    urlState.diffBranch,
    urlState.diffMode,
    urlState.treePanel,
    urlState.changedOnly,
    latestBranchCommit,
  ])

  // Clear selected file if it's not in the changed-files tree
  useEffect(() => {
    if (!urlState.changedOnly || !urlState.filePath || !urlState.repoName) return

    // Recursively check if a file path exists in the tree
    const fileInTree = (nodes: TreeNode[], path: string): boolean =>
      nodes.some(
        (n) =>
          (n.type === 'file' && n.path === path) ||
          (n.children != null && fileInTree(n.children, path))
      )

    if (treeNodes.length > 0 && !fileInTree(treeNodes, urlState.filePath)) {
      // File not in the changed-files tree — clear selection
      const params = new URLSearchParams(searchParams)
      // Remove file-scoped params so the selection actually clears
      // (prevents loop if file was set via legacy ?file= param)
      params.delete('file')
      params.delete('line')
      navigate(`/browse/${encodeURIComponent(urlState.repoName)}?${params}`, { replace: true })
    }
  }, [
    urlState.changedOnly,
    urlState.filePath,
    urlState.repoName,
    treeNodes,
    navigate,
    searchParams,
  ])

  // Load file versions
  useEffect(() => {
    if (!urlState.filePath || !urlState.repoName) {
      setFileVersions([])
      return
    }

    getFileHistory(urlState.repoName, urlState.filePath, urlState.selectedBranch || undefined)
      .then((response) => setFileVersions(response.versions))
      .catch(() => setFileVersions([]))
  }, [urlState.repoName, urlState.filePath, urlState.selectedBranch])

  // Load file content (skip for image files — they use raw content)
  useEffect(() => {
    if (!urlState.filePath || !urlState.repoName || isImageFile(urlState.filePath)) {
      setFileContent(null)
      setFileSymbols([])
      setFileReferences([])
      return
    }

    const loadFile = async () => {
      setFileLoading(true)
      try {
        const [content, symbols, references] = await Promise.all([
          getFileContentByPathAtCommit(
            urlState.repoName!,
            urlState.filePath!,
            urlState.selectedCommit || undefined,
            urlState.selectedBranch || undefined
          ),
          getFileSymbolsByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.selectedCommit || undefined,
            urlState.selectedBranch || undefined
          ),
          getFileReferencesByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.selectedCommit || undefined,
            urlState.selectedBranch || undefined
          ),
        ])
        setError(null) // Clear any previous error on successful load
        setFileContent(content)
        setFileSymbols(symbols.symbols)
        setFileReferences(references.references)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load file')
      } finally {
        setFileLoading(false)
      }
    }

    loadFile()
  }, [urlState.repoName, urlState.filePath, urlState.selectedCommit, urlState.selectedBranch])

  // Load raw content for image files
  useEffect(() => {
    if (!urlState.filePath || !urlState.repoName || !isImageFile(urlState.filePath)) {
      setRawContent(null)
      return
    }

    const loadRawContent = async () => {
      setFileLoading(true)
      try {
        const content = await getFileRawContent(
          urlState.repoName!,
          urlState.filePath!,
          urlState.selectedCommit || undefined,
          urlState.selectedBranch || undefined
        )
        setRawContent(content)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load file')
        setRawContent(null)
      } finally {
        setFileLoading(false)
      }
    }

    loadRawContent()
  }, [urlState.repoName, urlState.filePath, urlState.selectedCommit, urlState.selectedBranch])

  return {
    allRepositories,
    repository,
    treeNodes,
    fileContent,
    fileSymbols,
    fileReferences,
    fileVersions,
    rawContent,
    latestBranchCommit,
    loading,
    fileLoading,
    error,
    setError,
  }
}
