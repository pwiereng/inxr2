/**
 * API client for INXR2 backend
 */

// Use relative URL so Vite proxy handles it (works in Docker and locally)
const API_BASE = '/api'

// Types
export interface Repository {
  id: number
  name: string
  url: string
  description: string | null
  default_branch: string
  created_at: string | null
  updated_at: string | null
}

export interface FileInfo {
  id: number
  repository_id: number
  commit_id: number
  path: string
  language: string | null
  size_bytes: number
  line_count: number | null
}

export interface Symbol {
  id: number
  name: string
  qualified_name: string | null
  kind: string
  file_id: number
  file_path: string | null
  repository_id: number
  commit_id: number
  start_line: number
  start_column: number
  end_line: number
  end_column: number
  signature: string | null
  docstring: string | null
}

export interface SymbolListResponse {
  items: Symbol[]
  total: number
  limit: number
  offset: number
}

export interface Reference {
  id: number
  source_file_id: number
  source_file_path: string | null
  source_line: number
  source_column: number
  target_symbol_id: number | null
  reference_text: string
  reference_type: string
}

export interface ReferencesListResponse {
  items: Reference[]
  total: number
  symbol_name: string
}

export interface FileContent {
  id: number
  path: string
  language: string | null
  content: string
  line_count: number
  size_bytes: number
}

export interface FileSymbol {
  id: number
  name: string
  qualified_name: string | null
  kind: string
  start_line: number
  start_column: number
  end_line: number
  end_column: number
  signature: string | null
}

export interface FileSymbolsResponse {
  file_id: number
  file_path: string
  symbols: FileSymbol[]
  total: number
}

export interface FileReference {
  id: number
  reference_text: string
  reference_type: string
  source_line: number
  source_column: number
  target_symbol_id: number | null
}

export interface FileReferencesResponse {
  file_id: number
  file_path: string
  references: FileReference[]
  total: number
}

export interface TreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  file_id: number | null
  language: string | null
  size_bytes: number | null
  line_count: number | null
  children: TreeNode[] | null
}

export interface TreeResponse {
  repository_id: number
  repository_name: string
  root: TreeNode[]
  total_files: number
  total_directories: number
}

export interface RepositoryStats {
  repository_id: number
  name: string
  total_files: number
  total_symbols: number
  total_references: number
  languages: Record<string, number>
  total_lines: number
  total_references_resolved: number
  total_references_unresolved: number
  commit_date_earliest: string | null
  commit_date_latest: string | null
  last_indexed_at: string | null
  last_indexed_commit: string | null
  last_indexing_duration_seconds: number | null
  last_resolving_duration_seconds: number | null
  git_head_commit: string | null
  is_stale: boolean
}

// Time Travel types
export interface CommitInfo {
  hash: string
  short_hash: string
  message: string
  author_name: string
  author_email: string
  commit_date: string
  is_indexed: boolean
  tags: string[]
  is_branch_specific: boolean
  is_merge_base: boolean
}

export interface CommitListResponse {
  commits: CommitInfo[]
  total: number
}

export interface BranchInfo {
  name: string
  last_indexed_commit: string | null
  oldest_indexed_commit: string | null
  commit_count: number
  last_indexed_at: string | null
}

export interface BranchListResponse {
  branches: BranchInfo[]
}

export interface FileVersion {
  commit_id: number
  commit_hash: string
  short_hash: string
  commit_date: string
  message: string
  content_hash: string
}

export interface FileHistoryResponse {
  path: string
  repository_name: string
  versions: FileVersion[]
  total: number
}

// Blame types
export interface BlameLine {
  line_number: number
  commit_hash: string
  short_hash: string
  author_name: string
  commit_date: string
  message: string
  is_indexed: boolean
}

export interface FileBlameResponse {
  path: string
  repository_name: string
  lines: BlameLine[]
  total: number
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// API functions
async function fetchApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new ApiError(error.detail || `HTTP ${response.status}`, response.status)
  }
  return response.json()
}

// Repositories
export async function getRepositories(): Promise<Repository[]> {
  return fetchApi<Repository[]>('/repositories')
}

export async function getRepository(id: number): Promise<Repository> {
  return fetchApi<Repository>(`/repositories/${id}`)
}

