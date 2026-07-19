"""Tests for the PHP language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


@pytest.fixture
def parser_service() -> TreeSitterService:
    return TreeSitterService()


async def parse(service: TreeSitterService, code: str) -> tuple[list, list]:
    return await service.parse_file(code, "php", "test.php")


class TestPhpSupport:
    def test_supports_php(self, parser_service: TreeSitterService) -> None:
        assert parser_service.supports_language("php")
        assert parser_service.supports_language("PHP")

    def test_php_extensions_registered(self, parser_service: TreeSitterService) -> None:
        exts = parser_service.SUPPORTED_LANGUAGES.get("php", [])
        assert ".php" in exts
        assert ".phtml" in exts


class TestPhpClasses:
    @pytest.mark.asyncio
    async def test_simple_class(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nclass User {}\n"
        symbols, _ = await parse(parser_service, code)
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "User"

    @pytest.mark.asyncio
    async def test_class_with_methods_and_properties(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """<?php
class Account {
    public int $balance = 0;
    protected string $owner;

    public function deposit(int $amount): void {}
    private function log(): void {}
}
"""
        symbols, _ = await parse(parser_service, code)
        methods = {s.name for s in symbols if s.kind == "method"}
        props = {s.name for s in symbols if s.kind == "property"}
        assert methods == {"deposit", "log"}
        assert props == {"balance", "owner"}

    @pytest.mark.asyncio
    async def test_method_scoped_to_class(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nclass Foo {\n    public function bar(): void {}\n}\n"
        symbols, _ = await parse(parser_service, code)
        method = next(s for s in symbols if s.kind == "method")
        assert method.scope == "Foo"
        assert method.qualified_name == "Foo::bar"

    @pytest.mark.asyncio
    async def test_method_signature(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nclass Foo {\n    public function bar(int $x): string { return ''; }\n}\n"
        symbols, _ = await parse(parser_service, code)
        method = next(s for s in symbols if s.kind == "method")
        assert method.signature == "bar(int $x): string"

    @pytest.mark.asyncio
    async def test_class_constants(self, parser_service: TreeSitterService) -> None:
        code = """<?php
class Config {
    const VERSION = '1.0';
    public const MAX = 100;
}
"""
        symbols, _ = await parse(parser_service, code)
        consts = {s.name for s in symbols if s.kind == "constant"}
        assert consts == {"VERSION", "MAX"}


class TestPhpInterfacesTraitsEnums:
    @pytest.mark.asyncio
    async def test_interface(self, parser_service: TreeSitterService) -> None:
        code = "<?php\ninterface Repository {\n    public function find(int $id);\n}\n"
        symbols, _ = await parse(parser_service, code)
        iface = next(s for s in symbols if s.kind == "interface")
        assert iface.name == "Repository"
        assert any(s.kind == "method" and s.name == "find" for s in symbols)

    @pytest.mark.asyncio
    async def test_trait(self, parser_service: TreeSitterService) -> None:
        code = "<?php\ntrait HasTimestamps {\n    public function touch(): void {}\n}\n"
        symbols, _ = await parse(parser_service, code)
        trait = next(s for s in symbols if s.kind == "trait")
        assert trait.name == "HasTimestamps"

    @pytest.mark.asyncio
    async def test_enum_with_cases(self, parser_service: TreeSitterService) -> None:
        code = """<?php
enum Suit: string {
    case Hearts = 'H';
    case Spades = 'S';
}
"""
        symbols, _ = await parse(parser_service, code)
        enum = next(s for s in symbols if s.kind == "enum")
        assert enum.name == "Suit"
        cases = {s.name for s in symbols if s.kind == "enum_case"}
        assert cases == {"Hearts", "Spades"}


class TestPhpFunctions:
    @pytest.mark.asyncio
    async def test_top_level_function(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nfunction greet(string $name): string { return $name; }\n"
        symbols, _ = await parse(parser_service, code)
        fn = next(s for s in symbols if s.kind == "function")
        assert fn.name == "greet"
        assert fn.scope is None
        assert fn.signature == "greet(string $name): string"


class TestPhpNamespaces:
    @pytest.mark.asyncio
    async def test_namespace_in_qualified_name(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nnamespace App\\Models;\nclass User {}\n"
        symbols, _ = await parse(parser_service, code)
        cls = next(s for s in symbols if s.kind == "class")
        assert cls.name == "User"
        assert cls.qualified_name == "App\\Models\\User"

    @pytest.mark.asyncio
    async def test_braced_namespace(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nnamespace App {\n    class Service {}\n}\n"
        symbols, _ = await parse(parser_service, code)
        cls = next(s for s in symbols if s.kind == "class")
        assert cls.qualified_name == "App\\Service"


class TestPhpReferences:
    @pytest.mark.asyncio
    async def test_extends_is_inheritance(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nclass Dog extends Animal {}\n"
        _, refs = await parse(parser_service, code)
        inh = [r for r in refs if r.reference_type == "inheritance"]
        assert any(r.reference_text == "Animal" for r in inh)

    @pytest.mark.asyncio
    async def test_implements_is_implementation(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nclass User implements Repository, Arrayable {}\n"
        _, refs = await parse(parser_service, code)
        impls = {r.reference_text for r in refs if r.reference_type == "implementation"}
        assert impls == {"Repository", "Arrayable"}

    @pytest.mark.asyncio
    async def test_trait_use(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nclass User {\n    use HasTimestamps, Sluggable;\n}\n"
        _, refs = await parse(parser_service, code)
        traits = {r.reference_text for r in refs if r.reference_type == "trait_use"}
        assert traits == {"HasTimestamps", "Sluggable"}

    @pytest.mark.asyncio
    async def test_namespace_use_is_import(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nuse App\\Contracts\\Repository;\nuse App\\Baz as Qux;\n"
        _, refs = await parse(parser_service, code)
        imports = {r.reference_text for r in refs if r.reference_type == "import"}
        assert "Repository" in imports
        assert "Baz" in imports

    @pytest.mark.asyncio
    async def test_new_is_instantiation(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nfunction f() { $x = new UserRepository(); }\n"
        _, refs = await parse(parser_service, code)
        assert any(
            r.reference_type == "instantiation" and r.reference_text == "UserRepository"
            for r in refs
        )

    @pytest.mark.asyncio
    async def test_new_self_static_parent_not_instantiation(
        self, parser_service: TreeSitterService
    ) -> None:
        """`new self()`/`new static()`/`new parent()` name pseudo-classes and
        must not emit dangling instantiation refs."""
        code = """<?php
