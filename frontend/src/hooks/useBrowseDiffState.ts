import { useState, useEffect, useCallback } from 'react'
import type { MutableRefObject } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import {
  getFileContentByPathAtCommit,
  getFileSymbolsByPath,
  getFileReferencesByPath,
  getFileHistory,
  type FileContent,
  type FileSymbol,
  type FileReference,
  type FileVersion,
  type Repository,
} from '@/lib/api'
import type { BrowseUrlState } from './useBrowseTypes'
import { encodeFilePath } from './useBrowseUrlState'

export interface UseBrowseDiffStateRefs {
  fileVersionsRef: MutableRefObject<FileVersion[]>
  repositoryRef: MutableRefObject<Repository | null>
  comparisonCommitRef: MutableRefObject<string | null>
}

export interface UseBrowseDiffStateParams {
  urlState: BrowseUrlState
  navigate: NavigateFunction
  refs: UseBrowseDiffStateRefs
}

export interface UseBrowseDiffStateResult {
  diffContent: FileContent | null
  diffSymbols: FileSymbol[]
  diffReferences: FileReference[]
  diffFileVersions: FileVersion[]
  diffLoading: boolean
  enterDiffMode: () => void
  exitDiffMode: () => void
  closePanel: (panel: 'left' | 'right') => void
  swapDiffPanels: () => void
}

