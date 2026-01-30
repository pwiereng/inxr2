"""Tests for C language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestCSupport:
    """Tests for C language support in TreeSitterService."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    def test_supports_c(self, parser_service: TreeSitterService) -> None:
        """Test that C is supported."""
        assert parser_service.supports_language("c")
        assert parser_service.supports_language("C")


class TestCFunctions:
    """Tests for C function parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a simple function definition."""
        code = """
int add(int a, int b) {
    return a + b;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        func_symbols = [s for s in symbols if s["name"] == "add"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_parse_void_function(self, parser_service: TreeSitterService) -> None:
        """Test parsing a void function."""
        code = """
void print_hello(void) {
    printf("Hello\\n");
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        func_symbols = [s for s in symbols if s["name"] == "print_hello"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_parse_function_with_pointer_return(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a function returning a pointer."""
        code = """
char* get_message(void) {
    return "Hello";
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        func_symbols = [s for s in symbols if s["name"] == "get_message"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_parse_function_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing function declarations/prototypes."""
        code = """
int calculate(int x, int y);
void process(void);
char* get_name(const char* prefix);
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.h"
        )

        func_names = [s["name"] for s in symbols if s["kind"] == "function"]
        assert "calculate" in func_names
        assert "process" in func_names
        assert "get_name" in func_names


class TestCStructs:
    """Tests for C struct parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_struct(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple struct."""
        code = """
struct Point {
    int x;
    int y;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0]["name"] == "Point"

        # Check fields
        fields = [s for s in symbols if s["kind"] == "struct_field"]
        field_names = [s["name"] for s in fields]
        assert "x" in field_names
        assert "y" in field_names

    @pytest.mark.asyncio
    async def test_parse_struct_with_pointer_fields(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a struct with pointer fields."""
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

        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0]["name"] == "Node"

        fields = [s for s in symbols if s["kind"] == "struct_field"]
        field_names = [s["name"] for s in fields]
        assert "value" in field_names
        assert "next" in field_names
        assert "name" in field_names

    @pytest.mark.asyncio
    async def test_parse_struct_with_array_fields(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a struct with array fields."""
        code = """
struct Buffer {
    char data[256];
    int size;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        fields = [s for s in symbols if s["kind"] == "struct_field"]
        field_names = [s["name"] for s in fields]
        assert "data" in field_names
        assert "size" in field_names

    @pytest.mark.asyncio
    async def test_struct_field_scope(self, parser_service: TreeSitterService) -> None:
        """Test that struct fields have correct scope."""
        code = """
struct Person {
    char* name;
    int age;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        fields = [s for s in symbols if s["kind"] == "struct_field"]
        for field in fields:
            assert field["scope"] == "Person"
            assert field["qualified_name"].startswith("Person.")


class TestCUnions:
    """Tests for C union parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_union(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple union."""
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

        union_symbols = [s for s in symbols if s["kind"] == "union"]
        assert len(union_symbols) == 1
        assert union_symbols[0]["name"] == "Data"

        # Check fields
        fields = [s for s in symbols if s["kind"] == "union_field"]
        field_names = [s["name"] for s in fields]
        assert "i" in field_names
        assert "f" in field_names
        assert "c" in field_names

    @pytest.mark.asyncio
    async def test_union_field_scope(self, parser_service: TreeSitterService) -> None:
        """Test that union fields have correct scope."""
        code = """
union Value {
    int as_int;
    double as_double;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        fields = [s for s in symbols if s["kind"] == "union_field"]
        for field in fields:
            assert field["scope"] == "Value"


class TestCEnums:
    """Tests for C enum parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_enum(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple enum."""
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

        enum_symbols = [s for s in symbols if s["kind"] == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0]["name"] == "Color"

        # Check enum values
        values = [s for s in symbols if s["kind"] == "enum_value"]
        value_names = [s["name"] for s in values]
        assert "RED" in value_names
        assert "GREEN" in value_names
        assert "BLUE" in value_names

    @pytest.mark.asyncio
    async def test_parse_enum_with_values(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing an enum with explicit values."""
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

        values = [s for s in symbols if s["kind"] == "enum_value"]
        value_names = [s["name"] for s in values]
        assert "OK" in value_names
        assert "ERROR" in value_names
        assert "PENDING" in value_names

    @pytest.mark.asyncio
    async def test_enum_value_scope(self, parser_service: TreeSitterService) -> None:
        """Test that enum values have correct scope."""
        code = """
enum Direction {
    NORTH,
    SOUTH
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        values = [s for s in symbols if s["kind"] == "enum_value"]
        for value in values:
            assert value["scope"] == "Direction"


class TestCTypedefs:
    """Tests for C typedef parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_typedef(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a simple typedef."""
        code = """
typedef int Integer;
typedef unsigned char Byte;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        typedef_symbols = [s for s in symbols if s["kind"] == "typedef"]
        typedef_names = [s["name"] for s in typedef_symbols]
        assert "Integer" in typedef_names
        assert "Byte" in typedef_names

    @pytest.mark.asyncio
    async def test_parse_typedef_struct(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a typedef for a struct."""
        code = """
typedef struct {
    int x;
    int y;
} Point;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        typedef_symbols = [s for s in symbols if s["kind"] == "typedef"]
        typedef_names = [s["name"] for s in typedef_symbols]
        assert "Point" in typedef_names

    @pytest.mark.asyncio
    async def test_parse_typedef_pointer(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a typedef for a pointer."""
        code = """
typedef char* String;
typedef void* Pointer;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        typedef_symbols = [s for s in symbols if s["kind"] == "typedef"]
        typedef_names = [s["name"] for s in typedef_symbols]
        assert "String" in typedef_names
        assert "Pointer" in typedef_names

    @pytest.mark.asyncio
    async def test_parse_typedef_function_pointer(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a typedef for a function pointer."""
        code = """
typedef int (*Comparator)(const void*, const void*);
typedef void (*Callback)(int);
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        typedef_symbols = [s for s in symbols if s["kind"] == "typedef"]
        typedef_names = [s["name"] for s in typedef_symbols]
        assert "Comparator" in typedef_names
        assert "Callback" in typedef_names


class TestCMacros:
    """Tests for C macro parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_constant_macro(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing constant #define macros."""
        code = """
#define MAX_SIZE 100
#define PI 3.14159
#define VERSION "1.0.0"
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        macro_symbols = [s for s in symbols if s["kind"] == "macro"]
        macro_names = [s["name"] for s in macro_symbols]
        assert "MAX_SIZE" in macro_names
        assert "PI" in macro_names
        assert "VERSION" in macro_names

    @pytest.mark.asyncio
    async def test_parse_function_like_macro(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing function-like #define macros."""
        code = """
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define SQUARE(x) ((x) * (x))
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        macro_symbols = [s for s in symbols if s["kind"] == "macro"]
        macro_names = [s["name"] for s in macro_symbols]
        assert "MAX" in macro_names
        assert "MIN" in macro_names
        assert "SQUARE" in macro_names

    @pytest.mark.asyncio
    async def test_parse_empty_macro(self, parser_service: TreeSitterService) -> None:
        """Test parsing empty #define macros (flags)."""
        code = """
#define DEBUG
#define FEATURE_ENABLED
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        macro_symbols = [s for s in symbols if s["kind"] == "macro"]
        macro_names = [s["name"] for s in macro_symbols]
        assert "DEBUG" in macro_names
        assert "FEATURE_ENABLED" in macro_names


class TestCGlobalVariables:
    """Tests for C global variable parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_global_variables(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing global variables."""
        code = """
int counter;
static float rate = 0.5;
char buffer[256];
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "counter" in var_names
        assert "rate" in var_names
        assert "buffer" in var_names

    @pytest.mark.asyncio
    async def test_parse_pointer_variables(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing pointer variables."""
        code = """
int* ptr;
char* message = "Hello";
void* data;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "ptr" in var_names
        assert "message" in var_names
        assert "data" in var_names


class TestCReferences:
    """Tests for C reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_include_statements(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing #include statements."""
        code = """
#include <stdio.h>
#include <stdlib.h>
#include "myheader.h"
#include "utils/helper.h"
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        include_refs = [r for r in references if r["type"] == "include"]
        include_texts = [r["text"] for r in include_refs]
        assert "stdio.h" in include_texts
        assert "stdlib.h" in include_texts
        assert "myheader.h" in include_texts
        assert "utils/helper.h" in include_texts

    @pytest.mark.asyncio
    async def test_parse_function_calls(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing function calls."""
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

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        assert "initialize" in call_texts
        assert "calculate" in call_texts
        assert "cleanup" in call_texts

    @pytest.mark.asyncio
    async def test_builtin_calls_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that standard library calls are filtered out."""
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

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        # Builtins should be filtered
        assert "printf" not in call_texts
        assert "malloc" not in call_texts
        # Custom function should remain
        assert "my_function" in call_texts

    @pytest.mark.asyncio
    async def test_parse_type_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing type references."""
        code = """
void process(Point p, Node* n) {
    MyStruct s;
    CustomType* ptr;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        assert "Point" in type_texts
        assert "Node" in type_texts
        assert "MyStruct" in type_texts
        assert "CustomType" in type_texts

    @pytest.mark.asyncio
    async def test_primitive_types_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that primitive types are filtered from references."""
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

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        # Primitives should be filtered
        assert "int" not in type_texts
        assert "char" not in type_texts
        assert "float" not in type_texts
        assert "double" not in type_texts
        # Custom type should remain
        assert "MyType" in type_texts

    @pytest.mark.asyncio
    async def test_sizeof_type_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that sizeof(TypeName) extracts type references."""
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

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        # sizeof(TypeName) should extract type references
        assert "MyState" in type_texts
        assert "OtherState" in type_texts

    @pytest.mark.asyncio
    async def test_initializer_list_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that identifiers in initializer lists are captured as references."""
        code = """
FuncTable table[] = {
    { handler1, callback1, 0 },
    { handler2, callback2, 0 }
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_texts = [r["text"] for r in usage_refs]
        # Function pointers in initializer should be captured
        assert "handler1" in usage_texts
        assert "callback1" in usage_texts
        assert "handler2" in usage_texts
        assert "callback2" in usage_texts

    @pytest.mark.asyncio
    async def test_field_access_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that struct field accesses are captured as references."""
        code = """
void test(void) {
    config.numberOfNodes = 256;
    ptr->fieldName = 0;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_texts = [r["text"] for r in usage_refs]
        # Both base objects and fields should be captured (dot and arrow operators)
        assert "config" in usage_texts
        assert "numberOfNodes" in usage_texts
        assert "ptr" in usage_texts
        assert "fieldName" in usage_texts


class TestCEdgeCases:
    """Tests for edge cases in C parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_forward_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing forward struct declarations."""
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

        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        # Should find at least the full definition
        assert any(s["name"] == "Node" for s in struct_symbols)

    @pytest.mark.asyncio
    async def test_parse_nested_struct(self, parser_service: TreeSitterService) -> None:
        """Test parsing with nested anonymous structs."""
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

        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        # Should find the outer struct
        assert any(s["name"] == "Container" for s in struct_symbols)

    @pytest.mark.asyncio
    async def test_parse_complex_typedef(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing complex typedef with struct."""
        code = """
typedef struct ListNode {
    int data;
    struct ListNode* next;
} ListNode;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        # Should find both struct and typedef
        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        typedef_symbols = [s for s in symbols if s["kind"] == "typedef"]

        assert any(s["name"] == "ListNode" for s in struct_symbols)
        assert any(s["name"] == "ListNode" for s in typedef_symbols)

    @pytest.mark.asyncio
    async def test_parse_static_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing static functions."""
        code = """
static int helper(int x) {
    return x * 2;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        func_symbols = [s for s in symbols if s["name"] == "helper"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_parse_header_file(self, parser_service: TreeSitterService) -> None:
        """Test parsing a typical header file."""
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

        # Should find macros
        macro_symbols = [s for s in symbols if s["kind"] == "macro"]
        macro_names = [s["name"] for s in macro_symbols]
        assert "MYLIB_H" in macro_names
        assert "MAX_ITEMS" in macro_names

        # Should find typedef
        typedef_symbols = [s for s in symbols if s["kind"] == "typedef"]
        assert any(s["name"] == "Item" for s in typedef_symbols)

        # Should find function declarations
        func_symbols = [s for s in symbols if s["kind"] == "function"]
        func_names = [s["name"] for s in func_symbols]
        assert "create_item" in func_names
        assert "destroy_item" in func_names

        # Should find include
        include_refs = [r for r in references if r["type"] == "include"]
        assert any(r["text"] == "stdint.h" for r in include_refs)

    @pytest.mark.asyncio
    async def test_parse_function_pointer_field(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing struct with function pointer field."""
        code = """
struct Handler {
    int (*process)(void* data);
    void (*cleanup)(void);
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="c", file_path="test.c"
        )

        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        assert any(s["name"] == "Handler" for s in struct_symbols)

        # Verify function pointer fields are extracted
        fields = [s for s in symbols if s["kind"] == "struct_field"]
        field_names = [s["name"] for s in fields]
        assert "process" in field_names
        assert "cleanup" in field_names

        # Verify scope is set correctly
        for field in fields:
            assert field["scope"] == "Handler"

    @pytest.mark.asyncio
    async def test_parse_extern_c_block(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing content inside extern C blocks (common in C++ compatible headers)."""
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

        # Should find macros including header guard
        macro_symbols = [s for s in symbols if s["kind"] == "macro"]
        macro_names = [s["name"] for s in macro_symbols]
        assert "MY_HEADER_H" in macro_names

        # Should find struct inside extern "C" block
        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        struct_names = [s["name"] for s in struct_symbols]
        assert "_MyStruct" in struct_names

        # Should find struct fields
        fields = [s for s in symbols if s["kind"] == "struct_field"]
        field_names = [s["name"] for s in fields]
        assert "x" in field_names
        assert "y" in field_names

        # Should find typedef
        typedef_symbols = [s for s in symbols if s["kind"] == "typedef"]
        typedef_names = [s["name"] for s in typedef_symbols]
        assert "MyStruct" in typedef_names

        # Should find function declarations inside extern "C" block
        func_symbols = [s for s in symbols if s["kind"] == "function"]
        func_names = [s["name"] for s in func_symbols]
        assert "my_function" in func_names
        assert "another_function" in func_names

    @pytest.mark.asyncio
    async def test_parse_variable_usage_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that variable usages in field expressions are tracked as references."""
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

        # Should find the globals variable definition
        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        assert any(s["name"] == "globals" for s in var_symbols)

        # Should find usage references to globals
        usage_refs = [r for r in references if r["type"] == "usage"]
        globals_usages = [r for r in usage_refs if r["text"] == "globals"]

        # globals is used 5 times in field expressions:
        # init(): globals.debugLevel, globals.running
        # get_debug_level(): globals.debugLevel
        # process(): globals.running, globals.config
        assert len(globals_usages) == 5

        # Verify line numbers are correct
        usage_lines = sorted([r["source_line"] for r in globals_usages])
        assert 11 in usage_lines  # globals.debugLevel = 1
        assert 12 in usage_lines  # globals.running = 1
        assert 16 in usage_lines  # return globals.debugLevel
        assert 20 in usage_lines  # if (globals.running)
        assert 21 in usage_lines  # printf("%s", globals.config)