class Factory {
    public function a() { return new static(); }
    public function b() { return new self(); }
    public function c() { return new parent(); }
}
"""
        _, refs = await parse(parser_service, code)
        inst = {r.reference_text for r in refs if r.reference_type == "instantiation"}
        assert not (inst & {"static", "self", "parent"})

    @pytest.mark.asyncio
    async def test_function_call(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nfunction f() { helper_fn(1); }\n"
        _, refs = await parse(parser_service, code)
        assert any(
            r.reference_type == "call" and r.reference_text == "helper_fn" for r in refs
        )

    @pytest.mark.asyncio
    async def test_builtin_call_is_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nfunction f() { $n = strlen('abc'); count([]); }\n"
        _, refs = await parse(parser_service, code)
        call_texts = {r.reference_text for r in refs if r.reference_type == "call"}
        assert "strlen" not in call_texts
        assert "count" not in call_texts

    @pytest.mark.asyncio
    async def test_mixed_case_builtin_call_is_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """PHP function names are case-insensitive; non-canonical casing of a
        built-in must still be filtered."""
        code = "<?php\nfunction f() { Strlen('a'); COUNT([]); Array_map('x', []); }\n"
        _, refs = await parse(parser_service, code)
        call_texts = {r.reference_text for r in refs if r.reference_type == "call"}
        assert not (call_texts & {"Strlen", "COUNT", "Array_map"})

    @pytest.mark.asyncio
    async def test_user_function_shadowing_builtin_is_kept(
        self, parser_service: TreeSitterService
    ) -> None:
        """A same-file user function whose name collides with a builtin must
        keep its call references — the builtin filter only applies to
        unqualified, unshadowed names."""
        code = """<?php
namespace App;
function count($x) { return 0; }
function caller() { count([1, 2]); }
"""
        _, refs = await parse(parser_service, code)
        assert any(
            r.reference_type == "call" and r.reference_text == "count" for r in refs
        )

    @pytest.mark.asyncio
    async def test_qualified_call_not_filtered_as_builtin(
        self, parser_service: TreeSitterService
    ) -> None:
        """A namespace-qualified call (App\\count()) is a user function even if
        the last segment collides with a builtin — must not be filtered."""
        code = "<?php\nfunction f() { \\App\\count([1]); }\n"
        _, refs = await parse(parser_service, code)
        assert any(
            r.reference_type == "call" and r.reference_text == "count" for r in refs
        )

    @pytest.mark.asyncio
    async def test_method_call(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nfunction f($repo) { $repo->save($x); }\n"
        _, refs = await parse(parser_service, code)
        assert any(
            r.reference_type == "call" and r.reference_text == "save" for r in refs
        )

    @pytest.mark.asyncio
    async def test_nullsafe_method_call(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nfunction f($repo) { $repo?->save($x); }\n"
        _, refs = await parse(parser_service, code)
        assert any(
            r.reference_type == "call" and r.reference_text == "save" for r in refs
        )

    @pytest.mark.asyncio
    async def test_static_call(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nfunction f() { Log::info('hi'); }\n"
        _, refs = await parse(parser_service, code)
        assert any(
            r.reference_type == "call" and r.reference_text == "info" for r in refs
        )
        # The class part is a static usage reference.
        assert any(
            r.reference_type == "usage" and r.reference_text == "Log" for r in refs
        )

    @pytest.mark.asyncio
    async def test_relative_scope_not_emitted_as_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nclass Foo {\n    public function f() { self::boot(); }\n}\n"
        _, refs = await parse(parser_service, code)
        usages = {r.reference_text for r in refs if r.reference_type == "usage"}
        assert "self" not in usages

    @pytest.mark.asyncio
    async def test_type_annotation(self, parser_service: TreeSitterService) -> None:
        code = "<?php\nfunction f(UserRepo $r): ?Model { return null; }\n"
        _, refs = await parse(parser_service, code)
        type_refs = {
            r.reference_text for r in refs if r.reference_type == "type_annotation"
        }
        assert "UserRepo" in type_refs
        assert "Model" in type_refs

    @pytest.mark.asyncio
    async def test_primitive_type_not_annotated(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\nfunction f(int $x, string $y): void {}\n"
        _, refs = await parse(parser_service, code)
        type_refs = {
            r.reference_text for r in refs if r.reference_type == "type_annotation"
        }
        assert not (type_refs & {"int", "string", "void"})

    @pytest.mark.asyncio
    async def test_capitalized_primitive_type_not_annotated(
        self, parser_service: TreeSitterService
    ) -> None:
        """PHP type names are case-insensitive; capitalized scalar hints parse
        as named_type and must still be filtered (no dangling refs)."""
        code = "<?php\nfunction f(Array $x): Int {}\nfunction g(): Void {}\n"
        _, refs = await parse(parser_service, code)
        type_refs = {
            r.reference_text for r in refs if r.reference_type == "type_annotation"
        }
        assert not (type_refs & {"Array", "Int", "Void"})

    @pytest.mark.asyncio
    async def test_reference_scope_is_namespace_qualified(
        self, parser_service: TreeSitterService
    ) -> None:
        """A call ref inside a namespaced class must carry the same
        namespace-qualified scope the symbol pass produces for its members."""
        code = """<?php
