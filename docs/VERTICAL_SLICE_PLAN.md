# Vertical Slice: Basic File Indexing and Display

## Goal
Get a basic end-to-end flow working: index files from a directory → store in database → display in UI.

## Scope (Minimal)

### Backend
1. **Simple Indexer** (no git, no tree-sitter yet)
   - Read files from a local directory
   - Detect file language (by extension)
   - Create Repository, Commit, File entities
   - Save to database

2. **API Endpoints**
   - `GET /api/repositories` - List all repositories
   - `GET /api/repositories/{id}` - Get repository details
   - `GET /api/repositories/{id}/files` - List files in repository
   - `POST /api/index/local` - Index a local directory

3. **Use Cases**
   - `IndexLocalDirectoryUseCase` - Index files from local path
   - `ListRepositoriesUseCase` - Get all repositories
   - `GetRepositoryFilesUseCase` - Get files for a repository

### Frontend
1. **Repositories Page**
   - List of indexed repositories
   - Show name, file count, indexed date
   - Button to view files

2. **Files Page**
   - List files for selected repository
   - Show path, language, size
   - Filter/search by path or language

### Database
- Use existing schema (repositories, commits, files tables)
- No symbols or references yet (too complex for first slice)

## Implementation Order

### Phase 1: Backend Indexer (2-3 hours)
1. Create `IndexLocalDirectoryUseCase`
   - Input: directory path
   - Walk directory tree
   - Detect file language by extension
   - Create Repository entity
   - Create dummy Commit entity (hash = "local")
   - Create File entities for each file
   - Save via repository ports

2. Create language detector utility
   - Simple extension mapping (.py → python, .js → javascript, etc.)

### Phase 2: Backend API (1 hour)
1. Create FastAPI routes in `adapters/api/routes/`
   - `repositories.py` - Repository endpoints
   - `indexing.py` - Indexing endpoint

2. Create DTOs/Serializers
   - RepositoryResponse
   - FileResponse
   - IndexRequest

3. Wire up dependency injection

### Phase 3: Frontend UI (2 hours)
1. Create Repositories page
   - Fetch from `/api/repositories`
   - Display in table/grid
   - Link to files page

2. Create Files page
   - Fetch from `/api/repositories/{id}/files`
   - Display in table
   - Show path, language, size
   - Simple search/filter

### Phase 4: Testing & Demo (1 hour)
1. Index the inxr2 project itself
2. Verify data in database
3. Test UI flow
4. Screenshot for demo

## Out of Scope (For Later)
- ❌ Git integration (cloning, branches, commits)
- ❌ Tree-sitter parsing (symbols, references)
- ❌ Full-text search
- ❌ Code viewer
- ❌ Cross-references
- ❌ Incremental indexing

## Success Criteria
✅ Can index a local directory via API
✅ Files stored in database with metadata
✅ UI shows list of repositories
✅ UI shows list of files for a repository
✅ End-to-end flow works without errors

## Example Flow

```bash
# 1. Start backend
docker exec -it inxr2-dev bash
source /home/devuser/.venv/bin/activate
inxr2 serve --reload

# 2. Index current project
curl -X POST http://localhost:8000/api/index/local \
  -H "Content-Type: application/json" \
  -d '{"path": "/workspace", "name": "inxr2"}'

# 3. Start frontend
cd frontend && npm run dev

# 4. Open browser
# http://localhost:5173
# See "inxr2" repository
# Click → see all files
```

## Technical Details

### Language Detection
```python
LANGUAGE_MAP = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.jsx': 'javascript',
    '.java': 'java',
    '.go': 'go',
    '.rs': 'rust',
    '.c': 'c',
    '.cpp': 'cpp',
    '.h': 'c',
    '.hpp': 'cpp',
    '.sh': 'shell',
    '.md': 'markdown',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
}
```

### File Walking
```python
import os
from pathlib import Path

def walk_directory(path: str) -> list[Path]:
    """Walk directory and return all files."""
    files = []
    for root, dirs, filenames in os.walk(path):
        # Skip common ignore patterns
        dirs[:] = [d for d in dirs if not d.startswith('.')
                   and d not in ['node_modules', '__pycache__', 'venv']]

        for filename in filenames:
            if not filename.startswith('.'):
                files.append(Path(root) / filename)

    return files
```

### API Request/Response
```typescript
// Request
interface IndexLocalRequest {
  path: string;
  name: string;
  description?: string;
}

// Response
interface Repository {
  id: number;
  name: string;
  description?: string;
  file_count: number;
  indexed_at: string;
}

interface File {
  id: number;
  path: string;
  language: string;
  size_bytes: number;
}
```

## Next Steps After This Slice

Once this works, we can incrementally add:
1. Git integration (real commits instead of dummy)
2. Tree-sitter parsing (extract symbols)
3. Symbol display in UI
4. Code viewer with syntax highlighting
5. Cross-reference navigation