export async function getRepositoryFiles(id: number): Promise<FileInfo[]> {
  return fetchApi<FileInfo[]>(`/repositories/${id}/files`)
}

export async function getRepositoryTree(id: number, commit?: string): Promise<TreeResponse> {
  const params = new URLSearchParams()
  if (commit) params.set('commit', commit)
  const query = params.toString()
  return fetchApi<TreeResponse>(`/repositories/${id}/tree${query ? `?${query}` : ''}`)
}

export async function getRepositoryStats(id: number): Promise<RepositoryStats> {
  return fetchApi<RepositoryStats>(`/repositories/${id}/stats`)
}

export async function getAllRepositoryStats(): Promise<RepositoryStats[]> {
  return fetchApi<RepositoryStats[]>('/repositories/stats')
}

export async function getRepositoryByName(name: string): Promise<Repository> {
  return fetchApi<Repository>(`/repositories/by-name/${encodeURIComponent(name)}`)
}

export async function getRepositoryTreeByName(
  name: string,
  commit?: string,
  branch?: string,
  changedOnly?: boolean
): Promise<TreeResponse> {
  const params = new URLSearchParams()
  if (commit) params.set('commit', commit)
  if (branch) params.set('branch', branch)
  if (changedOnly) params.set('changed_only', 'true')
  const query = params.toString()
  return fetchApi<TreeResponse>(
    `/repositories/by-name/${encodeURIComponent(name)}/tree${query ? `?${query}` : ''}`
  )
}

// Symbol Tree (Logical View)
export interface SymbolTreeFile {
  file_id: number
  path: string
  language: string | null
  symbol_count: number
  kind_counts: Record<string, number>
  all_kind_counts: Record<string, number>
}

export interface SymbolTreeInheritance {
  reference_text: string
  target_symbol_id: number | null
  target_file_id: number | null
  target_file_path: string | null
  target_line: number | null
}

export interface SymbolTreeSymbol {
  id: number
  name: string
  kind: string
  start_line: number
  end_line: number
  file_path: string | null
  has_children: boolean
  signature: string | null
  inheritance: SymbolTreeInheritance[]
}

export interface SymbolTreeResponse {
  repository_id: number
  files: SymbolTreeFile[] | null
  symbols: SymbolTreeSymbol[] | null
  available_kinds: string[] | null
  total_kind_counts: Record<string, number> | null
}

export async function getSymbolTree(
  repoName: string,
  params?: {
    branch?: string
    commit?: string
    file_id?: number
    parent_symbol_id?: number
    language?: string
    kind?: string
    kinds?: string[]
  }
): Promise<SymbolTreeResponse> {
  const searchParams = new URLSearchParams()
  if (params?.branch) searchParams.set('branch', params.branch)
  if (params?.commit) searchParams.set('commit', params.commit)
  if (params?.file_id != null) searchParams.set('file_id', params.file_id.toString())
  if (params?.parent_symbol_id != null)
    searchParams.set('parent_symbol_id', params.parent_symbol_id.toString())
  if (params?.language) searchParams.set('language', params.language)
  if (params?.kind) searchParams.set('kind', params.kind)
  if (params?.kinds && params.kinds.length > 0) searchParams.set('kinds', params.kinds.join(','))
  const query = searchParams.toString()
  return fetchApi<SymbolTreeResponse>(
    `/repositories/by-name/${encodeURIComponent(repoName)}/symbol-tree${query ? `?${query}` : ''}`
  )
}

// Symbols
export async function searchSymbols(params: {
  q?: string
  kind?: string
  repository_id?: number
  branch?: string
  commit?: string
  language?: string
  extensions?: string[]
  mode?: string
  case_sensitive?: boolean
  scope?: 'latest' | 'all_branches' | 'all_history'
  top_level_only?: boolean
  limit?: number
  offset?: number
}): Promise<SymbolListResponse> {
  const searchParams = new URLSearchParams()
  if (params.q) searchParams.set('q', params.q)
  if (params.kind) searchParams.set('kind', params.kind)
  if (params.repository_id) searchParams.set('repository_id', params.repository_id.toString())
  if (params.branch) searchParams.set('branch', params.branch)
  if (params.commit) searchParams.set('commit', params.commit)
  if (params.language) searchParams.set('language', params.language)
  if (params.extensions) {
    params.extensions.forEach((ext) => searchParams.append('extensions', ext))
  }
  if (params.mode) searchParams.set('mode', params.mode)
  if (params.case_sensitive !== undefined)
    searchParams.set('case_sensitive', params.case_sensitive.toString())
  if (params.scope) searchParams.set('scope', params.scope)
  if (params.top_level_only) searchParams.set('top_level_only', 'true')
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())

  const query = searchParams.toString()
  return fetchApi<SymbolListResponse>(`/symbols${query ? `?${query}` : ''}`)
}

