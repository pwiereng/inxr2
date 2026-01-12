/**
 * API client for INXR2 backend
 */

const API_BASE = 'http://localhost:8000/api';

// Types
export interface Repository {
  id: number;
  name: string;
  url: string;
  description: string | null;
  default_branch: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface FileInfo {
  id: number;
  repository_id: number;
  commit_id: number;
  path: string;
  language: string | null;
  size_bytes: number;
  line_count: number | null;
}

export interface Symbol {
  id: number;
  name: string;
  qualified_name: string | null;
  kind: string;
  file_id: number;
  file_path: string | null;
  repository_id: number;
  commit_id: number;
  start_line: number;
  start_column: number;
  end_line: number;
  end_column: number;
  signature: string | null;
  docstring: string | null;
}

export interface SymbolListResponse {
  items: Symbol[];
  total: number;
  limit: number;
  offset: number;
}

export interface Reference {
  id: number;
  source_file_id: number;
  source_file_path: string | null;
  source_line: number;
  source_column: number;
  target_symbol_id: number | null;
  reference_text: string;
  reference_type: string;
}

export interface ReferencesListResponse {
  items: Reference[];
  total: number;
  symbol_name: string;
}

export interface FileContent {
  id: number;
  path: string;
  language: string | null;
  content: string;
  line_count: number;
  size_bytes: number;
}

export interface FileSymbol {
  id: number;
  name: string;
  qualified_name: string | null;
  kind: string;
  start_line: number;
  start_column: number;
  end_line: number;
  end_column: number;
  signature: string | null;
}

export interface FileSymbolsResponse {
  file_id: number;
  file_path: string;
  symbols: FileSymbol[];
  total: number;
}

export interface FileReference {
  id: number;
  reference_text: string;
  reference_type: string;
  source_line: number;
  source_column: number;
  target_symbol_id: number | null;
}

export interface FileReferencesResponse {
  file_id: number;
  file_path: string;
  references: FileReference[];
  total: number;
}

export interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  file_id: number | null;
  language: string | null;
  children: TreeNode[] | null;
}

export interface TreeResponse {
  repository_id: number;
  repository_name: string;
  root: TreeNode[];
  total_files: number;
  total_directories: number;
}

export interface RepositoryStats {
  repository_id: number;
  name: string;
  total_files: number;
  total_symbols: number;
  total_references: number;
  languages: Record<string, number>;
}

// API functions
async function fetchApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// Repositories
export async function getRepositories(): Promise<Repository[]> {
  return fetchApi<Repository[]>('/repositories');
}

export async function getRepository(id: number): Promise<Repository> {
  return fetchApi<Repository>(`/repositories/${id}`);
}

export async function getRepositoryFiles(id: number): Promise<FileInfo[]> {
  return fetchApi<FileInfo[]>(`/repositories/${id}/files`);
}

export async function getRepositoryTree(id: number): Promise<TreeResponse> {
  return fetchApi<TreeResponse>(`/repositories/${id}/tree`);
}

export async function getRepositoryStats(id: number): Promise<RepositoryStats> {
  return fetchApi<RepositoryStats>(`/repositories/${id}/stats`);
}

// Symbols
export async function searchSymbols(params: {
  q?: string;
  kind?: string;
  repository_id?: number;
  limit?: number;
  offset?: number;
}): Promise<SymbolListResponse> {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set('q', params.q);
  if (params.kind) searchParams.set('kind', params.kind);
  if (params.repository_id) searchParams.set('repository_id', params.repository_id.toString());
  if (params.limit) searchParams.set('limit', params.limit.toString());
  if (params.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  return fetchApi<SymbolListResponse>(`/symbols${query ? `?${query}` : ''}`);
}

export async function getSymbol(id: number): Promise<Symbol> {
  return fetchApi<Symbol>(`/symbols/${id}`);
}

export async function getSymbolReferences(id: number, limit = 100): Promise<ReferencesListResponse> {
  return fetchApi<ReferencesListResponse>(`/symbols/${id}/references?limit=${limit}`);
}

// Files
export async function getFileContent(id: number): Promise<FileContent> {
  return fetchApi<FileContent>(`/files/${id}/content`);
}

export async function getFileSymbols(id: number): Promise<FileSymbolsResponse> {
  return fetchApi<FileSymbolsResponse>(`/files/${id}/symbols`);
}

export async function getFileReferences(id: number): Promise<FileReferencesResponse> {
  return fetchApi<FileReferencesResponse>(`/files/${id}/references`);
}
