"""Tests for C++ language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestCppSupport:
    """Tests for C++ language support in TreeSitterService."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    def test_supports_cpp(self, parser_service: TreeSitterService) -> None:
        """Test that C++ is supported."""
        assert parser_service.supports_language("cpp")
        assert parser_service.supports_language("Cpp")
        assert parser_service.supports_language("CPP")


class TestCppNamespaces:
    """Tests for C++ namespace parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_namespace(self, parser_service: TreeSitterService) -> None:
        """Test parsing a namespace with a function."""
        code = """
namespace MyNamespace {
    void helper() {}
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="example.cpp"
        )

        ns_symbols = [s for s in symbols if s["kind"] == "namespace"]
        assert len(ns_symbols) == 1
        assert ns_symbols[0]["name"] == "MyNamespace"

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["name"] == "helper"
        assert func_symbols[0]["scope"] == "MyNamespace"

    @pytest.mark.asyncio
    async def test_parse_nested_namespaces(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing nested namespaces."""
        code = """
namespace Outer {
    namespace Inner {
        void nested_func() {}
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="example.cpp"
        )

        ns_symbols = [s for s in symbols if s["kind"] == "namespace"]
        ns_names = [s["name"] for s in ns_symbols]
        assert "Outer" in ns_names
        assert "Inner" in ns_names

        inner_ns = next(s for s in ns_symbols if s["name"] == "Inner")
        assert inner_ns["scope"] == "Outer"

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["name"] == "nested_func"
        assert func_symbols[0]["scope"] == "Outer.Inner"


class TestCppClasses:
    """Tests for C++ class parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_class(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple class with fields and a method."""
        code = """
class Person {
public:
    int age;
    void greet() {}
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="person.cpp"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["name"] == "Person"

        field_symbols = [s for s in symbols if s["kind"] == "field"]
        field_names = [s["name"] for s in field_symbols]
        assert "age" in field_names

        method_symbols = [s for s in symbols if s["kind"] == "method"]
        assert any(
            m["name"] == "greet" and m["scope"] == "Person" for m in method_symbols
        )

    @pytest.mark.asyncio
    async def test_parse_class_with_inheritance(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a class with base class inheritance."""
        code = """
class Base {
public:
    void base_method() {}
};

class Derived : public Base {
public:
    void derived_method() {}
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="inherit.cpp"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        class_names = [s["name"] for s in class_symbols]
        assert "Base" in class_names
        assert "Derived" in class_names

        # Base class should appear as a type reference
        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        assert "Base" in type_texts


class TestCppStructs:
    """Tests for C++ struct parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_struct(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple struct with fields."""
        code = """
struct Point {
    double x;
    double y;
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="point.cpp"
        )

        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0]["name"] == "Point"

        fields = [
            s for s in symbols if s["kind"] == "field" and s.get("scope") == "Point"
        ]
        field_names = [s["name"] for s in fields]
        assert "x" in field_names
        assert "y" in field_names


class TestCppFunctions:
    """Tests for C++ function parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a simple free function."""
        code = """
void hello() {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["name"] == "hello"

    @pytest.mark.asyncio
    async def test_parse_function_with_params(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a function with parameters and return type."""
        code = """
int add(int a, int b) {
    return a + b;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="math.cpp"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["name"] == "add"
        assert "signature" in func_symbols[0]
        assert "add" in func_symbols[0]["signature"]

    @pytest.mark.asyncio
    async def test_parse_multiple_functions(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing multiple free functions."""
        code = """
void foo() {}
int bar(int x) { return x; }
double baz(double a, double b) { return a + b; }
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="funcs.cpp"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        func_names = [s["name"] for s in func_symbols]
        assert "foo" in func_names
        assert "bar" in func_names
        assert "baz" in func_names


class TestCppMethods:
    """Tests for C++ method parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_inline_method(self, parser_service: TreeSitterService) -> None:
        """Test parsing an inline method defined inside a class body."""
        code = """
class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="calc.cpp"
        )

        method_symbols = [s for s in symbols if s["kind"] == "method"]
        assert len(method_symbols) == 1
        assert method_symbols[0]["name"] == "add"
        assert method_symbols[0]["scope"] == "Calculator"
        assert "signature" in method_symbols[0]

    @pytest.mark.asyncio
    async def test_parse_constructor_destructor(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing constructors and destructors."""
        code = """
class Resource {
public:
    Resource() {}
    ~Resource() {}
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="resource.cpp"
        )

        method_symbols = [s for s in symbols if s["kind"] == "method"]
        method_names = [s["name"] for s in method_symbols]
        assert "Resource" in method_names
        assert "~Resource" in method_names

        for m in method_symbols:
            assert m["scope"] == "Resource"

    @pytest.mark.asyncio
    async def test_parse_multiple_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing multiple methods in a class."""
        code = """
class Container {
public:
    void push(int val) {}
    int pop() { return 0; }
    int size() { return 0; }
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="container.cpp"
        )

        method_symbols = [s for s in symbols if s["kind"] == "method"]
        method_names = [s["name"] for s in method_symbols]
        assert "push" in method_names
        assert "pop" in method_names
        assert "size" in method_names

        for m in method_symbols:
            assert m["scope"] == "Container"


class TestCppFields:
    """Tests for C++ field (data member) parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_class_fields(self, parser_service: TreeSitterService) -> None:
        """Test parsing data members of a class."""
        code = """
class Config {
    int timeout;
    bool enabled;
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="config.cpp"
        )

        fields = [
            s for s in symbols if s["kind"] == "field" and s.get("scope") == "Config"
        ]
        field_names = [s["name"] for s in fields]
        assert "timeout" in field_names
        assert "enabled" in field_names


class TestCppEnums:
    """Tests for C++ enum parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_enum(self, parser_service: TreeSitterService) -> None:
        """Test parsing a regular enum."""
        code = """
enum Color {
    Red,
    Green,
    Blue
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="color.cpp"
        )

        enum_symbols = [s for s in symbols if s["kind"] == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0]["name"] == "Color"

        enum_values = [s for s in symbols if s["kind"] == "enum_value"]
        value_names = [s["name"] for s in enum_values]
        assert "Red" in value_names
        assert "Green" in value_names
        assert "Blue" in value_names

    @pytest.mark.asyncio
    async def test_parse_enum_class(self, parser_service: TreeSitterService) -> None:
        """Test parsing a scoped enum (enum class)."""
        code = """
enum class Status {
    Active,
    Inactive,
    Pending
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="status.cpp"
        )

        enum_symbols = [s for s in symbols if s["kind"] == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0]["name"] == "Status"

        enum_values = [s for s in symbols if s["kind"] == "enum_value"]
        value_names = [s["name"] for s in enum_values]
        assert "Active" in value_names
        assert "Inactive" in value_names
        assert "Pending" in value_names


class TestCppTypes:
    """Tests for C++ typedef and using alias parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_typedef(self, parser_service: TreeSitterService) -> None:
        """Test parsing a typedef declaration."""
        code = """
typedef unsigned long ulong;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="types.cpp"
        )

        typedef_symbols = [s for s in symbols if s["kind"] == "typedef"]
        assert any(s["name"] == "ulong" for s in typedef_symbols)

    @pytest.mark.asyncio
    async def test_parse_using_alias(self, parser_service: TreeSitterService) -> None:
        """Test parsing a using alias declaration."""
        code = """
using StringVec = int;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="types.cpp"
        )

        type_symbols = [s for s in symbols if s["kind"] == "type"]
        assert any(s["name"] == "StringVec" for s in type_symbols)


class TestCppTemplates:
    """Tests for C++ template parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_template_class(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a template class."""
        code = """
template<typename T>
class Container {
public:
    void add(T item) {}
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="container.cpp"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["name"] == "Container"

        method_symbols = [s for s in symbols if s["kind"] == "method"]
        assert any(
            m["name"] == "add" and m["scope"] == "Container" for m in method_symbols
        )

    @pytest.mark.asyncio
    async def test_parse_template_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a template function."""
        code = """
template<typename T>
T maximum(T a, T b) {
    return (a > b) ? a : b;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="util.cpp"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        assert any(s["name"] == "maximum" for s in func_symbols)


class TestCppReferences:
    """Tests for C++ reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_function_calls(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing function call references."""
        code = """
void helper() {}

void process() {
    helper();
    doWork();
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        assert "helper" in call_texts
        assert "doWork" in call_texts

    @pytest.mark.asyncio
    async def test_parse_include_directives(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing #include directives."""
        code = """
#include <iostream>
#include "myheader.h"

void main() {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )

        include_refs = [r for r in references if r["type"] == "include"]
        include_texts = [r["text"] for r in include_refs]
        assert "iostream" in include_texts
        assert "myheader.h" in include_texts

    @pytest.mark.asyncio
    async def test_parse_type_usage(self, parser_service: TreeSitterService) -> None:
        """Test parsing type usage references."""
        code = """
class Widget {};

void process(Widget w) {
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="proc.cpp"
        )

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        assert "Widget" in type_texts

    @pytest.mark.asyncio
    async def test_builtin_calls_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that builtin calls are filtered from references."""
        code = """
void process() {
    int x = sizeof(int);
    customFunc();
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        # sizeof is a builtin, should be filtered
        assert "sizeof" not in call_texts
        # Custom function should remain
        assert "customFunc" in call_texts

    @pytest.mark.asyncio
    async def test_primitive_types_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that primitive types are filtered from type references."""
        code = """
void compute(int a, double b) {
    bool flag = true;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="compute.cpp"
        )

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        assert "int" not in type_texts
        assert "double" not in type_texts
        assert "bool" not in type_texts


class TestCppComments:
    """Tests for C++ comment extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_single_line_comment(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing single-line comments."""
        code = """
// This is a comment
void foo() {}
"""
        comments = await parser_service.extract_comments(
            content=code, language="cpp", file_path="example.cpp"
        )

        assert len(comments) >= 1
        assert any(c["content"] == "This is a comment" for c in comments)
        assert any(c["content_type"] == "single_line_comment" for c in comments)

    @pytest.mark.asyncio
    async def test_parse_block_comment(self, parser_service: TreeSitterService) -> None:
        """Test parsing block comments."""
        code = """
/* Block comment */
void foo() {}
"""
        comments = await parser_service.extract_comments(
            content=code, language="cpp", file_path="example.cpp"
        )

        assert len(comments) >= 1
        assert any(c["content"] == "Block comment" for c in comments)
        assert any(c["content_type"] == "block_comment" for c in comments)


class TestCppComplexStructures:
    """Tests for complex C++ structures."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_full_cpp_file(self, parser_service: TreeSitterService) -> None:
        """Test parsing a complete C++ file with multiple constructs."""
        code = """
#include <iostream>

namespace App {

const int MAX_SIZE = 100;

enum class LogLevel {
    Debug,
    Info,
    Error
};

class Logger {
public:
    void log(int level) {}
    int count;
};

void initialize() {}

}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="app.cpp"
        )

        # Namespace
        ns = [s for s in symbols if s["kind"] == "namespace"]
        assert any(s["name"] == "App" for s in ns)

        # Constant
        consts = [s for s in symbols if s["kind"] == "constant"]
        assert any(c["name"] == "MAX_SIZE" for c in consts)

        # Enum
        enums = [s for s in symbols if s["kind"] == "enum"]
        assert any(e["name"] == "LogLevel" for e in enums)

        # Enum values
        enum_vals = [s for s in symbols if s["kind"] == "enum_value"]
        ev_names = [s["name"] for s in enum_vals]
        assert "Debug" in ev_names
        assert "Info" in ev_names
        assert "Error" in ev_names

        # Class
        classes = [s for s in symbols if s["kind"] == "class"]
        assert any(c["name"] == "Logger" for c in classes)

        # Method
        methods = [s for s in symbols if s["kind"] == "method"]
        assert any(m["name"] == "log" and m["scope"] == "App.Logger" for m in methods)

        # Field
        fields = [s for s in symbols if s["kind"] == "field"]
        assert any(
            f["name"] == "count" and f.get("scope") == "App.Logger" for f in fields
        )

        # Function
        funcs = [s for s in symbols if s["kind"] == "function"]
        assert any(f["name"] == "initialize" and f.get("scope") == "App" for f in funcs)

        # Include reference
        include_refs = [r for r in references if r["type"] == "include"]
        include_texts = [r["text"] for r in include_refs]
        assert "iostream" in include_texts

    @pytest.mark.asyncio
    async def test_parse_constexpr_variable(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing constexpr variables as constants."""
        code = """
constexpr int BUFFER_SIZE = 4096;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="config.cpp"
        )

        const_symbols = [s for s in symbols if s["kind"] == "constant"]
        assert any(s["name"] == "BUFFER_SIZE" for s in const_symbols)

    @pytest.mark.asyncio
    async def test_parse_define_macro(self, parser_service: TreeSitterService) -> None:
        """Test parsing #define macros as constants."""
        code = """
#define MAX_RETRIES 3
#define PI 3.14159
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="config.cpp"
        )

        const_symbols = [s for s in symbols if s["kind"] == "constant"]
        const_names = [s["name"] for s in const_symbols]
        assert "MAX_RETRIES" in const_names
        assert "PI" in const_names


class TestCppEdgeCases:
    """Tests for edge cases in C++ parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_empty_cpp_file(self, parser_service: TreeSitterService) -> None:
        """Test parsing an empty C++ file."""
        code = ""
        symbols, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="empty.cpp"
        )

        assert isinstance(symbols, list)
        assert isinstance(references, list)

    @pytest.mark.asyncio
    async def test_malformed_cpp_code(self, parser_service: TreeSitterService) -> None:
        """Test that malformed C++ code doesn't crash the parser."""
        code = """
class Broken {
    void method(
    int x = ;
};
"""
        # Should not raise an exception
        symbols, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="broken.cpp"
        )

        assert isinstance(symbols, list)
        assert isinstance(references, list)

    @pytest.mark.asyncio
    async def test_function_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that function symbol start_line points to the function name."""
        code = """void MyFunction() {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )

        func_symbols = [s for s in symbols if s["name"] == "MyFunction"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["start_line"] == 1