export async function getSymbol(id: number): Promise<Symbol> {
  return fetchApi<Symbol>(`/symbols/${id}`)
}

export async function getSymbolsByName(
  name: string,
  repositoryId?: number,
  commit?: string
): Promise<SymbolListResponse> {
  const params = new URLSearchParams()
  if (repositoryId) params.set('repository_id', repositoryId.toString())
  if (commit) params.set('commit', commit)
  const query = params.toString()
  return fetchApi<SymbolListResponse>(
    `/symbols/by-name/${encodeURIComponent(name)}${query ? `?${query}` : ''}`
  )
}

export async function getSymbolReferences(
  id: number,
  limit = 100,
  commit?: string,
  branch?: string
): Promise<ReferencesListResponse> {
  const params = new URLSearchParams()
  params.set('limit', limit.toString())
  if (commit) params.set('commit', commit)
  if (branch) params.set('branch', branch)
  return fetchApi<ReferencesListResponse>(`/symbols/${id}/references?${params}`)
}

// Files
export async function getFileContent(id: number): Promise<FileContent> {
  return fetchApi<FileContent>(`/files/${id}/content`)
}

export async function getFileSymbols(id: number): Promise<FileSymbolsResponse> {
  return fetchApi<FileSymbolsResponse>(`/files/${id}/symbols`)
}

export async function getFileReferences(id: number): Promise<FileReferencesResponse> {
  return fetchApi<FileReferencesResponse>(`/files/${id}/references`)
}

export async function getFileContentByPath(repo: string, path: string): Promise<FileContent> {
  const params = new URLSearchParams({ repo, path })
  return fetchApi<FileContent>(`/files/by-path?${params}`)
}

export async function getFileSymbolsByPath(
  repo: string,
  path: string,
  commit?: string,
  branch?: string
): Promise<FileSymbolsResponse> {
  const params = new URLSearchParams({ repo, path })
  if (commit) params.set('commit', commit)
  if (branch) params.set('branch', branch)
  return fetchApi<FileSymbolsResponse>(`/files/by-path/symbols?${params}`)
}

export async function getFileReferencesByPath(
  repo: string,
  path: string,
  commit?: string,
  branch?: string
): Promise<FileReferencesResponse> {
  const params = new URLSearchParams({ repo, path })
  if (commit) params.set('commit', commit)
  if (branch) params.set('branch', branch)
  return fetchApi<FileReferencesResponse>(`/files/by-path/references?${params}`)
}

// Time Travel functions
export async function getCommits(
  repoName: string,
  branch?: string,
  limit = 50
): Promise<CommitListResponse> {
  const params = new URLSearchParams({ repo: repoName })
  if (branch) params.set('branch', branch)
  params.set('limit', limit.toString())
  return fetchApi<CommitListResponse>(`/commits?${params}`)
}

export async function getRepositoryBranches(repoName: string): Promise<BranchListResponse> {
  return fetchApi<BranchListResponse>(
    `/repositories/by-name/${encodeURIComponent(repoName)}/branches`
  )
}

export async function getFileHistory(
  repo: string,
  path: string,
  branch?: string
): Promise<FileHistoryResponse> {
  const params = new URLSearchParams({ repo, path })
  if (branch) params.set('branch', branch)
  return fetchApi<FileHistoryResponse>(`/files/history?${params}`)
}

export async function getFileContentByPathAtCommit(
  repo: string,
  path: string,
  commit?: string,
  branch?: string
): Promise<FileContent> {
  const params = new URLSearchParams({ repo, path })
  if (commit) params.set('commit', commit)
  if (branch) params.set('branch', branch)
  return fetchApi<FileContent>(`/files/by-path?${params}`)
}

