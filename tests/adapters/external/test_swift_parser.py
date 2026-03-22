"""Tests for Swift language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestSwiftSupport:
    """Tests for Swift language support in TreeSitterService."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    def test_supports_swift(self, parser_service: TreeSitterService) -> None:
        assert parser_service.supports_language("swift")
        assert parser_service.supports_language("Swift")
        assert parser_service.supports_language("SWIFT")

    def test_swift_extension_registered(
        self, parser_service: TreeSitterService
    ) -> None:
        assert ".swift" in parser_service.SUPPORTED_LANGUAGES.get("swift", [])


class TestSwiftClasses:
    """Tests for Swift class declaration parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_class(self, parser_service: TreeSitterService) -> None:
        code = """
class Vehicle {
    var speed: Double = 0
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "Vehicle"

    @pytest.mark.asyncio
    async def test_class_with_protocol_conformance(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
class Vehicle: Identifiable {
    let id: UUID = UUID()
}
"""
        symbols, refs = await parser_service.parse_file(code, "swift", "test.swift")
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "Vehicle"

        conformance_refs = [
            r for r in refs if r.reference_type == "protocol_conformance"
        ]
        assert any(r.reference_text == "Identifiable" for r in conformance_refs)

    @pytest.mark.asyncio
    async def test_class_with_properties(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
class Car {
    let model: String
    var speed: Double = 0
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        props = [s for s in symbols if s.kind == "property"]
        prop_names = {s.name for s in props}
        assert "model" in prop_names
        assert "speed" in prop_names

    @pytest.mark.asyncio
    async def test_class_property_scoped_to_class(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
class Car {
    var speed: Double = 0
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        speed = next(s for s in symbols if s.name == "speed")
        assert speed.scope == "Car"
        assert speed.qualified_name == "Car.speed"

    @pytest.mark.asyncio
    async def test_class_with_methods(self, parser_service: TreeSitterService) -> None:
        code = """
class Car {
    func accelerate() {}
    func brake() {}
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        methods = [s for s in symbols if s.kind == "method"]
        method_names = {s.name for s in methods}
        assert "accelerate" in method_names
        assert "brake" in method_names
        for m in methods:
            assert m.scope == "Car"

    @pytest.mark.asyncio
    async def test_class_with_init(self, parser_service: TreeSitterService) -> None:
        code = """
class Car {
    let model: String
    init(model: String) {
        self.model = model
    }
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        inits = [s for s in symbols if s.kind == "init"]
        assert len(inits) == 1
        assert inits[0].scope == "Car"

    @pytest.mark.asyncio
    async def test_method_has_signature(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
class Car {
    func drive(to destination: String) -> Bool {
        return true
    }
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].signature is not None
        assert "drive" in methods[0].signature


class TestSwiftStructs:
    """Tests for Swift struct declaration parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_struct(self, parser_service: TreeSitterService) -> None:
        code = """
struct Point {
    var x: Double
    var y: Double
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        structs = [s for s in symbols if s.kind == "struct"]
        assert len(structs) == 1
        assert structs[0].name == "Point"

    @pytest.mark.asyncio
    async def test_struct_with_method(self, parser_service: TreeSitterService) -> None:
        code = """
struct Point {
    var x: Double
    var y: Double
    func distanceTo(_ other: Point) -> Double {
        return 0.0
    }
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].name == "distanceTo"
        assert methods[0].scope == "Point"

    @pytest.mark.asyncio
    async def test_struct_fields_scoped(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
struct Point {
    var x: Double
    var y: Double
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        props = [s for s in symbols if s.kind == "property"]
        for prop in props:
            assert prop.scope == "Point"


class TestSwiftEnums:
    """Tests for Swift enum declaration parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_enum(self, parser_service: TreeSitterService) -> None:
        code = """
enum Direction {
    case north
    case south
    case east
    case west
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        enums = [s for s in symbols if s.kind == "enum"]
        assert len(enums) == 1
        assert enums[0].name == "Direction"

    @pytest.mark.asyncio
    async def test_enum_cases_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
enum Direction {
    case north
    case south
    case east
    case west
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        cases = [s for s in symbols if s.kind == "enum_case"]
        case_names = {s.name for s in cases}
        assert case_names == {"north", "south", "east", "west"}

    @pytest.mark.asyncio
    async def test_enum_cases_scoped_to_enum(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
enum Color {
    case red
    case green
    case blue
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        cases = [s for s in symbols if s.kind == "enum_case"]
        for case in cases:
            assert case.scope == "Color"

    @pytest.mark.asyncio
    async def test_enum_with_raw_type_conformance(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
enum Direction: String {
    case north = "N"
    case south = "S"
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        enums = [s for s in symbols if s.kind == "enum"]
        assert len(enums) == 1
        cases = [s for s in symbols if s.kind == "enum_case"]
        assert len(cases) == 2

    @pytest.mark.asyncio
    async def test_enum_with_method(self, parser_service: TreeSitterService) -> None:
        code = """
enum Direction {
    case north
    func opposite() -> Direction {
        return .north
    }
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].name == "opposite"


class TestSwiftProtocols:
    """Tests for Swift protocol declaration parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_protocol(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
protocol Drawable {
    func draw() -> Void
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        protocols = [s for s in symbols if s.kind == "protocol"]
        assert len(protocols) == 1
        assert protocols[0].name == "Drawable"

    @pytest.mark.asyncio
    async def test_protocol_function_requirements(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
protocol Drawable {
    func draw() -> Void
    func resize(by factor: Double)
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        methods = [s for s in symbols if s.kind == "method"]
        method_names = {s.name for s in methods}
        assert "draw" in method_names
        assert "resize" in method_names

    @pytest.mark.asyncio
    async def test_protocol_property_requirements(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
protocol Vehicle {
    var speed: Double { get set }
    var name: String { get }
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        props = [s for s in symbols if s.kind == "property"]
        prop_names = {s.name for s in props}
        assert "speed" in prop_names
        assert "name" in prop_names

    @pytest.mark.asyncio
    async def test_protocol_inheritance(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
protocol AnimatableDrawable: Drawable {
    func animate()
}
"""
        symbols, refs = await parser_service.parse_file(code, "swift", "test.swift")
        protocols = [s for s in symbols if s.kind == "protocol"]
        assert len(protocols) == 1

        conformance_refs = [
            r for r in refs if r.reference_type == "protocol_conformance"
        ]
        assert any(r.reference_text == "Drawable" for r in conformance_refs)


class TestSwiftExtensions:
    """Tests for Swift extension declaration parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_extension(self, parser_service: TreeSitterService) -> None:
        code = """
extension Vehicle {
    func describe() -> String {
        return "vehicle"
    }
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        extensions = [s for s in symbols if s.kind == "extension"]
        assert len(extensions) == 1
        assert extensions[0].name == "Vehicle"

    @pytest.mark.asyncio
    async def test_extension_methods_scoped(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
extension Vehicle {
    func describe() -> String { return "" }
    func reset() {}
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 2
        for m in methods:
            assert m.scope == "Vehicle"

    @pytest.mark.asyncio
    async def test_extension_with_protocol_conformance(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
extension Vehicle: Drawable {
    func draw() -> Void {}
}
"""
        symbols, refs = await parser_service.parse_file(code, "swift", "test.swift")
        extensions = [s for s in symbols if s.kind == "extension"]
        assert len(extensions) == 1

        conformance_refs = [
            r for r in refs if r.reference_type == "protocol_conformance"
        ]
        assert any(r.reference_text == "Drawable" for r in conformance_refs)

    @pytest.mark.asyncio
    async def test_extension_qualified_name_distinct_from_class(
        self, parser_service: TreeSitterService
    ) -> None:
        """Extension qualified_name must not collide with a same-named class."""
        code = """
class Vehicle {}
extension Vehicle {
    func describe() -> String { return "" }
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        class_sym = next(s for s in symbols if s.kind == "class")
        ext_sym = next(s for s in symbols if s.kind == "extension")
        assert class_sym.qualified_name != ext_sym.qualified_name
        assert ext_sym.qualified_name is not None
        assert "<extension>" in ext_sym.qualified_name


class TestSwiftTopLevelFunctions:
    """Tests for top-level Swift function parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_top_level_function(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
func greet(_ name: String) -> String {
    return "Hello, \\(name)"
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "greet"
        assert funcs[0].scope is None

    @pytest.mark.asyncio
    async def test_top_level_function_has_signature(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
func add(a: Int, b: Int) -> Int {
    return a + b
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].signature is not None
        assert "add" in funcs[0].signature


class TestSwiftReferences:
    """Tests for Swift reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_import_references(self, parser_service: TreeSitterService) -> None:
        code = """
import Foundation
import UIKit
"""
        _, refs = await parser_service.parse_file(code, "swift", "test.swift")
        imports = [r for r in refs if r.reference_type == "import"]
        import_names = {r.reference_text for r in imports}
        assert "Foundation" in import_names
        assert "UIKit" in import_names

    @pytest.mark.asyncio
    async def test_call_references(self, parser_service: TreeSitterService) -> None:
        code = """
func main() {
    doSomething()
    processData()
}
"""
        _, refs = await parser_service.parse_file(code, "swift", "test.swift")
        calls = [r for r in refs if r.reference_type == "call"]
        call_names = {r.reference_text for r in calls}
        assert "doSomething" in call_names
        assert "processData" in call_names

    @pytest.mark.asyncio
    async def test_type_annotation_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
class Service {
    var delegate: MyDelegate
    var manager: DataManager
}
"""
        _, refs = await parser_service.parse_file(code, "swift", "test.swift")
        type_refs = [r for r in refs if r.reference_type == "type_annotation"]
        type_names = {r.reference_text for r in type_refs}
        assert "MyDelegate" in type_names
        assert "DataManager" in type_names

    @pytest.mark.asyncio
    async def test_builtin_types_not_in_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
class Config {
    var count: Int = 0
    var name: String = ""
    var flag: Bool = false
}
"""
        _, refs = await parser_service.parse_file(code, "swift", "test.swift")
        type_refs = {
            r.reference_text for r in refs if r.reference_type == "type_annotation"
        }
        # Primitive types should be filtered out
        assert "Int" not in type_refs
        assert "String" not in type_refs
        assert "Bool" not in type_refs

    @pytest.mark.asyncio
    async def test_navigation_method_call_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
func setup() {
    obj.doWork()
    delegate.handleEvent()
}
"""
        _, refs = await parser_service.parse_file(code, "swift", "test.swift")
        calls = [r for r in refs if r.reference_type == "call"]
        call_names = {r.reference_text for r in calls}
        assert "doWork" in call_names
        assert "handleEvent" in call_names


class TestSwiftComments:
    """Tests for Swift comment extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_single_line_comments(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
// This is a regular comment
class Foo {}
"""
        comments = await parser_service.extract_comments(code, "swift", "test.swift")
        assert any(
            "regular comment" in c.content
            for c in comments
            if c.content_type == "single_line_comment"
        )

    @pytest.mark.asyncio
    async def test_doc_comments(self, parser_service: TreeSitterService) -> None:
        code = """
/// A documented class
class Foo {}
"""
        comments = await parser_service.extract_comments(code, "swift", "test.swift")
        assert any(c.content_type == "docstring" for c in comments)

    @pytest.mark.asyncio
    async def test_block_comments(self, parser_service: TreeSitterService) -> None:
        code = """
/* A block comment
   spanning multiple lines */
class Foo {}
"""
        comments = await parser_service.extract_comments(code, "swift", "test.swift")
        block_comments = [c for c in comments if c.content_type == "block_comment"]
        assert len(block_comments) >= 1

    @pytest.mark.asyncio
    async def test_exclamation_doc_comment_no_leading_bang(
        self, parser_service: TreeSitterService
    ) -> None:
        """/*! ... */ doc comments must not start with a leading '!' in content."""
        code = """
/*! A HeaderDoc-style doc comment */
class Foo {}
"""
        comments = await parser_service.extract_comments(code, "swift", "test.swift")
        doc = next(c for c in comments if c.content_type == "docstring")
        assert not doc.content.startswith("!")


class TestSwiftLineNumbers:
    """Tests for correct line number reporting."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_symbol_line_numbers(self, parser_service: TreeSitterService) -> None:
        code = """class Foo {
    var x: Int = 0
    func bar() {}
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        foo = next(s for s in symbols if s.name == "Foo")
        assert foo.start_line == 1

        bar = next(s for s in symbols if s.name == "bar")
        assert bar.start_line == 3

    @pytest.mark.asyncio
    async def test_reference_line_numbers(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """import Foundation
import UIKit
"""
        _, refs = await parser_service.parse_file(code, "swift", "test.swift")
        imports = {r.reference_text: r for r in refs if r.reference_type == "import"}
        assert imports["Foundation"].source_line == 1
        assert imports["UIKit"].source_line == 2


class TestSwiftErrorRecovery:
    """Tests for graceful handling of syntactically invalid Swift files."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_protocol_with_invalid_member_still_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regression: protocol body with invalid syntax should still yield
        the protocol symbol (tree-sitter wraps it in an ERROR node)."""
        code = """import Foundation

protocol LLMPort {
    func complete(systemPrompt: String, userMessage: String) async throws -> String
    func isConfigured: Bool
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        protocols = [s for s in symbols if s.kind == "protocol"]
        assert len(protocols) == 1
        assert protocols[0].name == "LLMPort"

    @pytest.mark.asyncio
    async def test_protocol_members_inside_error_node_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regression: valid protocol_function_declaration nodes inside an ERROR
        node (caused by an invalid sibling) should still be extracted."""
        code = """protocol LLMPort {
    func complete(systemPrompt: String, userMessage: String) async throws -> String
    func isConfigured: Bool
}
"""
        symbols, _ = await parser_service.parse_file(code, "swift", "test.swift")
        methods = [s for s in symbols if s.kind == "method"]
        assert any(s.name == "complete" for s in methods)
