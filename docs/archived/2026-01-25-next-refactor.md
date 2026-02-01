# Next Refactor: Extract Business Logic from Controllers

**Priority**: 2 (High)
**Estimated Effort**: 3-4 days
**Source**: Architectural Review - Priority 2 item

---

## Overview

Several API route controllers contain business logic that should be extracted to use cases in the application layer. This violates Clean Architecture principles where controllers should be thin coordinators that delegate to use cases.

**Current Issues:**
- Controllers directly access `GitService` (should go through use cases)
- Controllers orchestrate multiple adapters for aggregations
- Controllers handle branch/file resolution logic
- Controllers format complex responses from raw adapter data
- Significant code duplication across endpoints

---

## Critical Issues (High Duplication)

### 1. File Resolution Pattern (3 endpoints)

**Location**: `src/inxr2/adapters/api/routes/files.py`

**Problem**: Three endpoints have nearly identical 50-line blocks implementing file resolution with priority: commit > branch > latest.

**Duplicated in:**
- `get_file_content_by_path` (lines 162-209)
- `get_file_symbols_by_path` (lines 369-405)
- `get_file_references_by_path` (lines 469-501)

**Solution**: Create `ResolveFileUseCase`

```python
# application/use_cases/files/resolve_file.py
@dataclass
class ResolveFileRequest:
    repository_name: str
    file_path: str
    commit_hash: str | None = None
    branch: str | None = None

@dataclass
class ResolveFileResponse:
    file: File
    commit: Commit
    repository: Repository

class ResolveFileUseCase:
    def __init__(
        self,
        repository_repo: RepositoryRepositoryPort,
        file_repo: FileRepositoryPort,
        commit_repo: CommitRepositoryPort,
    ):
        self._repository_repo = repository_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo

    async def execute(self, request: ResolveFileRequest) -> ResolveFileResponse:
        # 1. Find repository by name
        # 2. If commit_hash provided, use it directly
        # 3. Else if branch provided, find latest commit for branch
        # 4. Else use repository's default branch
        # 5. Find file at resolved commit
        # 6. Return resolved file with context
        ...
```

---

### 2. Repository Statistics Aggregation

**Location**: `src/inxr2/adapters/api/routes/repositories.py` (lines 292-328)

**Problem**: Endpoint manually orchestrates 4 adapter calls to build statistics response.

**Current code pattern:**
```python
# In controller - this is orchestration logic
files = await file_adapter.list_by_repository(repo_id)
symbols = await symbol_adapter.list_by_repository(repo_id)
references = await reference_adapter.list_by_repository(repo_id)
# ... aggregate counts, build language distribution
```

**Solution**: Create `GetRepositoryStatsUseCase`

```python
# application/use_cases/repositories/get_repository_stats.py
@dataclass
class RepositoryStats:
    file_count: int
    symbol_count: int
    reference_count: int
    language_distribution: dict[str, int]
    last_indexed: datetime | None

class GetRepositoryStatsUseCase:
    def __init__(
        self,
        file_repo: FileRepositoryPort,
        symbol_repo: SymbolRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
    ):
        ...

    async def execute(self, repository_id: int) -> RepositoryStats:
        # Orchestrate all adapter calls
        # Build aggregated stats
        ...
```

---

### 3. Repository Branches with Git Integration

**Location**: `src/inxr2/adapters/api/routes/repositories.py` (lines 331-388)

**Problem**: Controller directly calls `GitService` and correlates with database indexing status.

**Current code pattern:**
```python
# In controller - direct git service access
branches = git_service.list_branches(repo_path)
# ... correlate with DB index status for each branch
```

**Solution**: Create `GetRepositoryBranchesUseCase`

```python
# application/use_cases/repositories/get_repository_branches.py
@dataclass
class BranchInfo:
    name: str
    is_indexed: bool
    last_indexed_commit: str | None
    commit_count: int | None

@dataclass
class GetRepositoryBranchesResponse:
    branches: list[BranchInfo]
    default_branch: str

class GetRepositoryBranchesUseCase:
    def __init__(
        self,
        repository_repo: RepositoryRepositoryPort,
        commit_repo: CommitRepositoryPort,
        git_service: GitServicePort,
    ):
        ...

    async def execute(self, repository_id: int) -> GetRepositoryBranchesResponse:
        # 1. Get repository path
        # 2. Fetch branches from git
        # 3. Correlate with DB indexing status
        # 4. Return enriched branch info
        ...
```

