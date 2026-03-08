import { useState, useEffect, useRef } from 'react'
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
  commitDateMap: Map<string, string>
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

  // Latest commit hash for the current branch (HEAD fallback for changedOnly).
  // We track which repository the resolved commit belongs to and pair this with
  // a per-request ID so that stale results from previous repos/requests are
  // never exposed to consumers.
  const [rawLatestBranchCommit, setRawLatestBranchCommit] = useState<string | null | undefined>(
    undefined
  )
  const commitRepoRef = useRef<string | undefined>(undefined)
  const commitRequestIdRef = useRef(0)
  // Safe value: undefined if the resolved commit doesn't belong to current repo
  const latestBranchCommit =
    commitRepoRef.current === urlState.repoName ? rawLatestBranchCommit : undefined
  // Map of commit hash → commit date for temporal comparison (populated from getCommits)
  const [commitDateMap, setCommitDateMap] = useState<Map<string, string>>(new Map())

  // ========== UI state (loading/error only) ==========
  const [loading, setLoading] = useState(true)
  const [fileLoading, setFileLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Track previous selectedCommit to detect commit-sync transitions (null → hash)
  // that should NOT trigger a re-fetch.
  const prevCommitRef = useRef<string | null | undefined>(undefined)
  // Track which file the current content belongs to, so we only skip re-fetch
  // when the file hasn't changed.
  const loadedFileKeyRef = useRef<string | null>(null)
  // Whether we have file content loaded (ref to avoid circular effect dep)
  const hasContentRef = useRef(false)

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

    // Only use repository.default_branch if it belongs to the current repo
    const repoDefaultBranch =
      repository?.name === urlState.repoName ? repository.default_branch : undefined
    const branch = urlState.selectedBranch || repoDefaultBranch
    if (!branch) {
      // Invalidate any in-flight commit requests and clear stale commit data
      commitRequestIdRef.current++
      setRawLatestBranchCommit(undefined)
      setCommitDateMap(new Map())
      return // Wait for repository to load so we know the default branch
    }

    const requestId = ++commitRequestIdRef.current
    const effectRepoName = urlState.repoName

    // Reset to pending so the tree-loading guard knows we're fetching
    commitRepoRef.current = effectRepoName
    setRawLatestBranchCommit(undefined)

    getCommits(effectRepoName, branch || undefined, 500)
      .then((res) => {
        if (requestId !== commitRequestIdRef.current) return // stale response
        // Find the newest indexed commit (commits are newest-first)
        const latest = res.commits.find((c) => c.is_indexed)
        setRawLatestBranchCommit(latest?.hash ?? null)
        // Build hash→date map for temporal comparison
        const dateMap = new Map<string, string>()
        for (const c of res.commits) {
          dateMap.set(c.hash, c.commit_date)
        }
        setCommitDateMap(dateMap)
      })
      .catch(() => {
        if (requestId !== commitRequestIdRef.current) return // stale response
        setRawLatestBranchCommit(null)
        setCommitDateMap(new Map())
      })
  }, [urlState.repoName, urlState.selectedBranch, repository?.default_branch, repository?.name])

  // Load tree
  useEffect(() => {
    if (!urlState.repoName) return

    // Determine which branch to use for tree (left or right panel in diff mode)
    // Layout: left=comparison (diffBranch), right=current (selectedBranch)
    const treeBranch = urlState.diffMode
      ? urlState.treePanel === 'left'
        ? urlState.diffBranch || urlState.selectedBranch
        : urlState.selectedBranch
      : urlState.selectedBranch

    const loadTree = async () => {
      try {
        // Guard 1: When changedOnly is requested but latestBranchCommit is still
        // pending (undefined = not yet resolved), skip loading to avoid showing
        // the full unfiltered tree. Once it resolves (to a string or null), the
        // effect re-fires.
        if (urlState.changedOnly && !treeCommit && latestBranchCommit === undefined) return

        // Guard 2: When neither an explicit commit nor branch is available, wait
        // for latestBranchCommit to resolve. Without this, the tree API is called
        // without filtering params, which returns ghost files (stale paths from
        // renamed/deleted files). Once latestBranchCommit resolves, the effect
        // re-fires with a proper commit.
        if (!treeCommit && !treeBranch && latestBranchCommit === undefined) {
          setTreeNodes([])
          return
        }

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
      prevCommitRef.current = urlState.selectedCommit
      loadedFileKeyRef.current = null
      hasContentRef.current = false
      return
    }

    const fileKey = `${urlState.repoName}:${urlState.filePath}:${urlState.selectedBranch}`

    // Skip redundant re-fetch when commit-sync resolves HEAD hash.
    // The commit-sync effect writes the resolved HEAD hash to the URL, changing
    // selectedCommit from null → hash.  Since null already meant "branch HEAD",
    // the API would return the same file.  Skip the re-fetch to prevent a
    // second load+scroll cycle.
    const prevCommit = prevCommitRef.current
    prevCommitRef.current = urlState.selectedCommit
    if (
      prevCommit === null &&
      typeof urlState.selectedCommit === 'string' &&
      hasContentRef.current &&
      loadedFileKeyRef.current === fileKey
    ) {
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
        loadedFileKeyRef.current = fileKey
        hasContentRef.current = true
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
    commitDateMap,
    loading,
    fileLoading,
    error,
    setError,
  }
}