// Raw file content (for images)
export interface RawFileContent {
  path: string
  language: string | null
  content_type: string
  encoding: string // "base64" or "utf-8"
  data: string
  size_bytes: number
}

export async function getFileRawContent(
  repo: string,
  path: string,
  commit?: string,
  branch?: string
): Promise<RawFileContent> {
  const params = new URLSearchParams({ repo, path })
  if (commit) params.set('commit', commit)
  if (branch) params.set('branch', branch)
  return fetchApi<RawFileContent>(`/files/by-path/raw?${params}`)
}

// Blame
export async function getFileBlame(
  repo: string,
  path: string,
  commit?: string,
  branch?: string
): Promise<FileBlameResponse> {
  const params = new URLSearchParams({ repo, path })
  if (commit) params.set('commit', commit)
  if (branch) params.set('branch', branch)
  return fetchApi<FileBlameResponse>(`/files/by-path/blame?${params}`)
}

// Text Search types and functions
export interface TextSearchParams {
  q: string
  mode?: 'keyword' | 'phrase' | 'regex'
  repo?: number
  branch?: string
  commit?: string
  source_types?: string[]
  languages?: string[]
  extensions?: string[]
  case_sensitive?: boolean
  scope?: 'latest' | 'all_branches' | 'all_history'
  limit?: number
  offset?: number
}

export interface TextSearchResult {
  id: number
  repository_id: number
  repository_name: string
  file_path: string | null
  source_line: number | null
  source_end_line: number | null
  source_type: string
  content: string
  content_type: string | null
  language: string | null
  commit_hash: string | null
  branch: string | null
  rank: number
  headline: string | null
}

export interface TextSearchResponse {
  results: TextSearchResult[]
  total: number
  query: string
  mode: string
  limit: number
  offset: number
}

export async function searchText(params: TextSearchParams): Promise<TextSearchResponse> {
  const searchParams = new URLSearchParams()
  searchParams.set('q', params.q)
  if (params.mode) searchParams.set('mode', params.mode)
  if (params.repo) searchParams.set('repository_id', params.repo.toString())
  if (params.branch) searchParams.set('branch', params.branch)
  if (params.commit) searchParams.set('commit_hash', params.commit)
  if (params.source_types) {
    params.source_types.forEach((type) => searchParams.append('source_types', type))
  }
  if (params.languages) {
    params.languages.forEach((lang) => searchParams.append('languages', lang))
  }
  if (params.extensions) {
    params.extensions.forEach((ext) => searchParams.append('extensions', ext))
  }
  if (params.case_sensitive !== undefined)
    searchParams.set('case_sensitive', params.case_sensitive.toString())
  if (params.scope) searchParams.set('scope', params.scope)
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())

  return fetchApi<TextSearchResponse>(`/search/text?${searchParams}`)
}

// File Search types and functions
export interface FileSearchParams {
  q: string
  repository?: string
  branch?: string
  commit_hash?: string
  language?: string
  extensions?: string[]
  scope?: 'latest' | 'all_branches' | 'all_history'
  limit?: number
  offset?: number
}

export interface FileSearchResult {
  id: number
  path: string
  name: string
  language: string | null
  repository_id: number
  repository_name: string
  commit_id: number
  commit_hash: string
}

export interface FileSearchResponse {
  files: FileSearchResult[]
  total_count: number
  limit: number
  offset: number
}

export async function searchFiles(params: FileSearchParams): Promise<FileSearchResponse> {
  const searchParams = new URLSearchParams()
  searchParams.set('q', params.q)
  if (params.repository) searchParams.set('repository', params.repository)
  if (params.branch) searchParams.set('branch', params.branch)
  if (params.commit_hash) searchParams.set('commit_hash', params.commit_hash)
  if (params.language) searchParams.set('language', params.language)
  if (params.extensions) {
    params.extensions.forEach((ext) => searchParams.append('extensions', ext))
  }
  if (params.scope) searchParams.set('scope', params.scope)
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())

  return fetchApi<FileSearchResponse>(`/search/files?${searchParams}`)
}

// File Extensions
export interface ExtensionsResponse {
  extensions: string[]
}