namespace App\\Models;
class User {
    public function save(): void { helper_fn(); }
}
"""
        symbols, refs = await parse(parser_service, code)
        method = next(s for s in symbols if s.kind == "method")
        assert method.scope == "App\\Models\\User"
        call = next(
            r
            for r in refs
            if r.reference_type == "call" and r.reference_text == "helper_fn"
        )
        assert call.scope == "App\\Models\\User::save"

    @pytest.mark.asyncio
    async def test_top_level_function_reference_scope_is_qualified(
        self, parser_service: TreeSitterService
    ) -> None:
        """A call inside a namespaced *top-level* function must carry the
        namespace-qualified scope matching the function symbol's qualified_name
        (not the bare function name)."""
        code = """<?php
namespace App;
function greet() { helper(); }
"""
        symbols, refs = await parse(parser_service, code)
        fn = next(s for s in symbols if s.kind == "function")
        assert fn.qualified_name == "App\\greet"
        call = next(
            r
            for r in refs
            if r.reference_type == "call" and r.reference_text == "helper"
        )
        assert call.scope == "App\\greet"

    @pytest.mark.asyncio
    async def test_builtin_shadow_is_namespace_scoped(
        self, parser_service: TreeSitterService
    ) -> None:
        """A user function shadows a builtin only within its own namespace: a
        call to the same bare name in a different namespace resolves to the
        builtin and must be filtered."""
        code = """<?php
namespace A;
function count($x) { return 0; }
function inA() { count([1]); }

namespace B;
function inB() { count([2]); }
"""
        _, refs = await parse(parser_service, code)
        count_calls = [
            r
            for r in refs
            if r.reference_type == "call" and r.reference_text == "count"
        ]
        # Kept in namespace A (A\count exists), filtered in namespace B.
        scopes = {r.scope for r in count_calls}
        assert scopes == {"A\\inA"}


class TestPhpComments:
    @pytest.mark.asyncio
    async def test_docblock(self, parser_service: TreeSitterService) -> None:
        code = "<?php\n/**\n * A docblock.\n */\nclass Foo {}\n"
        comments = await parser_service.extract_comments(code, "php", "test.php")
        docs = [c for c in comments if c.content_type == "docstring"]
        assert any("A docblock." in c.content for c in docs)

    @pytest.mark.asyncio
    async def test_line_and_hash_comments(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "<?php\n// slash comment\n# hash comment\n"
        comments = await parser_service.extract_comments(code, "php", "test.php")
        singles = {
            c.content for c in comments if c.content_type == "single_line_comment"
        }
        assert "slash comment" in singles
        assert "hash comment" in singles

    @pytest.mark.asyncio
    async def test_block_comment(self, parser_service: TreeSitterService) -> None:
        code = "<?php\n/* a block */\nclass Foo {}\n"
        comments = await parser_service.extract_comments(code, "php", "test.php")
        blocks = [c for c in comments if c.content_type == "block_comment"]
        assert any("a block" in c.content for c in blocks)


class TestPhpRobustness:
    @pytest.mark.asyncio
    async def test_empty_file(self, parser_service: TreeSitterService) -> None:
        symbols, refs = await parse(parser_service, "<?php\n")
        assert symbols == []
        assert refs == []

    @pytest.mark.asyncio
    async def test_html_mixed_with_php(self, parser_service: TreeSitterService) -> None:
        code = "<html><body><?php class Widget {} ?></body></html>\n"
        symbols, _ = await parse(parser_service, code)
        assert any(s.kind == "class" and s.name == "Widget" for s in symbols)
