---
name: new-feature
description: "Step-by-step guide for adding a new feature following Clean Architecture. Covers domain, ports, tests, adapters, migrations, and DI wiring."
user-invocable: true
argument-hint: "<brief description of the feature>"
---

# New Feature Workflow

Follow Clean Architecture layers when adding features. Start from the inside and work outward.

## Steps

1. **Plan** — Identify which layer(s) the feature touches
2. **Domain First** — Start with domain entities and use cases
3. **Ports** — Define interfaces for external dependencies
4. **Tests** — Write tests using fake implementations (NOT mocks)
5. **Adapters** — Implement adapters (API, database, etc.)
6. **Integration** — Wire up with dependency injection

## Example: Adding a Use Case

```python
# 1. Use case (application layer)
class SearchSymbolsUseCase:
    def __init__(self, symbol_repository: SymbolRepositoryPort):
        self._symbol_repository = symbol_repository

    async def execute(self, request: SearchSymbolsRequest) -> SearchSymbolsResponse:
        symbols = await self._symbol_repository.search_by_name(request.query)
        return SearchSymbolsResponse(symbols=symbols, total_count=len(symbols))

# 2. Port (application layer)
class SymbolRepositoryPort(ABC):
    @abstractmethod
    async def search_by_name(self, name: str) -> list[Symbol]: ...

# 3. Test (with fake)
def test_search_symbols():
    fake_repo = FakeSymbolRepository()
    fake_repo.add_test_symbol(Symbol(...))
    use_case = SearchSymbolsUseCase(symbol_repository=fake_repo)
    result = await use_case.execute(SearchSymbolsRequest(query="test"))
    assert len(result.symbols) == 1

# 4. Adapter implementation
class PostgresSymbolRepository(SymbolRepositoryPort):
    async def search_by_name(self, name: str) -> list[Symbol]:
        models = await self.session.execute(
            select(SymbolModel).where(SymbolModel.name.contains(name))
        )
        return [self.mapper.to_domain(m) for m in models.scalars()]

# 5. API controller
@router.get("/symbols/search")
async def search_symbols(q: str, repo: SymbolRepositoryPort = Depends()):
    use_case = SearchSymbolsUseCase(symbol_repository=repo)
    result = await use_case.execute(SearchSymbolsRequest(query=q))
    return result
```

## Database Migrations

When adding/modifying database schema:

1. Update domain entity if needed
2. Update ORM model in `adapters/persistence/models/`
3. Update mapper if field names changed
4. Generate migration: `alembic revision --autogenerate -m "description"`
5. Review generated migration (fix any issues)
6. Apply migration: `alembic upgrade head`
7. Update tests

**Common Issues:**
- Field name conflicts: Use `extra_metadata` not `metadata` in ORM models
- Relationship ambiguity: Specify `foreign_keys` parameter explicitly

## Testing with Fakes (NOT Mocks)

❌ **DON'T** use `unittest.mock.Mock` — tests become brittle and break on refactoring.

✅ **DO** create fake implementations of ports:
```python
class FakeSymbolRepository(SymbolRepositoryPort):
    def __init__(self):
        self._symbols = {}

    async def search_by_name(self, name: str) -> list[Symbol]:
        return [s for s in self._symbols.values() if name in s.name]
```

See `tests/fixtures/test_doubles.py` for shared fakes.
See `tests/unit/application/test_default_indexing_orchestrator.py` for complete examples.