export async function getFileExtensions(params?: {
  repository_id?: number
  branch?: string
  scope?: 'latest'
}): Promise<ExtensionsResponse> {
  const searchParams = new URLSearchParams()
  if (params?.repository_id) searchParams.set('repository_id', params.repository_id.toString())
  if (params?.branch) searchParams.set('branch', params.branch)
  if (params?.scope) searchParams.set('scope', params.scope)
  const query = searchParams.toString()
  return fetchApi<ExtensionsResponse>(`/search/extensions${query ? `?${query}` : ''}`)
}

// Dependency Search types and functions
export interface DependencySearchParams {
  q: string
  repository_id?: number
  language?: string
  dependency_type?: string
  is_direct?: boolean
  branch?: string
  limit?: number
  offset?: number
}

export interface DependencySearchResult {
  id: number
  package_name: string
  language: string
  version_spec: string | null
  resolved_version: string | null
  dependency_type: string
  is_direct: boolean
  file_id: number
  file_path: string | null
  repository_id: number
  repository_name: string
  source_line: number | null
}

export interface DependencySearchResponse {
  results: DependencySearchResult[]
  total: number
  query: string
  limit: number
  offset: number
}

export async function searchDependencies(
  params: DependencySearchParams
): Promise<DependencySearchResponse> {
  const searchParams = new URLSearchParams()
  searchParams.set('q', params.q)
  if (params.repository_id) searchParams.set('repository_id', params.repository_id.toString())
  if (params.language) searchParams.set('language', params.language)
  if (params.dependency_type) searchParams.set('dependency_type', params.dependency_type)
  if (params.is_direct !== undefined) searchParams.set('is_direct', params.is_direct.toString())
  if (params.branch) searchParams.set('branch', params.branch)
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())

  return fetchApi<DependencySearchResponse>(`/search/dependencies?${searchParams}`)
}

// Dependencies
export interface DependencyItem {
  id: number
  package_name: string
  language: string
  version_spec: string | null
  resolved_version: string | null
  dependency_type: string
  is_direct: boolean
  file_id: number
  file_path: string | null
  source_line: number | null
}

export interface DependenciesListResponse {
  repository_id: number
  repository_name: string
  commit_hash: string | null
  items: DependencyItem[]
  total: number
}

export async function getRepositoryDependencies(
  repoName: string,
  params?: {
    commit?: string
    branch?: string
    language?: string
    dependency_type?: string
    is_direct?: boolean
  }
): Promise<DependenciesListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.commit) searchParams.set('commit', params.commit)
  if (params?.branch) searchParams.set('branch', params.branch)
  if (params?.language) searchParams.set('language', params.language)
  if (params?.dependency_type) searchParams.set('dependency_type', params.dependency_type)
  if (params?.is_direct !== undefined) searchParams.set('is_direct', params.is_direct.toString())
  const query = searchParams.toString()
  return fetchApi<DependenciesListResponse>(
    `/repositories/by-name/${encodeURIComponent(repoName)}/dependencies${query ? `?${query}` : ''}`
  )
}

export interface ResolvePathResult {
  found: boolean
  resolved_path: string | null
  renamed_from: string | null
  renamed_to: string | null
  rename_commit_hash: string | null
}

export async function resolveFilePath(
  repo: string,
  path: string,
  commit: string,
  branch?: string
): Promise<ResolvePathResult> {
  const params = new URLSearchParams({ repo, path, commit })
  if (branch) params.set('branch', branch)
  return fetchApi<ResolvePathResult>(`/renames/resolve-path?${params}`)
}

export interface ActivityEntry {
  id: number
  source: string
  tool_or_path: string
  logged_at: string
  params: Record<string, unknown> | null
  repository: string | null
  status_code: number | null
  duration_ms: number | null
  result_count: number | null
  session_id: string | null
}

export interface ActivityLogResponse {
  entries: ActivityEntry[]
  returned_count: number
}

export async function getActivityLog(params?: {
  source?: string
  repository?: string
  limit?: number
  offset?: number
}): Promise<ActivityLogResponse> {
  const searchParams = new URLSearchParams()
  if (params?.source) searchParams.set('source', params.source)
  if (params?.repository) searchParams.set('repository', params.repository)
  if (params?.limit !== undefined) searchParams.set('limit', params.limit.toString())
  if (params?.offset !== undefined) searchParams.set('offset', params.offset.toString())
  const query = searchParams.toString()
  return fetchApi<ActivityLogResponse>(`/activity${query ? `?${query}` : ''}`)
}
