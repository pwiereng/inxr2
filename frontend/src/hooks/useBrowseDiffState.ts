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
  rightCommitRef: MutableRefObject<string | null>
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
    const repository = refs.repositoryRef.current

    const currentIndex = fileVersions.findIndex(
      (v) => v.commit_hash === (urlState.selectedCommit || fileVersions[0]?.commit_hash)
    )
    let diffTarget: string | null = null
    if (currentIndex >= 0 && currentIndex < fileVersions.length - 1) {
      diffTarget = fileVersions[currentIndex + 1]?.commit_hash || null
    } else if (fileVersions.length > 1) {
      diffTarget = fileVersions[1]?.commit_hash || null
    }

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

    if (diffTarget) {
      // Compare against a different version on the same branch
      params.set('diff', diffTarget)
    } else {
      // No other versions available - enter cross-branch comparison mode
      // Set diffBranch to current branch so user can change it
      params.set('diffBranch', urlState.selectedBranch || repository?.default_branch || 'main')
    }

    navigate(
      `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
    )
  }, [navigate, urlState])

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

      // When closing left panel, switch to the right panel's version/branch
      if (panel === 'left') {
        const params = new URLSearchParams()
        if (urlState.highlightLine) params.set('line', urlState.highlightLine.toString())
        // Use the effective right commit (could be from diffCommit or diffFileVersions)
        const rightCommit = refs.rightCommitRef.current
        if (rightCommit) params.set('commit', rightCommit)
        // Preserve drawer state only - closing panel clears search context
        if (!urlState.drawerOpen) params.set('drawer', '0')
        // Don't preserve refs, searchQuery - closing panel is a context change
        // When closing left panel, the diff side becomes the main view - prefer diffBranch,
        // but fall back to selectedBranch for same-branch diff mode
        const rightBranch = urlState.diffBranch ?? urlState.selectedBranch
        if (rightBranch) params.set('branch', rightBranch)
        // Preserve changedOnly state
        if (urlState.changedOnly) params.set('co', '1')
        navigate(
          `/browse/${encodeURIComponent(urlState.repoName!)}/${encodeFilePath(urlState.filePath)}?${params}`
        )
        return
      }
      // Closing right panel - keep the left panel's version/branch
      exitDiffMode()
    },
    [navigate, urlState, exitDiffMode]
  )

  return {
    diffContent,
    diffSymbols,
    diffReferences,
    diffFileVersions,
    diffLoading,
    enterDiffMode,
    exitDiffMode,
    closePanel,
  }
}
