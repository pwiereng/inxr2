"""Tests for unified C/C++ language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService

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
