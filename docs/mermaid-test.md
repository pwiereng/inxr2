# Mermaid Diagram Test

This file tests mermaid diagram rendering in the INXR2 markdown viewer.

## Flowchart

```mermaid
graph TD
    A[User Request] --> B{Authenticated?}
    B -- Yes --> C[Load Repository]
    B -- No --> D[Return 401]
    C --> E[Parse File]
    E --> F[Highlight Symbols]
    F --> G[Return Response]
```

## Sequence Diagram

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI
    participant PostgreSQL

    Browser->>FastAPI: GET /api/repos/inxr2/files/README.md
    FastAPI->>PostgreSQL: SELECT file WHERE path = 'README.md'
    PostgreSQL-->>FastAPI: FileRecord
    FastAPI-->>Browser: FileContent + Symbols
```

## Class Diagram

```mermaid
classDiagram
    class Repository {
        +String name
        +String path
        +index()
    }
    class File {
        +String path
        +String content
        +List~Symbol~ symbols
    }
    class Symbol {
        +String name
        +String kind
        +int line
    }
    Repository "1" --> "*" File
    File "1" --> "*" Symbol
```

## Git Graph

```mermaid
gitGraph
    commit id: "Initial commit"
    branch feat/mermaid
    checkout feat/mermaid
    commit id: "Add mermaid dep"
    commit id: "Implement MermaidDiagram"
    checkout main
    merge feat/mermaid id: "Merge PR #383"
```

## Non-mermaid code block (should use Prism, not mermaid)

```python
def index_repository(repo: Repository) -> IndexResult:
    """Index all files in a repository."""
    symbols = []
    for file in repo.files():
        symbols.extend(parse_symbols(file))
    return IndexResult(symbols=symbols)
```
