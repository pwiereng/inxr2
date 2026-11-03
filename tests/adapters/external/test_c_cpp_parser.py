"""Tests for unified C/C++ language parser using Tree-sitter."""

import re

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService
from inxr2.application.ports.services.parser_service import (
    ParsedReference,
    ParsedSymbol,
)

# ── Support ─────────────────────────────────────────────────────────


class TestLanguageSupport:
    """Tests that C and C++ are both supported."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    def test_supports_c(self, parser_service: TreeSitterService) -> None:
        assert parser_service.supports_language("c")
        assert parser_service.supports_language("C")

    def test_supports_cpp(self, parser_service: TreeSitterService) -> None:
        assert parser_service.supports_language("cpp")
        assert parser_service.supports_language("Cpp")
        assert parser_service.supports_language("CPP")


# ── C-mode tests ────────────────────────────────────────────────────


class TestCFunctions:
    """Tests for C function parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_function(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
int add(int a, int b) {
    return a + b;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        func_symbols = [s for s in symbols if s.name == "add"]
        assert len(func_symbols) == 1
        assert func_symbols[0].kind == "function"

    @pytest.mark.asyncio
    async def test_parse_void_function(self, parser_service: TreeSitterService) -> None:
        code = """
void print_hello(void) {
    printf("Hello\\n");
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        func_symbols = [s for s in symbols if s.name == "print_hello"]
        assert len(func_symbols) == 1
        assert func_symbols[0].kind == "function"

    @pytest.mark.asyncio
    async def test_parse_function_with_pointer_return(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
char* get_message(void) {
    return "Hello";
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        func_symbols = [s for s in symbols if s.name == "get_message"]
        assert len(func_symbols) == 1
        assert func_symbols[0].kind == "function"

    @pytest.mark.asyncio
    async def test_parse_function_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
int calculate(int x, int y);
void process(void);
char* get_name(const char* prefix);
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.h"
        )
        func_names = [s.name for s in symbols if s.kind == "function"]
        assert "calculate" in func_names
        assert "process" in func_names
        assert "get_name" in func_names

    @pytest.mark.asyncio
    async def test_function_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Function symbol start_line should point to the name, not the return type."""
        code = """void
my_function(int arg) {
    return;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        func_symbols = [s for s in symbols if s.name == "my_function"]
        assert len(func_symbols) == 1
        assert func_symbols[0].start_line == 2


class TestCStructs:
    """Tests for C struct parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_struct(self, parser_service: TreeSitterService) -> None:
        code = """
struct Point {
    int x;
    int y;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0].name == "Point"

        fields = [s for s in symbols if s.kind == "struct_field"]
        field_names = [s.name for s in fields]
        assert "x" in field_names
        assert "y" in field_names

    @pytest.mark.asyncio
    async def test_parse_struct_with_pointer_fields(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
struct Node {
    int value;
    struct Node* next;
    char* name;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0].name == "Node"

        fields = [s for s in symbols if s.kind == "struct_field"]
        field_names = [s.name for s in fields]
        assert "value" in field_names
        assert "next" in field_names
        assert "name" in field_names

    @pytest.mark.asyncio
    async def test_parse_struct_with_array_fields(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
struct Buffer {
    char data[256];
    int size;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        fields = [s for s in symbols if s.kind == "struct_field"]
        field_names = [s.name for s in fields]
        assert "data" in field_names
        assert "size" in field_names

    @pytest.mark.asyncio
    async def test_struct_field_scope(self, parser_service: TreeSitterService) -> None:
        code = """
struct Person {
    char* name;
    int age;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        fields = [s for s in symbols if s.kind == "struct_field"]
        for field in fields:
            assert field.scope == "Person"
            assert field.qualified_name is not None and field.qualified_name.startswith(
                "Person."
            )


class TestCUnions:
    """Tests for C union parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_union(self, parser_service: TreeSitterService) -> None:
        code = """
union Data {
    int i;
    float f;
    char c;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        union_symbols = [s for s in symbols if s.kind == "union"]
        assert len(union_symbols) == 1
        assert union_symbols[0].name == "Data"

        fields = [s for s in symbols if s.kind == "union_field"]
        field_names = [s.name for s in fields]
        assert "i" in field_names
        assert "f" in field_names
        assert "c" in field_names

    @pytest.mark.asyncio
    async def test_union_field_scope(self, parser_service: TreeSitterService) -> None:
        code = """
union Value {
    int as_int;
    double as_double;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        fields = [s for s in symbols if s.kind == "union_field"]
        for field in fields:
            assert field.scope == "Value"


class TestCEnums:
    """Tests for C enum parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_enum(self, parser_service: TreeSitterService) -> None:
        code = """
enum Color {
    RED,
    GREEN,
    BLUE
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        enum_symbols = [s for s in symbols if s.kind == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0].name == "Color"

        values = [s for s in symbols if s.kind == "enum_value"]
        value_names = [s.name for s in values]
        assert "RED" in value_names
        assert "GREEN" in value_names
        assert "BLUE" in value_names

    @pytest.mark.asyncio
    async def test_parse_enum_with_values(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
enum Status {
    OK = 0,
    ERROR = -1,
    PENDING = 1
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        values = [s for s in symbols if s.kind == "enum_value"]
        value_names = [s.name for s in values]
        assert "OK" in value_names
        assert "ERROR" in value_names
        assert "PENDING" in value_names

    @pytest.mark.asyncio
    async def test_enum_value_scope(self, parser_service: TreeSitterService) -> None:
        code = """
enum Direction {
    NORTH,
    SOUTH
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        values = [s for s in symbols if s.kind == "enum_value"]
        for value in values:
            assert value.scope == "Direction"


class TestCTypedefs:
    """Tests for C typedef parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_typedef(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef int Integer;
typedef unsigned char Byte;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        typedef_symbols = [s for s in symbols if s.kind == "typedef"]
        typedef_names = [s.name for s in typedef_symbols]
        assert "Integer" in typedef_names
        assert "Byte" in typedef_names

    @pytest.mark.asyncio
    async def test_parse_typedef_struct(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef struct {
    int x;
    int y;
} Point;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        typedef_symbols = [s for s in symbols if s.kind == "typedef"]
        typedef_names = [s.name for s in typedef_symbols]
        assert "Point" in typedef_names

    @pytest.mark.asyncio
    async def test_parse_typedef_pointer(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef char* String;
typedef void* Pointer;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        typedef_symbols = [s for s in symbols if s.kind == "typedef"]
        typedef_names = [s.name for s in typedef_symbols]
        assert "String" in typedef_names
        assert "Pointer" in typedef_names

    @pytest.mark.asyncio
    async def test_parse_typedef_function_pointer(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef int (*Comparator)(const void*, const void*);
typedef void (*Callback)(int);
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        typedef_symbols = [s for s in symbols if s.kind == "typedef"]
        typedef_names = [s.name for s in typedef_symbols]
        assert "Comparator" in typedef_names
        assert "Callback" in typedef_names


class TestCMacros:
    """Tests for C macro parsing (now uses 'constant' kind)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_constant_macro(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
#define MAX_SIZE 100
#define PI 3.14159
#define VERSION "1.0.0"
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        const_symbols = [s for s in symbols if s.kind == "constant"]
        const_names = [s.name for s in const_symbols]
        assert "MAX_SIZE" in const_names
        assert "PI" in const_names
        assert "VERSION" in const_names

    @pytest.mark.asyncio
    async def test_parse_function_like_macro(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define SQUARE(x) ((x) * (x))
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        const_symbols = [s for s in symbols if s.kind == "constant"]
        const_names = [s.name for s in const_symbols]
        assert "MAX" in const_names
        assert "MIN" in const_names
        assert "SQUARE" in const_names

    @pytest.mark.asyncio
    async def test_parse_empty_macro(self, parser_service: TreeSitterService) -> None:
        code = """
#define DEBUG
#define FEATURE_ENABLED
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        const_symbols = [s for s in symbols if s.kind == "constant"]
        const_names = [s.name for s in const_symbols]
        assert "DEBUG" in const_names
        assert "FEATURE_ENABLED" in const_names


class TestCGlobalVariables:
    """Tests for C global variable parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_global_variables(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
int counter;
static float rate = 0.5;
char buffer[256];
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        var_symbols = [s for s in symbols if s.kind == "variable"]
        var_names = [s.name for s in var_symbols]
        assert "counter" in var_names
        assert "rate" in var_names
        assert "buffer" in var_names

    @pytest.mark.asyncio
    async def test_parse_pointer_variables(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
int* ptr;
char* message = "Hello";
void* data;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        var_symbols = [s for s in symbols if s.kind == "variable"]
        var_names = [s.name for s in var_symbols]
        assert "ptr" in var_names
        assert "message" in var_names
        assert "data" in var_names


class TestCReferences:
    """Tests for C reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_include_statements(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
#include <stdio.h>
#include <stdlib.h>
#include "myheader.h"
#include "utils/helper.h"
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        include_refs = [r for r in references if r.reference_type == "include"]
        include_texts = [r.reference_text for r in include_refs]
        assert "stdio.h" in include_texts
        assert "stdlib.h" in include_texts
        assert "myheader.h" in include_texts
        assert "utils/helper.h" in include_texts

    @pytest.mark.asyncio
    async def test_parse_function_calls(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void process(void) {
    initialize();
    calculate(1, 2);
    cleanup();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "initialize" in call_texts
        assert "calculate" in call_texts
        assert "cleanup" in call_texts

    @pytest.mark.asyncio
    async def test_builtin_calls_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void test(void) {
    printf("Hello");
    malloc(100);
    my_function();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "printf" not in call_texts
        assert "malloc" not in call_texts
        assert "my_function" in call_texts

    @pytest.mark.asyncio
    async def test_parse_type_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void process(Point p, Node* n) {
    MyStruct s;
    CustomType* ptr;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        assert "Point" in type_texts
        assert "Node" in type_texts
        assert "MyStruct" in type_texts
        assert "CustomType" in type_texts

    @pytest.mark.asyncio
    async def test_primitive_types_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void test(int x, char c) {
    float f;
    double d;
    MyType m;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        assert "int" not in type_texts
        assert "char" not in type_texts
        assert "float" not in type_texts
        assert "double" not in type_texts
        assert "MyType" in type_texts

    @pytest.mark.asyncio
    async def test_sizeof_references(self, parser_service: TreeSitterService) -> None:
        code = """
typedef struct { int x; } MyState;

void test(void) {
    size_t s1 = sizeof(MyState);
    size_t s2 = sizeof(OtherState);
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "MyState" in usage_texts
        assert "OtherState" in usage_texts

    @pytest.mark.asyncio
    async def test_initializer_list_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
FuncTable table[] = {
    { handler1, callback1, 0 },
    { handler2, callback2, 0 }
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "handler1" in usage_texts
        assert "callback1" in usage_texts
        assert "handler2" in usage_texts
        assert "callback2" in usage_texts

    @pytest.mark.asyncio
    async def test_field_access_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void test(void) {
    config.numberOfNodes = 256;
    ptr->fieldName = 0;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "config" in usage_texts
        assert "numberOfNodes" in usage_texts
        assert "ptr" in usage_texts
        assert "fieldName" in usage_texts

    @pytest.mark.asyncio
    async def test_method_call_no_duplicate_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Method calls should only create a 'call' reference, not also 'usage'."""
        code = """
void test(void) {
    obj.method();
    ptr->callback();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        method_refs = [r for r in references if r.reference_text == "method"]
        assert len(method_refs) == 1
        assert method_refs[0].reference_type == "call"

        callback_refs = [r for r in references if r.reference_text == "callback"]
        assert len(callback_refs) == 1
        assert callback_refs[0].reference_type == "call"

    @pytest.mark.asyncio
    async def test_ifdef_ifndef_identifier_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Macro names in #ifdef/#ifndef should produce references."""
        code = """
#ifndef MY_HEADER_H
#define MY_HEADER_H

#ifdef DEBUG_MODE
int debug_level;
#endif

#endif
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.h"
        )
        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "MY_HEADER_H" in usage_texts
        assert "DEBUG_MODE" in usage_texts


class TestCEdgeCases:
    """Tests for edge cases in C parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_forward_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
struct Node;

struct Node {
    int value;
    struct Node* next;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert any(s.name == "Node" for s in struct_symbols)

    @pytest.mark.asyncio
    async def test_parse_nested_struct(self, parser_service: TreeSitterService) -> None:
        code = """
struct Container {
    int id;
    struct {
        int x;
        int y;
    } position;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert any(s.name == "Container" for s in struct_symbols)

    @pytest.mark.asyncio
    async def test_parse_complex_typedef(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef struct ListNode {
    int data;
    struct ListNode* next;
} ListNode;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        struct_symbols = [s for s in symbols if s.kind == "struct"]
        typedef_symbols = [s for s in symbols if s.kind == "typedef"]
        assert any(s.name == "ListNode" for s in struct_symbols)
        assert any(s.name == "ListNode" for s in typedef_symbols)

    @pytest.mark.asyncio
    async def test_struct_type_ref_in_field_generates_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        """struct Tag used as a type in a field should produce a reference."""
        code = """
typedef struct _Actor {
    struct _Actor* next;
    int value;
} Actor;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        # The struct tag used as a type in the field should be a reference
        assert "_Actor" in type_texts

    @pytest.mark.asyncio
    async def test_typedef_name_positioned_at_alias(
        self, parser_service: TreeSitterService
    ) -> None:
        """Typedef symbol should be positioned at the alias name, not at 'typedef'."""
        code = """\
typedef struct _Desc {
    int x;
} Desc;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        typedef_sym = next(s for s in symbols if s.kind == "typedef")
        assert typedef_sym.name == "Desc"
        # The name "Desc" is on line 3, not line 1 where "typedef" starts
        assert typedef_sym.start_line == 3
        # end_line should span the whole typedef
        assert typedef_sym.end_line == 3

    @pytest.mark.asyncio
    async def test_parse_static_function(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
static int helper(int x) {
    return x * 2;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        func_symbols = [s for s in symbols if s.name == "helper"]
        assert len(func_symbols) == 1
        assert func_symbols[0].kind == "function"

    @pytest.mark.asyncio
    async def test_parse_header_file(self, parser_service: TreeSitterService) -> None:
        code = """
#ifndef MYLIB_H
#define MYLIB_H

#include <stdint.h>

#define MAX_ITEMS 100

typedef struct {
    int id;
    char name[64];
} Item;

int create_item(Item* item);
void destroy_item(Item* item);

#endif
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="mylib.h"
        )
        const_symbols = [s for s in symbols if s.kind == "constant"]
        const_names = [s.name for s in const_symbols]
        assert "MYLIB_H" in const_names
        assert "MAX_ITEMS" in const_names

        typedef_symbols = [s for s in symbols if s.kind == "typedef"]
        assert any(s.name == "Item" for s in typedef_symbols)

        func_symbols = [s for s in symbols if s.kind == "function"]
        func_names = [s.name for s in func_symbols]
        assert "create_item" in func_names
        assert "destroy_item" in func_names

        include_refs = [r for r in references if r.reference_type == "include"]
        assert any(r.reference_text == "stdint.h" for r in include_refs)

    @pytest.mark.asyncio
    async def test_parse_function_pointer_field(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
struct Handler {
    int (*process)(void* data);
    void (*cleanup)(void);
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert any(s.name == "Handler" for s in struct_symbols)

        fields = [s for s in symbols if s.kind == "struct_field"]
        field_names = [s.name for s in fields]
        assert "process" in field_names
        assert "cleanup" in field_names
        for field in fields:
            assert field.scope == "Handler"

    @pytest.mark.asyncio
    async def test_parse_extern_c_block(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
#ifndef MY_HEADER_H
#define MY_HEADER_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct _MyStruct {
    int x;
    int y;
} MyStruct;

void my_function(MyStruct* s);
int another_function(int a, int b);

#ifdef __cplusplus
}
#endif

#endif
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.h"
        )
        const_symbols = [s for s in symbols if s.kind == "constant"]
        const_names = [s.name for s in const_symbols]
        assert "MY_HEADER_H" in const_names

        struct_symbols = [s for s in symbols if s.kind == "struct"]
        struct_names = [s.name for s in struct_symbols]
        assert "_MyStruct" in struct_names

        fields = [s for s in symbols if s.kind == "struct_field"]
        field_names = [s.name for s in fields]
        assert "x" in field_names
        assert "y" in field_names

        typedef_symbols = [s for s in symbols if s.kind == "typedef"]
        typedef_names = [s.name for s in typedef_symbols]
        assert "MyStruct" in typedef_names

        func_symbols = [s for s in symbols if s.kind == "function"]
        func_names = [s.name for s in func_symbols]
        assert "my_function" in func_names
        assert "another_function" in func_names

    @pytest.mark.asyncio
    async def test_parse_variable_usage_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef struct {
    int debugLevel;
    int running;
    char* config;
} Globals;

static Globals globals;

void init() {
    globals.debugLevel = 1;
    globals.running = 1;
}

int get_debug_level() {
    return globals.debugLevel;
}

void process() {
    if (globals.running) {
        printf("%s", globals.config);
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        var_symbols = [s for s in symbols if s.kind == "variable"]
        assert any(s.name == "globals" for s in var_symbols)

        usage_refs = [r for r in references if r.reference_type == "usage"]
        globals_usages = [r for r in usage_refs if r.reference_text == "globals"]
        assert len(globals_usages) == 5


# ── C++ mode tests ──────────────────────────────────────────────────


class TestCppNamespaces:
    """Tests for C++ namespace parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_namespace(self, parser_service: TreeSitterService) -> None:
        code = """
namespace MyNamespace {
    void helper() {}
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="example.cpp"
        )
        ns_symbols = [s for s in symbols if s.kind == "namespace"]
        assert len(ns_symbols) == 1
        assert ns_symbols[0].name == "MyNamespace"

        func_symbols = [s for s in symbols if s.kind == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0].name == "helper"
        assert func_symbols[0].scope == "MyNamespace"

    @pytest.mark.asyncio
    async def test_parse_nested_namespaces(
        self, parser_service: TreeSitterService
    ) -> None:
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
        ns_symbols = [s for s in symbols if s.kind == "namespace"]
        ns_names = [s.name for s in ns_symbols]
        assert "Outer" in ns_names
        assert "Inner" in ns_names

        inner_ns = next(s for s in ns_symbols if s.name == "Inner")
        assert inner_ns.scope == "Outer"

        func_symbols = [s for s in symbols if s.kind == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0].name == "nested_func"
        assert func_symbols[0].scope == "Outer.Inner"


class TestCppClasses:
    """Tests for C++ class parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_class(self, parser_service: TreeSitterService) -> None:
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
        class_symbols = [s for s in symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "Person"

        field_symbols = [s for s in symbols if s.kind == "field"]
        field_names = [s.name for s in field_symbols]
        assert "age" in field_names

        method_symbols = [s for s in symbols if s.kind == "method"]
        assert any(m.name == "greet" and m.scope == "Person" for m in method_symbols)

    @pytest.mark.asyncio
    async def test_parse_class_with_inheritance(
        self, parser_service: TreeSitterService
    ) -> None:
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
        class_symbols = [s for s in symbols if s.kind == "class"]
        class_names = [s.name for s in class_symbols]
        assert "Base" in class_names
        assert "Derived" in class_names

        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        assert "Base" in type_texts


class TestCppStructs:
    """Tests for C++ struct parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_struct(self, parser_service: TreeSitterService) -> None:
        code = """
struct Point {
    double x;
    double y;
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="point.cpp"
        )
        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0].name == "Point"

        fields = [s for s in symbols if s.kind == "field" and s.scope == "Point"]
        field_names = [s.name for s in fields]
        assert "x" in field_names
        assert "y" in field_names


class TestCppFunctions:
    """Tests for C++ function parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_function(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void hello() {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )
        func_symbols = [s for s in symbols if s.kind == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0].name == "hello"

    @pytest.mark.asyncio
    async def test_parse_function_with_params(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
int add(int a, int b) {
    return a + b;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="math.cpp"
        )
        func_symbols = [s for s in symbols if s.kind == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0].name == "add"
        assert func_symbols[0].signature is not None
        assert (
            func_symbols[0].signature is not None and "add" in func_symbols[0].signature
        )

    @pytest.mark.asyncio
    async def test_parse_multiple_functions(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void foo() {}
int bar(int x) { return x; }
double baz(double a, double b) { return a + b; }
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="funcs.cpp"
        )
        func_symbols = [s for s in symbols if s.kind == "function"]
        func_names = [s.name for s in func_symbols]
        assert "foo" in func_names
        assert "bar" in func_names
        assert "baz" in func_names


class TestCppMethods:
    """Tests for C++ method parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_inline_method(self, parser_service: TreeSitterService) -> None:
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
        method_symbols = [s for s in symbols if s.kind == "method"]
        assert len(method_symbols) == 1
        assert method_symbols[0].name == "add"
        assert method_symbols[0].scope == "Calculator"
        assert method_symbols[0].signature is not None

    @pytest.mark.asyncio
    async def test_parse_constructor_destructor(
        self, parser_service: TreeSitterService
    ) -> None:
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
        method_symbols = [s for s in symbols if s.kind == "method"]
        method_names = [s.name for s in method_symbols]
        assert "Resource" in method_names
        assert "~Resource" in method_names
        for m in method_symbols:
            assert m.scope == "Resource"

    @pytest.mark.asyncio
    async def test_parse_multiple_methods(
        self, parser_service: TreeSitterService
    ) -> None:
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
        method_symbols = [s for s in symbols if s.kind == "method"]
        method_names = [s.name for s in method_symbols]
        assert "push" in method_names
        assert "pop" in method_names
        assert "size" in method_names
        for m in method_symbols:
            assert m.scope == "Container"


class TestCppFields:
    """Tests for C++ field (data member) parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_class_fields(self, parser_service: TreeSitterService) -> None:
        code = """
class Config {
    int timeout;
    bool enabled;
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="config.cpp"
        )
        fields = [s for s in symbols if s.kind == "field" and s.scope == "Config"]
        field_names = [s.name for s in fields]
        assert "timeout" in field_names
        assert "enabled" in field_names


class TestCppEnums:
    """Tests for C++ enum parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_enum(self, parser_service: TreeSitterService) -> None:
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
        enum_symbols = [s for s in symbols if s.kind == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0].name == "Color"

        enum_values = [s for s in symbols if s.kind == "enum_value"]
        value_names = [s.name for s in enum_values]
        assert "Red" in value_names
        assert "Green" in value_names
        assert "Blue" in value_names

    @pytest.mark.asyncio
    async def test_parse_enum_class(self, parser_service: TreeSitterService) -> None:
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
        enum_symbols = [s for s in symbols if s.kind == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0].name == "Status"

        enum_values = [s for s in symbols if s.kind == "enum_value"]
        value_names = [s.name for s in enum_values]
        assert "Active" in value_names
        assert "Inactive" in value_names
        assert "Pending" in value_names


class TestCppTypes:
    """Tests for C++ typedef and using alias parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_typedef(self, parser_service: TreeSitterService) -> None:
        code = """
typedef unsigned long ulong;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="types.cpp"
        )
        typedef_symbols = [s for s in symbols if s.kind == "typedef"]
        assert any(s.name == "ulong" for s in typedef_symbols)

    @pytest.mark.asyncio
    async def test_parse_using_alias(self, parser_service: TreeSitterService) -> None:
        code = """
using StringVec = int;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="types.cpp"
        )
        type_symbols = [s for s in symbols if s.kind == "type"]
        assert any(s.name == "StringVec" for s in type_symbols)


class TestCppTemplates:
    """Tests for C++ template parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_template_class(
        self, parser_service: TreeSitterService
    ) -> None:
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
        class_symbols = [s for s in symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "Container"

        method_symbols = [s for s in symbols if s.kind == "method"]
        assert any(m.name == "add" and m.scope == "Container" for m in method_symbols)

    @pytest.mark.asyncio
    async def test_parse_template_function(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
template<typename T>
T maximum(T a, T b) {
    return (a > b) ? a : b;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="util.cpp"
        )
        func_symbols = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "maximum" for s in func_symbols)


class TestCppReferences:
    """Tests for C++ reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_function_calls(
        self, parser_service: TreeSitterService
    ) -> None:
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
        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "helper" in call_texts
        assert "doWork" in call_texts

    @pytest.mark.asyncio
    async def test_parse_include_directives(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
#include <iostream>
#include "myheader.h"

void main() {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )
        include_refs = [r for r in references if r.reference_type == "include"]
        include_texts = [r.reference_text for r in include_refs]
        assert "iostream" in include_texts
        assert "myheader.h" in include_texts

    @pytest.mark.asyncio
    async def test_parse_type_usage(self, parser_service: TreeSitterService) -> None:
        code = """
class Widget {};

void process(Widget w) {
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="proc.cpp"
        )
        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        assert "Widget" in type_texts

    @pytest.mark.asyncio
    async def test_builtin_calls_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void process() {
    int x = sizeof(int);
    customFunc();
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )
        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "sizeof" not in call_texts
        assert "customFunc" in call_texts

    @pytest.mark.asyncio
    async def test_primitive_types_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void compute(int a, double b) {
    bool flag = true;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="compute.cpp"
        )
        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        assert "int" not in type_texts
        assert "double" not in type_texts
        assert "bool" not in type_texts


class TestCppComments:
    """Tests for C++ comment extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_single_line_comment(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
// This is a comment
void foo() {}
"""
        comments = await parser_service.extract_comments(
            content=code, language="cpp", file_path="example.cpp"
        )
        assert len(comments) >= 1
        assert any(c.content == "This is a comment" for c in comments)
        assert any(c.content_type == "single_line_comment" for c in comments)

    @pytest.mark.asyncio
    async def test_parse_block_comment(self, parser_service: TreeSitterService) -> None:
        code = """
/* Block comment */
void foo() {}
"""
        comments = await parser_service.extract_comments(
            content=code, language="cpp", file_path="example.cpp"
        )
        assert len(comments) >= 1
        assert any(c.content == "Block comment" for c in comments)
        assert any(c.content_type == "block_comment" for c in comments)


class TestCppComplexStructures:
    """Tests for complex C++ structures."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_full_cpp_file(self, parser_service: TreeSitterService) -> None:
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

        ns = [s for s in symbols if s.kind == "namespace"]
        assert any(s.name == "App" for s in ns)

        consts = [s for s in symbols if s.kind == "constant"]
        assert any(c.name == "MAX_SIZE" for c in consts)

        enums = [s for s in symbols if s.kind == "enum"]
        assert any(e.name == "LogLevel" for e in enums)

        enum_vals = [s for s in symbols if s.kind == "enum_value"]
        ev_names = [s.name for s in enum_vals]
        assert "Debug" in ev_names
        assert "Info" in ev_names
        assert "Error" in ev_names

        classes = [s for s in symbols if s.kind == "class"]
        assert any(c.name == "Logger" for c in classes)

        methods = [s for s in symbols if s.kind == "method"]
        assert any(m.name == "log" and m.scope == "App.Logger" for m in methods)

        fields = [s for s in symbols if s.kind == "field"]
        assert any(f.name == "count" and f.scope == "App.Logger" for f in fields)

        funcs = [s for s in symbols if s.kind == "function"]
        assert any(f.name == "initialize" and f.scope == "App" for f in funcs)

        include_refs = [r for r in references if r.reference_type == "include"]
        include_texts = [r.reference_text for r in include_refs]
        assert "iostream" in include_texts

    @pytest.mark.asyncio
    async def test_parse_constexpr_variable(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
constexpr int BUFFER_SIZE = 4096;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="config.cpp"
        )
        const_symbols = [s for s in symbols if s.kind == "constant"]
        assert any(s.name == "BUFFER_SIZE" for s in const_symbols)

    @pytest.mark.asyncio
    async def test_parse_define_macro(self, parser_service: TreeSitterService) -> None:
        code = """
#define MAX_RETRIES 3
#define PI 3.14159
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="config.cpp"
        )
        const_symbols = [s for s in symbols if s.kind == "constant"]
        const_names = [s.name for s in const_symbols]
        assert "MAX_RETRIES" in const_names
        assert "PI" in const_names


class TestCppUnions:
    """Tests for C++ union parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_union(self, parser_service: TreeSitterService) -> None:
        code = """
union Data {
    int i;
    float f;
    char c;
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="data.cpp"
        )
        unions = [s for s in symbols if s.kind == "union"]
        assert len(unions) == 1
        assert unions[0].name == "Data"

        fields = [s for s in symbols if s.kind == "field"]
        field_names = [f.name for f in fields]
        assert "i" in field_names
        assert "f" in field_names
        assert "c" in field_names

    @pytest.mark.asyncio
    async def test_parse_typedef_union(self, parser_service: TreeSitterService) -> None:
        code = """
typedef union {
    int value;
    float fval;
} Variant;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="variant.cpp"
        )
        typedefs = [s for s in symbols if s.kind == "typedef"]
        assert any(t.name == "Variant" for t in typedefs)


class TestCppEdgeCases:
    """Tests for edge cases in C++ parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_empty_cpp_file(self, parser_service: TreeSitterService) -> None:
        code = ""
        symbols, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="empty.cpp"
        )
        assert isinstance(symbols, list)
        assert isinstance(references, list)

    @pytest.mark.asyncio
    async def test_malformed_cpp_code(self, parser_service: TreeSitterService) -> None:
        code = """
class Broken {
    void method(
    int x = ;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="broken.cpp"
        )
        assert isinstance(symbols, list)
        assert isinstance(references, list)

    @pytest.mark.asyncio
    async def test_namespace_qualified_function_not_method(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
namespace N {
    void f();
}
void N::f() {}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="ns_func.cpp"
        )
        out_of_class = [s for s in symbols if s.name == "f" and s.kind == "function"]
        assert len(out_of_class) >= 1
        methods = [s for s in symbols if s.name == "f" and s.kind == "method"]
        assert len(methods) == 0

    @pytest.mark.asyncio
    async def test_class_qualified_function_is_method(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
class MyClass {
public:
    void doWork();
};
void MyClass::doWork() {}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="class_method.cpp"
        )
        methods = [s for s in symbols if s.name == "doWork" and s.kind == "method"]
        assert len(methods) >= 1

    @pytest.mark.asyncio
    async def test_typedef_no_self_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef int MyInt;
using MyFloat = float;
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="aliases.cpp"
        )
        ref_texts = [r.reference_text for r in references]
        assert "MyInt" not in ref_texts
        assert "MyFloat" not in ref_texts

    @pytest.mark.asyncio
    async def test_qualified_call_uses_terminal_name(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
namespace NS {
    void helper();
}
void foo() {
    NS::helper();
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="calls.cpp"
        )
        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "helper" in call_texts
        assert "NS::helper" not in call_texts

    @pytest.mark.asyncio
    async def test_method_declarations_in_header(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
class Widget {
public:
    void draw();
    int width() const;
    void resize(int w, int h);
private:
    int m_width;
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="widget.h"
        )
        methods = [s for s in symbols if s.kind == "method"]
        method_names = [m.name for m in methods]
        assert "draw" in method_names
        assert "width" in method_names
        assert "resize" in method_names

        fields = [s for s in symbols if s.kind == "field"]
        assert any(f.name == "m_width" for f in fields)

    @pytest.mark.asyncio
    async def test_pure_c_header_parsed_as_cpp(
        self, parser_service: TreeSitterService
    ) -> None:
        """Pure C code in .h files should be parsed correctly by C++ parser."""
        code = """
#ifndef MY_HEADER_H
#define MY_HEADER_H

#include <stdio.h>

#define BUFFER_SIZE 1024

typedef struct {
    int x;
    int y;
} Point;

enum Color { RED, GREEN, BLUE };

static int counter = 0;

int add(int a, int b);
void print_point(const Point *p);

#endif
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="cpp", file_path="utils.h"
        )
        sym_names = [s.name for s in symbols]
        sym_kinds = {s.name: s.kind for s in symbols}

        assert "MY_HEADER_H" in sym_names
        assert "BUFFER_SIZE" in sym_names
        assert sym_kinds["BUFFER_SIZE"] == "constant"
        assert "Point" in sym_names
        assert "Color" in sym_names
        assert "RED" in sym_names
        assert "counter" in sym_names
        assert "add" in sym_names
        assert "print_point" in sym_names

        include_refs = [r for r in references if r.reference_type == "include"]
        assert any(r.reference_text == "stdio.h" for r in include_refs)

    @pytest.mark.asyncio
    async def test_function_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """void MyFunction() {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="cpp", file_path="main.cpp"
        )
        func_symbols = [s for s in symbols if s.name == "MyFunction"]
        assert len(func_symbols) == 1
        assert func_symbols[0].start_line == 1


# ── Identifier usage references ────────────────────────────────


class TestIdentifierUsageReferences:
    """Tests for general identifier usage references (enum values, constants,
    variables used in expressions, function arguments, etc.)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_enum_value_as_function_argument(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef enum { TIMER_ONESHOT, TIMER_PERIODIC } TimerType;
void Create_Timer(int x, TimerType type, int ms);
void test() {
    Create_Timer(0, TIMER_ONESHOT, 100);
}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r
            for r in refs
            if r.reference_text == "TIMER_ONESHOT" and r.reference_type == "usage"
        ]
        assert len(usage_refs) >= 1

    @pytest.mark.asyncio
    async def test_enum_value_in_assignment(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef enum { VALUE_A, VALUE_B } MyEnum;
void test() {
    MyEnum x = VALUE_A;
}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r
            for r in refs
            if r.reference_text == "VALUE_A" and r.reference_type == "usage"
        ]
        assert len(usage_refs) >= 1

    @pytest.mark.asyncio
    async def test_enum_value_in_comparison(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef enum { STATE_INIT, STATE_RUNNING } State;
void test(State s) {
    if (s == STATE_INIT) {}
}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r
            for r in refs
            if r.reference_text == "STATE_INIT" and r.reference_type == "usage"
        ]
        assert len(usage_refs) >= 1

    @pytest.mark.asyncio
    async def test_constant_as_function_argument(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
#define MAX_SIZE 100
void alloc(int size);
void test() {
    alloc(MAX_SIZE);
}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r
            for r in refs
            if r.reference_text == "MAX_SIZE" and r.reference_type == "usage"
        ]
        assert len(usage_refs) >= 1

    @pytest.mark.asyncio
    async def test_variable_definition_not_duplicated(
        self, parser_service: TreeSitterService
    ) -> None:
        """Variable names in declarations should NOT create usage refs."""
        code = """
int myGlobal = 42;
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r
            for r in refs
            if r.reference_text == "myGlobal" and r.reference_type == "usage"
        ]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_enum_value_in_return_statement(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
typedef enum { OK, ERR } Status;
Status get_status() {
    return OK;
}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r for r in refs if r.reference_text == "OK" and r.reference_type == "usage"
        ]
        assert len(usage_refs) >= 1

    @pytest.mark.asyncio
    async def test_identifier_in_array_size(
        self, parser_service: TreeSitterService
    ) -> None:
        """Array size expressions should generate usage refs."""
        code = """
#define ARRAY_SIZE 10
int arr[ARRAY_SIZE];
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r
            for r in refs
            if r.reference_text == "ARRAY_SIZE" and r.reference_type == "usage"
        ]
        assert len(usage_refs) >= 1

    @pytest.mark.asyncio
    async def test_identifier_in_case_statement(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
#define MY_CONST 1
void test(int x) {
    switch(x) {
    case MY_CONST:
        break;
    }
}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r
            for r in refs
            if r.reference_text == "MY_CONST" and r.reference_type == "usage"
        ]
        assert len(usage_refs) >= 1

    @pytest.mark.asyncio
    async def test_function_param_not_usage_ref(
        self, parser_service: TreeSitterService
    ) -> None:
        """Parameter names should NOT generate usage refs."""
        code = """
void foo(int myParam) {}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r
            for r in refs
            if r.reference_text == "myParam" and r.reference_type == "usage"
        ]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_enum_definition_not_usage_ref(
        self, parser_service: TreeSitterService
    ) -> None:
        """Enum value definitions should NOT generate usage refs."""
        code = """
enum Color { RED, GREEN, BLUE };
"""
        _, refs = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )
        usage_refs = [
            r for r in refs if r.reference_text == "RED" and r.reference_type == "usage"
        ]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_qualified_definition_not_usage_ref(
        self, parser_service: TreeSitterService
    ) -> None:
        """Out-of-class definitions like N::f should NOT generate usage refs."""
        code = """
namespace N {
    void f();
}
void N::f() {}

class MyClass {
public:
    void doWork();
};
void MyClass::doWork() {}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="cpp", file_path="test.cpp"
        )
        # "f" and "doWork" should not get spurious usage refs from qualified_identifier
        f_usage = [
            r for r in refs if r.reference_text == "f" and r.reference_type == "usage"
        ]
        assert len(f_usage) == 0
        dowork_usage = [
            r
            for r in refs
            if r.reference_text == "doWork" and r.reference_type == "usage"
        ]
        assert len(dowork_usage) == 0

    @pytest.mark.asyncio
    async def test_template_call_no_duplicate_ref(
        self, parser_service: TreeSitterService
    ) -> None:
        """Template function calls should not generate duplicate usage refs."""
        code = """
template<typename T>
T make();
void test() {
    make<int>();
}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="cpp", file_path="test.cpp"
        )
        make_refs = [r for r in refs if r.reference_text == "make"]
        call_refs = [r for r in make_refs if r.reference_type == "call"]
        usage_refs = [r for r in make_refs if r.reference_type == "usage"]
        assert len(call_refs) == 1
        assert len(usage_refs) == 0


class TestCppQualifierReferences:
    """The class/namespace qualifier in `T::member` is a reference (#548)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    async def test_scope_qualifiers_are_referenced(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
void f() {
    auto a = Factory::create();
    auto b = Outer::Inner::VALUE;
    std::vector<int> v;
}
"""
        _, refs = await parser_service.parse_file(code, "cpp", "f.cpp")
        texts = {r.reference_text for r in refs}
        assert {"Factory", "Outer", "Inner"} <= texts
        assert "std" not in texts


# ── Out-of-line definitions: qualified names (#591) ─────────────────

# A qualified_name must be a dotted path of bare identifiers.  The only
# exception is the final segment of an operator (``operator()``,
# ``operator bool``, ``operator char*``), whose canonical C++ spelling
# contains punctuation and, for conversion operators, a space.
_JUNK_IN_SCOPE = re.compile(r"[\s<>{}();:,&*]")


def _assert_clean_qualified_name(qualified_name: str | None) -> None:
    if qualified_name is None:
        return
    scope, _, name = qualified_name.rpartition(".")
    assert not _JUNK_IN_SCOPE.search(scope), f"junk in scope: {qualified_name!r}"
    if not name.startswith("operator"):
        assert not _JUNK_IN_SCOPE.search(name), f"junk in name: {qualified_name!r}"
    assert "\n" not in qualified_name


async def _parse(
    code: str, language: str = "cpp"
) -> tuple[list[ParsedSymbol], list[ParsedReference]]:
    symbols, refs = await TreeSitterService().parse_file(
        content=code, language=language, file_path="x.h"
    )
    for s in symbols:
        _assert_clean_qualified_name(s.qualified_name)
        assert "\n" not in s.name and "::" not in s.name, s.name
    return symbols, refs


def _by_name(symbols: list[ParsedSymbol], name: str) -> ParsedSymbol:
    matches = [s for s in symbols if s.name == name]
    assert (
        len(matches) == 1
    ), f"{name!r}: {[(s.name, s.qualified_name) for s in symbols]}"
    return matches[0]


class TestCppOutOfLineQualifiedNames:
    """Out-of-line definitions must not leak return types, macros, template
    arguments or misparsed text into ``name``/``qualified_name`` (#591).

    Fixtures are trimmed from spdlog, where tree-sitter misparses macro
    prefixes (``SPDLOG_INLINE``) and qualified return types into one long
    ``qualified_identifier`` chain bridged by MISSING ``::`` or ERROR nodes.
    """

    async def test_macro_prefixed_after_unterminated_macro_call(self) -> None:
        # SPDLOG_LOGGER_CATCH(...) has no semicolon, so the next definition
        # parses as `SPDLOG_INLINE ERROR(void async_logger) :: backend_sink_it_`.
        code = """
// send flush request to the thread pool
SPDLOG_INLINE void async_logger::flush_(){
    SPDLOG_TRY{if (auto pool_ptr = thread_pool_.lock()){
        pool_ptr -> post_flush(shared_from_this(), overflow_policy_);
}
else {
    throw_spdlog_ex("async flush: thread pool doesn't exist anymore");
}
}
SPDLOG_LOGGER_CATCH(source_loc())
}

//
// backend functions - called from the thread pool to do the actual job
//
SPDLOG_INLINE void async_logger::backend_sink_it_(const details::log_msg &incoming_log_msg) {
    for (auto &sink : sinks_) {
        if (sink->should_log(incoming_log_msg.level)) {
}}}
"""
        symbols, _ = await _parse(code)
        sym = _by_name(symbols, "backend_sink_it_")
        assert sym.kind == "method"
        assert sym.qualified_name == "async_logger.backend_sink_it_"

    async def test_macro_prefixed_after_namespace_macro(self) -> None:
        # SPDLOG_NAMESPACE_BEGIN expands to `namespace spdlog {`; unexpanded
        # it yields `SPDLOG_INLINE ERROR(bool sinks) :: sink::should_log`.
        code = """
SPDLOG_NAMESPACE_BEGIN

SPDLOG_INLINE bool sinks::sink::should_log(level::level_enum msg_level) const {
    return msg_level >= level_.load(std::memory_order_relaxed);
}
"""
        symbols, _ = await _parse(code)
        sym = _by_name(symbols, "should_log")
        assert sym.kind == "method"
        assert sym.qualified_name == "sinks.sink.should_log"

    async def test_templated_qualified_return_type(self) -> None:
        code = """
namespace spdlog {
SPDLOG_INLINE std::shared_ptr<logger> async_logger::clone(std::string new_name) {
    return cloned;
}
}
"""
        symbols, _ = await _parse(code)
        sym = _by_name(symbols, "clone")
        assert sym.kind == "method"
        assert sym.qualified_name == "spdlog.async_logger.clone"

    async def test_nested_namespace_return_type(self) -> None:
        code = """
SPDLOG_INLINE level::level_enum logger::level() const {
    return static_cast<level::level_enum>(level_.load(std::memory_order_relaxed));
}
"""
        symbols, _ = await _parse(code)
        sym = _by_name(symbols, "level")
        assert sym.kind == "method"
        assert sym.qualified_name == "logger.level"

    async def test_reference_to_templated_return_type(self) -> None:
        code = """
SPDLOG_INLINE const std::vector<sink_ptr> &logger::sinks() const { return sinks_; }
"""
        symbols, _ = await _parse(code)
        sym = _by_name(symbols, "sinks")
        assert sym.kind == "method"
        assert sym.qualified_name == "logger.sinks"

    async def test_pointer_and_reference_return_types_keep_scope(self) -> None:
        code = """
int* Foo::ptr() { return 0; }
Foo& Foo::operator=(const Foo& o) { return *this; }
"""
        symbols, _ = await _parse(code)
        ptr = _by_name(symbols, "ptr")
        assert (ptr.kind, ptr.qualified_name) == ("method", "Foo.ptr")
        assign = _by_name(symbols, "operator=")
        assert (assign.kind, assign.qualified_name) == ("method", "Foo.operator=")

    async def test_class_template_member_with_macro(self) -> None:
        code = """
template <typename Mutex>
void SPDLOG_INLINE spdlog::sinks::base_sink<Mutex>::log(const details::log_msg &msg) {
}

template <typename Mutex>
void SPDLOG_INLINE
sinks::base_sink<Mutex>::set_formatter(std::unique_ptr<formatter> sink_formatter) {
}
"""
        symbols, _ = await _parse(code)
        log = _by_name(symbols, "log")
        assert (log.kind, log.qualified_name) == (
            "method",
            "spdlog.sinks.base_sink.log",
        )
        set_fmt = _by_name(symbols, "set_formatter")
        assert set_fmt.kind == "method"
        assert set_fmt.qualified_name == "sinks.base_sink.set_formatter"

    async def test_template_arguments_stripped_from_scope_and_name(self) -> None:
        code = """
template <typename T> void ns::Outer<T>::Inner::baz() {}
template <> void Foo<int>::bar() {}
template <> void Widget::get<int>() {}
"""
        symbols, _ = await _parse(code)
        assert _by_name(symbols, "baz").qualified_name == "ns.Outer.Inner.baz"
        assert _by_name(symbols, "bar").qualified_name == "Foo.bar"
        assert _by_name(symbols, "get").qualified_name == "Widget.get"

    async def test_free_function_with_qualified_return_type(self) -> None:
        code = """
namespace spdlog {
namespace level {
SPDLOG_INLINE level::level_enum from_str(const std::string &name) SPDLOG_NOEXCEPT {
    return off;
}
SPDLOG_API level::level_enum to_level(const std::string &name) SPDLOG_NOEXCEPT;
}
SPDLOG_INLINE std::shared_ptr<logger> get(const std::string &name) {
    return details::registry::instance().get(name);
}
}
SPDLOG_CONSTEXPR_FUNC spdlog::string_view_t to_string_view(const memory_buf_t &buf)
    SPDLOG_NOEXCEPT {
    return spdlog::string_view_t{buf.data(), buf.size()};
}
"""
        symbols, _ = await _parse(code)
        from_str = _by_name(symbols, "from_str")
        assert (from_str.kind, from_str.qualified_name) == (
            "function",
            "spdlog.level.from_str",
        )
        to_level = _by_name(symbols, "to_level")
        assert (to_level.kind, to_level.qualified_name) == (
            "function",
            "spdlog.level.to_level",
        )
        get = _by_name(symbols, "get")
        assert (get.kind, get.qualified_name) == ("function", "spdlog.get")
        tsv = _by_name(symbols, "to_string_view")
        assert (tsv.kind, tsv.scope, tsv.qualified_name) == ("function", None, None)

    async def test_template_free_function_after_namespace_macro(self) -> None:
        code = """
SPDLOG_NAMESPACE_BEGIN

template <typename Factory>
SPDLOG_INLINE std::shared_ptr<logger> stdout_color_mt(const std::string &logger_name,
                                                      color_mode mode) {
    return Factory::template create<sinks::stdout_color_sink_mt>(logger_name, mode);
}
"""
        symbols, _ = await _parse(code)
        sym = _by_name(symbols, "stdout_color_mt")
        assert (sym.kind, sym.qualified_name) == ("function", None)

    async def test_conversion_operators(self) -> None:
        code = """
struct S {
    explicit operator bool() const { return true; }
};
Foo::operator bool() const { return ok_; }
foo::operator char*() const { return p_; }
void Foo::operator()(int x) {}
"""
        symbols, _ = await _parse(code)
        in_class = [s for s in symbols if s.qualified_name == "S.operator bool"]
        assert len(in_class) == 1 and in_class[0].kind == "method"
        out_bool = [s for s in symbols if s.qualified_name == "Foo.operator bool"]
        assert len(out_bool) == 1 and out_bool[0].kind == "method"
        out_ptr = [s for s in symbols if s.qualified_name == "foo.operator char*"]
        assert len(out_ptr) == 1 and out_ptr[0].name == "operator char*"
        call = [s for s in symbols if s.qualified_name == "Foo.operator()"]
        assert len(call) == 1 and call[0].kind == "method"

    async def test_misparsed_class_body_does_not_become_a_method(self) -> None:
        # FMT_BEGIN_EXPORT (no semicolon) + a template class: tree-sitter
        # makes one bogus function_definition whose "scope" is a dependent_name
        # wrapping an ERROR that spans the whole class body, and whose "name"
        # is a call inside a method (`detail::is_constant_evaluated`).
        code = """
// Parsing-related public API and forward declarations.
FMT_BEGIN_EXPORT

/**
 * An implementation of `std::basic_string_view` for pre-C++17. It provides a
 * subset of the API. `fmt::basic_string_view` is used for format strings even
 * if `std::basic_string_view` is available to prevent issues when a library is
 * compiled with a different `-std` option than the client code (which is not
 * recommended).
 */
template <typename Char> class basic_string_view {
 private:
  const Char* data_;
  size_t size_;

 public:
  using value_type = Char;
  using iterator = const Char*;

  constexpr basic_string_view() noexcept : data_(nullptr), size_(0) {}

  /// Constructs a string view object from a C string and a size.
  constexpr basic_string_view(const Char* s, size_t count) noexcept
      : data_(s), size_(count) {}

  constexpr basic_string_view(nullptr_t) = delete;

  /// Constructs a string view object from a C string.
#if FMT_GCC_VERSION
  FMT_ALWAYS_INLINE
#endif
  FMT_CONSTEXPR20 basic_string_view(const Char* s) : data_(s) {
#if FMT_HAS_BUILTIN(__builtin_strlen) || FMT_GCC_VERSION || FMT_CLANG_VERSION
    if (std::is_same<Char, char>::value && !detail::is_constant_evaluated()) {
      size_ = __builtin_strlen(detail::narrow(s));  // strlen is not constexpr.
      return;
    }
#endif
    size_t len = 0;
    while (*s++) ++len;
    size_ = len;
  }
};
"""
        symbols, _ = await _parse(code)
        phantom = [s for s in symbols if "is_constant_evaluated" in s.name]
        assert not phantom, [(s.name, s.qualified_name) for s in phantom]

    async def test_misparsed_exported_class_does_not_become_a_method(self) -> None:
        # `class SPDLOG_API spdlog_ex : public std::exception {` parses as a
        # function_definition whose declarator is the bare base class name.
        code = """
class SPDLOG_API spdlog_ex : public std::exception {
public:
    explicit spdlog_ex(std::string msg);
    const char *what() const SPDLOG_NOEXCEPT override;

private:
    std::string msg_;
};
"""
        symbols, _ = await _parse(code)
        phantom = [s for s in symbols if s.name == "exception"]
        assert not phantom, [(s.name, s.qualified_name) for s in phantom]

    async def test_call_references_use_structured_terminal_name(self) -> None:
        code = """
void f() {
    Factory::template create<sinks::stdout_color_sink_mt>(name, mode);
    detail::tm_writer<int, Char>(out);
    detail::copy<Char, const Char*, Char*>(a, b);
    ns::g();
    loc.template get<std::locale>();
    obj.convert<int>(x);
    ptr->~Widget();
}
"""
        _, refs = await _parse(code)
        calls = {r.reference_text for r in refs if r.reference_type == "call"}
        assert {
            "create",
            "tm_writer",
            "copy",
            "g",
            "get",
            "convert",
            "~Widget",
        } <= calls
        assert not [c for c in calls if _JUNK_IN_SCOPE.search(c)], calls


class TestCMacroPrefixedFunctions:
    """C shares the C/C++ parser; macro-prefixed definitions keep clean names."""

    async def test_macro_prefixed_c_functions(self) -> None:
        code = """
API_EXPORT int add(int a, int b) { return a + b; }
CJSON_PUBLIC char *dup_string(const char *s) { return 0; }
"""
        symbols, _ = await _parse(code, language="c")
        add = _by_name(symbols, "add")
        assert (add.kind, add.scope, add.qualified_name) == ("function", None, None)
        dup = _by_name(symbols, "dup_string")
        assert (dup.kind, dup.scope, dup.qualified_name) == ("function", None, None)

    async def test_misparsed_call_in_kr_function_is_not_a_definition(self) -> None:
        # From git's compat/regex/regcomp.c: a K&R definition behind
        # `auto inline` + `__attribute` misparses so that the call
        # `strlen ((const char *) name)` becomes a nested function_declarator.
        code = """
  auto inline reg_errcode_t
  __attribute ((always_inline))
  build_collating_symbol (sbcset, mbcset, coll_sym_alloc, name)
     re_charset_t *mbcset;
     int *coll_sym_alloc;
     bitset_t sbcset;
     const unsigned char *name;
    {
      int32_t elem, idx;
      size_t name_len = strlen ((const char *) name);
      if (nrules != 0)
    {
      elem = seek_collating_symbol_entry (name, name_len);
      if (symb_table[2 * elem] != 0)
        {
          /* We found the entry.  */
          idx = symb_table[2 * elem + 1];
          /* Skip the name of collating element name.  */
          idx += 1 + extra[idx];
        }
      else if (symb_table[2 * elem] == 0 && name_len == 1)
        {
          /* No valid character, treat it as a normal
         character.  */
          bitset_set (sbcset, name[0]);
          return REG_NOERROR;
        }
      else
        return REG_ECOLLATE;

      /* Got valid collation sequence, add it as a new entry.  */
      /* Check the space of the arrays.  */
      if (BE (*coll_sym_alloc == mbcset->ncoll_syms, 0))
        {
          /* Not enough, realloc it.  */
          /* +1 in case of mbcset->ncoll_syms is 0.  */
          int new_coll_sym_alloc = 2 * mbcset->ncoll_syms + 1;
          /* Use realloc since mbcset->coll_syms is NULL
         if *alloc == 0.  */
          int32_t *new_coll_syms = re_realloc (mbcset->coll_syms, int32_t,
                           new_coll_sym_alloc);
          if (BE (new_coll_syms == NULL, 0))
        return REG_ESPACE;
          mbcset->coll_syms = new_coll_syms;
          *coll_sym_alloc = new_coll_sym_alloc;
        }
      mbcset->coll_syms[mbcset->ncoll_syms++] = idx;
      return REG_NOERROR;
    }
"""
        symbols, _ = await _parse(code, language="c")
        assert not [s for s in symbols if s.name == "strlen"]


class TestCppMisparsedTemplateScopes:
    """Template scopes damaged by macros resolve to the right class, never to
    a dropped class or a keyword such as ``void`` (#596 review).

    These assert exact names, so a rule that rejects too much fails too.
    """

    async def test_macro_line_before_template_keeps_class(self) -> None:
        # The scope becomes dependent_name(ERROR(<...> void), basic_ios<C, T>).
        code = """
namespace std {
MY_MACRO
 template<typename C, typename T>
 void
 basic_ios<C, T>::clear(int s) {}
}
"""
        symbols, _ = await _parse(code)
        clear = _by_name(symbols, "clear")
        assert (clear.kind, clear.qualified_name) == ("method", "std.basic_ios.clear")

    async def test_macro_line_before_template_keeps_swallowed_qualifier(
        self,
    ) -> None:
        # `outer::` ends up inside the dependent_name's ERROR node.
        code = """
MY_MACRO
 template<typename C, typename T>
 void
 outer::basic_ios<C, T>::clear(int s) {}
"""
        symbols, _ = await _parse(code)
        assert _by_name(symbols, "clear").qualified_name == "outer.basic_ios.clear"

    async def test_clean_dependent_name_mid_chain_keeps_outer_scope(self) -> None:
        code = """
template <typename T> template <typename U>
void ns::Outer<T>::template Inner<U>::f() {}
"""
        symbols, _ = await _parse(code)
        f = _by_name(symbols, "f")
        assert (f.kind, f.qualified_name) == ("method", "ns.Outer.Inner.f")

    async def test_macro_between_template_and_return_type(self) -> None:
        # The scope becomes template_type(name: void, ERROR(Foo), <T>).
        code = """
template<class T> MACRO void Foo<T>::mac() {}
template<typename T> MACRO typename vector<T>::iterator
vector<T>::_M_erase(iterator p) { return p; }
"""
        symbols, _ = await _parse(code)
        mac = _by_name(symbols, "mac")
        assert (mac.kind, mac.qualified_name) == ("method", "Foo.mac")
        erase = _by_name(symbols, "_M_erase")
        assert (erase.kind, erase.qualified_name) == ("method", "vector._M_erase")

    async def test_keyword_is_never_a_scope(self) -> None:
        # libstdc++ bits/cow_string.h: `friend void ::f()` misparses with
        # `void` as a namespace_identifier scope.
        code = """
      friend const char*
      ::_txnal_cow_string_c_str(const void *that);
      friend void
      ::_txnal_cow_string_D1(void *that);
      friend void
"""
        symbols, _ = await _parse(code)
        d1 = _by_name(symbols, "_txnal_cow_string_D1")
        assert (d1.kind, d1.qualified_name) == ("function", None)
        assert not [
            s for s in symbols if s.qualified_name and "void." in s.qualified_name
        ]

    async def test_scope_with_parenthesised_template_args_is_kept(self) -> None:
        # Braces/semicolons reject a scope only inside error-recovered nodes;
        # clean template arguments may contain `{}`, `(` and `)`.
        code = """
template <typename T> void Foo<decltype(T{} + 1)>::m() {}
template <typename T> void Bar<sizeof(T)>::n() {}
"""
        symbols, _ = await _parse(code)
        assert _by_name(symbols, "m").qualified_name == "Foo.m"
        assert _by_name(symbols, "n").qualified_name == "Bar.n"

    async def test_qualified_prototype_gets_class_scope(self) -> None:
        # spdlog sinks/base_sink-inl.h: the mem-initializer `formatter_{...}`
        # makes tree-sitter parse this constructor as a declaration.
        code = """
template <typename Mutex>
SPDLOG_INLINE sinks::base_sink<Mutex>::base_sink(
    std::unique_ptr<formatter> formatter)
    : formatter_{std::move(formatter)} {}
"""
        symbols, _ = await _parse(code)
        ctor = _by_name(symbols, "base_sink")
        assert ctor.kind == "method"
        assert ctor.qualified_name == "sinks.base_sink.base_sink"

    async def test_unqualified_prototype_stays_function(self) -> None:
        code = """
namespace ns {
void helper(int x);
}
"""
        symbols, _ = await _parse(code)
        helper = _by_name(symbols, "helper")
        assert (helper.kind, helper.qualified_name) == ("function", "ns.helper")

    async def test_bare_template_declarator_is_not_a_definition(self) -> None:
        # fmt os.h: `FMT_BEGIN_EXPORT` + doc comment + `template <typename
        # Char>` misparses as the declarator `FMT_BEGIN_EXPORT<typename Char>`.
        code = """
FMT_BEGIN_NAMESPACE
FMT_BEGIN_EXPORT

/**
 * A reference to a null-terminated string.
 */
template <typename Char> class basic_cstring_view {
 private:
  const Char* data_;

 public:
  basic_cstring_view(const Char* s) : data_(s) {}
};
"""
        symbols, _ = await _parse(code)
        assert not [s for s in symbols if s.name == "FMT_BEGIN_EXPORT"]

    async def test_cast_in_preprocessor_branch_is_not_a_method(self) -> None:
        # libstdc++ parallel/random_number.h: `return static_cast<T>(x);`
        # under `#if` misparses as a template_method declarator.
        code = """
  class _RandomNumber
  {
  private:
    std::tr1::mt19937   _M_mt;
    uint64_t            _M_supremum;
    uint64_t            _M_rand_sup;
    double              _M_supremum_reciprocal;
    double              _M_rand_sup_reciprocal;

    // Assumed to be twice as long as the usual random number.
    uint64_t              __cache;

    // Bit results.
    int __bits_left;

    static uint32_t
    __scale_down(uint64_t __x,
#if _GLIBCXX_SCALE_DOWN_FPU
               uint64_t /*_M_supremum*/, double _M_supremum_reciprocal)
#else
               uint64_t _M_supremum, double /*_M_supremum_reciprocal*/)
#endif
        {
#if _GLIBCXX_SCALE_DOWN_FPU
          return uint32_t(__x * _M_supremum_reciprocal);
#else
          return static_cast<uint32_t>(__x % _M_supremum);
#endif
        }

  public:
    /** @brief Default constructor. Seed with 0. */
    _RandomNumber()
    : _M_mt(0), _M_supremum(0x100000000ULL),
      _M_rand_sup(1ULL << std::numeric_limits<uint32_t>::digits),
      _M_supremum_reciprocal(double(_M_supremum) / double(_M_rand_sup)),
      _M_rand_sup_reciprocal(1.0 / double(_M_rand_sup)),
      __cache(0), __bits_left(0) { }
"""
        symbols, _ = await _parse(code)
        assert not [s for s in symbols if s.name == "static_cast"]
        scale = _by_name(symbols, "__scale_down")
        assert scale.qualified_name == "_RandomNumber.__scale_down"

    async def test_missing_identifier_is_not_a_name(self) -> None:
        # libstdc++ experimental/bits/simd.h: error recovery inserts a
        # zero-width MISSING identifier as a function name.
        code = """
  struct _SimdWrapper<bool, _Width,
              void_t<typename __bool_storage_member_type<_Width>::type>>
  {
    using _BuiltinType = typename __bool_storage_member_type<_Width>::type;
    using value_type = bool;

    static constexpr size_t _S_full_size = sizeof(_BuiltinType) * __CHAR_BIT__;

    _GLIBCXX_SIMD_INTRINSIC constexpr _SimdWrapper<bool, _S_full_size>
    __as_full_vector() const
    { return _M_data; }

    _GLIBCXX_SIMD_INTRINSIC constexpr
    _SimdWrapper() = default;

    _GLIBCXX_SIMD_INTRINSIC constexpr
    _SimdWrapper(_BuiltinType __k) : _M_data(__k) {};

    _GLIBCXX_SIMD_INTRINSIC
    operator const _BuiltinType&() const
    { return _M_data; }

    _GLIBCXX_SIMD_INTRINSIC
    operator _BuiltinType&()
    { return _M_data; }
"""
        symbols, _ = await _parse(code)
        assert all(s.name.strip() for s in symbols), [
            (s.kind, s.name, s.qualified_name) for s in symbols
        ]

    async def test_template_keyword_call_without_template_args(self) -> None:
        code = """
void f() {
    X::template g(a);
    Y::template h<int>(b);
}
"""
        _, refs = await _parse(code)
        calls = {r.reference_text for r in refs if r.reference_type == "call"}
        assert {"g", "h"} <= calls