export function useBrowseDiffState({
  urlState,
  navigate,
  refs,
}: UseBrowseDiffStateParams): UseBrowseDiffStateResult {
  const [diffContent, setDiffContent] = useState<FileContent | null>(null)
  const [diffSymbols, setDiffSymbols] = useState<FileSymbol[]>([])
  const [diffReferences, setDiffReferences] = useState<FileReference[]>([])
  const [diffFileVersions, setDiffFileVersions] = useState<FileVersion[]>([])
  const [diffLoading, setDiffLoading] = useState(false)

  // Load diff file versions (for diff mode - either cross-branch or same-branch version comparison)
  useEffect(() => {
    if (!urlState.filePath || !urlState.repoName || !urlState.diffMode) {
      setDiffFileVersions([])
      return
    }

    // Use the same branch logic as the right panel's VersionSelector
    const diffBranchToUse = urlState.diffBranch || urlState.selectedBranch
    getFileHistory(urlState.repoName, urlState.filePath, diffBranchToUse || undefined)
      .then((response) => setDiffFileVersions(response.versions))
      .catch(() => setDiffFileVersions([]))
  }, [
    urlState.repoName,
    urlState.filePath,
    urlState.diffMode,
    urlState.diffBranch,
    urlState.selectedBranch,
  ])

  // Load diff content
  useEffect(() => {
    // Diff mode can work with either diffCommit or diffBranch
    const hasDiffTarget = urlState.diffCommit || urlState.diffBranch
    if (!urlState.diffMode || !hasDiffTarget || !urlState.filePath || !urlState.repoName) {
      setDiffContent(null)
      setDiffSymbols([])
      setDiffReferences([])
      return
    }

    const loadDiffFile = async () => {
      setDiffLoading(true)
      try {
        const [content, symbols, references] = await Promise.all([
          getFileContentByPathAtCommit(
            urlState.repoName!,
            urlState.filePath!,
            urlState.diffCommit || undefined,
            urlState.diffBranch || undefined
          ),
          getFileSymbolsByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.diffCommit || undefined,
            urlState.diffBranch || undefined
          ),
          getFileReferencesByPath(
            urlState.repoName!,
            urlState.filePath!,
            urlState.diffCommit || undefined,
            urlState.diffBranch || undefined
          ),
        ])
        setDiffContent(content)
        setDiffSymbols(symbols.symbols)
        setDiffReferences(references.references)
      } catch (err) {
        // 404 errors are expected when file doesn't exist on the target branch/commit
        // Only log unexpected errors
        const isNotFoundError =
          err instanceof Error && (err.message.includes('not found') || err.message.includes('404'))
        if (!isNotFoundError) {
          console.error('Failed to load diff file:', err)
        }
        setDiffContent(null)
        setDiffSymbols([])
        setDiffReferences([])
      } finally {
        setDiffLoading(false)
      }
    }

    loadDiffFile()
  }, [
    urlState.repoName,
    urlState.filePath,
    urlState.diffMode,
    urlState.diffCommit,
    urlState.diffBranch,
  ])

  // ========== Diff Mode Actions ==========

  const enterDiffMode = useCallback(() => {
    if (!urlState.filePath) return

    const fileVersions = refs.fileVersionsRef.current

    // Set diff to current commit — both panels show same version initially.
    // User picks a different version on the left panel to start comparing.
    const currentCommit = urlState.selectedCommit || fileVersions[0]?.commit_hash

    const params = new URLSearchParams()
    if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
    if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
    // Preserve drawer state only - entering diff mode clears search context
    if (!urlState.drawerOpen) params.set('drawer', '0')
    // Don't preserve refs, searchQuery - diff mode is a new context
    // Preserve branch state
    if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
    // Preserve changedOnly state
    if (urlState.changedOnly) params.set('co', '1')

    if (currentCommit) {
      params.set('diff', currentCommit)
    }

    navigate(
      `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
    )
  }, [navigate, urlState, refs.fileVersionsRef])

  const exitDiffMode = useCallback(() => {
    if (!urlState.filePath) return

    setDiffContent(null)
    setDiffSymbols([])
    setDiffReferences([])
    // Note: tp/rp/ap params are not set, so they default to 'left' when URL is parsed

    const params = new URLSearchParams()
    if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
    if (urlState.selectedCommit) params.set('commit', urlState.selectedCommit)
    // Preserve drawer state only - exiting diff mode clears search context
    if (!urlState.drawerOpen) params.set('drawer', '0')
    // Don't preserve refs, searchQuery - exiting diff mode is a context change
    // Preserve branch state (but not diffBranch since we're exiting diff mode)
    if (urlState.selectedBranch) params.set('branch', urlState.selectedBranch)
    // Preserve changedOnly state
    if (urlState.changedOnly) params.set('co', '1')
    navigate(
      `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
    )
  }, [navigate, urlState])

  const closePanel = useCallback(
    (panel: 'left' | 'right') => {
      if (!urlState.filePath) return

      // Layout: left=comparison (diff param), right=current (commit param synced with top picker)

      if (panel === 'left') {
        // Closing comparison (left) panel — just exit diff mode, keep current version
        exitDiffMode()
        return
      }

      // Closing current (right) panel — switch to comparison's version/branch
      const params = new URLSearchParams()
      if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
      // The comparison commit (currently on left) becomes the new current version
      if (urlState.diffCommit) params.set('commit', urlState.diffCommit)
      // Preserve drawer state only - closing panel clears search context
      if (!urlState.drawerOpen) params.set('drawer', '0')
      // Use the comparison's branch (diffBranch, or fall back to selectedBranch)
      const newBranch = urlState.diffBranch ?? urlState.selectedBranch
      if (newBranch) params.set('branch', newBranch)
      // Preserve changedOnly state
      if (urlState.changedOnly) params.set('co', '1')
      navigate(
        `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
      )
    },
    [navigate, urlState, exitDiffMode]
  )

  const swapDiffPanels = useCallback(() => {
    if (!urlState.filePath) return
    const fileVersions = refs.fileVersionsRef.current

    const currentCommit = urlState.selectedCommit || fileVersions[0]?.commit_hash
    const currentDiff = urlState.diffCommit

    const params = new URLSearchParams()
    if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
    // Old diff → new commit (right panel)
    if (currentDiff) params.set('commit', currentDiff)
    // Old commit → new diff (left panel)
    if (currentCommit) params.set('diff', currentCommit)
    // Swap branches too if cross-branch
    if (urlState.diffBranch) params.set('branch', urlState.diffBranch)
    if (urlState.selectedBranch) params.set('diffBranch', urlState.selectedBranch)
    // Preserve other state
    if (!urlState.drawerOpen) params.set('drawer', '0')
    if (urlState.changedOnly) params.set('co', '1')

    navigate(
      `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
    )
  }, [navigate, urlState, refs.fileVersionsRef])

  return {
    diffContent,
    diffSymbols,
    diffReferences,
    diffFileVersions,
    diffLoading,
    enterDiffMode,
    exitDiffMode,
    closePanel,
    swapDiffPanels,
  }
}