---

## Important Issues (Orchestration Logic)

### 4. Symbol/Reference File Path Enrichment

**Location**: `src/inxr2/adapters/api/routes/symbols.py` (lines 105-131)

**Problem**: N+1 query pattern - for each symbol/reference, makes separate query to get file path.

**Current code pattern:**
```python
# In controller - N+1 queries
for symbol in symbols:
    file = await file_adapter.find_by_id(symbol.file_id)
    symbol_with_path = SymbolResponse(..., file_path=file.path)
```

**Solution Options:**

A. Add repository method that returns pre-enriched objects:
```python
# In FileRepositoryPort
async def find_symbols_with_file_paths(
    repository_id: int,
    query: str
) -> list[SymbolWithFilePath]:
    # JOIN symbols with files in single query
```

B. Create use case that handles enrichment efficiently:
```python
class SearchSymbolsUseCase:
    async def execute(request: SearchSymbolsRequest) -> SearchSymbolsResponse:
        symbols = await self._symbol_repo.search(...)
        file_ids = {s.file_id for s in symbols}
        files = await self._file_repo.find_by_ids(file_ids)  # Single query
        # Map and return enriched symbols
```

---

### 5. Symbol References with Decision Logic

**Location**: `src/inxr2/adapters/api/routes/symbols.py` (lines 291-300)

**Problem**: Controller contains decision logic for how to fetch references (by symbol ID vs. by name).

**Solution**: Create `GetSymbolReferencesUseCase`

```python
@dataclass
class GetSymbolReferencesRequest:
    repository_id: int
    symbol_id: int | None = None
    symbol_name: str | None = None
    by_name: bool = False
    commit_hash: str | None = None

class GetSymbolReferencesUseCase:
    async def execute(self, request: GetSymbolReferencesRequest) -> list[ReferenceWithContext]:
        # Handle by_name vs by_id decision
        # Resolve commit if provided
        # Enrich references with file paths
        ...
```

---

### 6. File Content from Git

**Location**: `src/inxr2/adapters/api/routes/files.py` (lines 210-249, 562-575)

**Problem**: Two endpoints have duplicate logic for fetching file content from git with error handling.

**Solution**: Create `GetFileContentUseCase`

```python
@dataclass
class GetFileContentRequest:
    repository_name: str
    file_path: str
    commit_hash: str | None = None
    branch: str | None = None

@dataclass
class GetFileContentResponse:
    content: str
    file: File
    commit: Commit
    is_binary: bool

class GetFileContentUseCase:
    def __init__(
        self,
        resolve_file_use_case: ResolveFileUseCase,
        git_service: GitServicePort,
    ):
        ...

    async def execute(self, request: GetFileContentRequest) -> GetFileContentResponse:
        # 1. Resolve file using ResolveFileUseCase
        # 2. Fetch content from git
        # 3. Handle binary file detection
        # 4. Handle errors (file not found, etc.)
        ...
```

---

### 7. Commit List with Git Metadata Hydration

**Location**: `src/inxr2/adapters/api/routes/commits.py` (lines 103-129)

**Problem**: Controller fetches commits from DB, then hydrates each with git metadata (author, message) using caching logic.

**Solution**: Create `GetCommitListUseCase`

```python
@dataclass
class CommitWithMetadata:
    commit: Commit
    author_name: str
    author_email: str
    message: str

class GetCommitListUseCase:
    def __init__(
        self,
        commit_repo: CommitRepositoryPort,
        git_service: GitServicePort,
    ):
        ...

    async def execute(
        self,
        repository_id: int,
        branch: str | None = None,
        limit: int = 50
    ) -> list[CommitWithMetadata]:
        # 1. Get commits from DB
        # 2. Batch fetch metadata from git (with caching)
        # 3. Return enriched commits
        ...
```

