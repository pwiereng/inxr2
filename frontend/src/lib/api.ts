/**
 * API client for INXR2 backend
 */

const API_BASE = 'http://localhost:8000/api'

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
}

// Time Travel types
export interface CommitInfo {
  id: number
  hash: string
  short_hash: string
  branch: string | null
  message: string
  author_name: string
  author_email: string
  commit_date: string
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

// API functions
async function fetchApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
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

export async function getRepositoryByName(name: string): Promise<Repository> {
  return fetchApi<Repository>(`/repositories/by-name/${encodeURIComponent(name)}`)
}

export async function getRepositoryTreeByName(
  name: string,
  commit?: string,
  branch?: string
): Promise<TreeResponse> {
  const params = new URLSearchParams()
  if (commit) params.set('commit', commit)
  if (branch) params.set('branch', branch)
  const query = params.toString()
  return fetchApi<TreeResponse>(
    `/repositories/by-name/${encodeURIComponent(name)}/tree${query ? `?${query}` : ''}`
  )
}

// Symbols
export async function searchSymbols(params: {
  q?: string
  kind?: string
  repository_id?: number
  limit?: number
  offset?: number
}): Promise<SymbolListResponse> {
  const searchParams = new URLSearchParams()
  if (params.q) searchParams.set('q', params.q)
  if (params.kind) searchParams.set('kind', params.kind)
  if (params.repository_id) searchParams.set('repository_id', params.repository_id.toString())
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

export async function getRepositoryBranches(repoId: number): Promise<BranchListResponse> {
  return fetchApi<BranchListResponse>(`/repositories/${repoId}/branches`)
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

// Text Search types and functions
export interface TextSearchParams {
  q: string
  mode?: 'keyword' | 'phrase' | 'regex'
  repo?: number
  branch?: string
  commit?: string
  source_types?: string[]
  languages?: string[]
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
  commit_hash: string
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
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())

  return fetchApi<TextSearchResponse>(`/search/text?${searchParams}`)
}