---

### 8. File History with Commit Info

**Location**: `src/inxr2/adapters/api/routes/files.py` (lines 299-327)

**Problem**: Controller fetches file versions, then hydrates each with commit message from git.

**Solution**: Create `GetFileHistoryUseCase`

```python
@dataclass
class FileVersionWithCommitInfo:
    file: File
    commit_hash: str
    commit_message: str
    commit_date: datetime
    author_name: str

class GetFileHistoryUseCase:
    async def execute(
        self,
        repository_id: int,
        file_path: str,
        branch: str | None = None
    ) -> list[FileVersionWithCommitInfo]:
        # 1. Get file versions from DB
        # 2. Hydrate commit info from git
        # 3. Return enriched history
        ...
```

---

## Implementation Plan

### Phase 1: Core Resolution Use Cases (Day 1)

1. **Create `ResolveFileUseCase`**
   - Extract file resolution logic from files.py
   - Add comprehensive tests
   - Update 3 endpoints to use it

2. **Create `ResolveBranchToCommitUseCase`** (helper)
   - Extract branch → commit resolution
   - Used by ResolveFileUseCase and others

### Phase 2: Repository Use Cases (Day 2)

3. **Create `GetRepositoryStatsUseCase`**
   - Extract statistics aggregation
   - Update repositories.py endpoint

4. **Create `GetRepositoryBranchesUseCase`**
   - Extract git + DB branch correlation
   - Update repositories.py endpoint

### Phase 3: File & Symbol Use Cases (Day 3)

5. **Create `GetFileContentUseCase`**
   - Compose with ResolveFileUseCase
   - Update files.py endpoints

6. **Create `GetFileHistoryUseCase`**
   - Extract commit info hydration
   - Update files.py endpoint

7. **Enhance symbol enrichment**
   - Add `find_by_ids` to FileRepositoryPort
   - Update symbol search to batch fetch files

### Phase 4: Remaining Use Cases (Day 4)

8. **Create `GetSymbolReferencesUseCase`**
   - Extract reference fetching logic
   - Update symbols.py endpoint

9. **Create `GetCommitListUseCase`**
   - Extract commit hydration with caching
   - Update commits.py endpoint

10. **Final cleanup**
    - Remove dead code from controllers
    - Update tests
    - Run full test suite

---

## Files to Modify

### New Files (Application Layer)
```
src/inxr2/application/use_cases/files/
├── resolve_file.py
├── get_file_content.py
└── get_file_history.py

src/inxr2/application/use_cases/repositories/
├── get_repository_stats.py
└── get_repository_branches.py

src/inxr2/application/use_cases/symbols/
└── get_symbol_references.py

src/inxr2/application/use_cases/commits/
└── get_commit_list.py
```

### Modified Files (Adapters Layer)
```
src/inxr2/adapters/api/routes/
├── files.py          # Use new use cases
├── repositories.py   # Use new use cases
├── symbols.py        # Use new use cases
└── commits.py        # Use new use cases

src/inxr2/adapters/persistence/repositories/
└── file_adapter.py   # Add find_by_ids method
```

### New Test Files
```
tests/unit/application/use_cases/
├── test_resolve_file.py
├── test_get_file_content.py
├── test_get_file_history.py
├── test_get_repository_stats.py
├── test_get_repository_branches.py
├── test_get_symbol_references.py
└── test_get_commit_list.py
```

---

## Verification

```bash
# Run all tests
docker exec inxr2-dev ./scripts/run-all-tests.sh

# Run specific use case tests
docker exec inxr2-dev pytest tests/unit/application/use_cases/ -v

# Type check
docker exec inxr2-dev mypy src/ tests/

# Verify no regressions in API behavior
docker exec inxr2-dev pytest tests/integration/api/ -v
```

---

## Benefits After Refactor

1. **Testability**: Use cases can be unit tested with fake repositories
2. **Reusability**: Use cases can be called from CLI, other endpoints, background jobs
3. **Maintainability**: Single source of truth for each business operation
4. **Clean Architecture**: Controllers become thin coordinators
5. **Reduced Duplication**: File resolution logic in one place instead of three
