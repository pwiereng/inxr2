"""Tests for TreeSitterService adapter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestTreeSitterService:
    """Tests for TreeSitterService parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    def test_supports_python(self, parser_service: TreeSitterService) -> None:
        """Test that Python is supported."""
        assert parser_service.supports_language("python")
        assert parser_service.supports_language("Python")
        assert parser_service.supports_language("PYTHON")

    def test_supports_typescript(self, parser_service: TreeSitterService) -> None:
        """Test that TypeScript is supported."""
        assert parser_service.supports_language("typescript")
        assert parser_service.supports_language("TypeScript")

    def test_supports_javascript(self, parser_service: TreeSitterService) -> None:
        """Test that JavaScript is supported."""
        assert parser_service.supports_language("javascript")
        assert parser_service.supports_language("JavaScript")

    def test_supports_cpp(self, parser_service: TreeSitterService) -> None:
        """Test that C++ is supported."""
        assert parser_service.supports_language("cpp")
        assert parser_service.supports_language("Cpp")
        assert parser_service.supports_language("CPP")

    def test_unsupported_language(self, parser_service: TreeSitterService) -> None:
        """Test that unsupported languages are rejected."""
        assert not parser_service.supports_language("rust")
        assert not parser_service.supports_language("kotlin")


class TestPythonParsing:
    """Tests for Python parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a simple function definition."""
        code = '''
def hello_world():
    """Say hello."""
    print("Hello, World!")
'''
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find the function
        func_symbols = [s for s in symbols if s["name"] == "hello_world"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_parse_class_with_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a class with methods."""
        code = '''
class Calculator:
    """A simple calculator."""

    def __init__(self, value=0):
        self.value = value

    def add(self, x):
        """Add x to value."""
        self.value += x
        return self.value

    def subtract(self, x):
        self.value -= x
        return self.value
'''
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find the class
        class_symbols = [s for s in symbols if s["name"] == "Calculator"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["kind"] == "class"

        # Should find methods
        method_names = [s["name"] for s in symbols if s["kind"] == "method"]
        assert "__init__" in method_names
        assert "add" in method_names
        assert "subtract" in method_names

    @pytest.mark.asyncio
    async def test_parse_imports(self, parser_service: TreeSitterService) -> None:
        """Test parsing import statements."""
        code = """
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find import references
        import_refs = [r for r in references if r["type"] == "import"]
        import_texts = [r["text"] for r in import_refs]

        assert "os" in import_texts
        assert "sys" in import_texts
        assert "Path" in import_texts
        assert "List" in import_texts
        assert "Dict" in import_texts
        assert "Optional" in import_texts

    @pytest.mark.asyncio
    async def test_parse_constants(self, parser_service: TreeSitterService) -> None:
        """Test parsing constants (UPPER_CASE variables)."""
        code = """
MAX_SIZE = 1000
DEFAULT_NAME = "test"
BUFFER_SIZE = 4096
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find constants
        const_symbols = [s for s in symbols if s["kind"] == "constant"]
        const_names = [s["name"] for s in const_symbols]

        assert "MAX_SIZE" in const_names
        assert "DEFAULT_NAME" in const_names
        assert "BUFFER_SIZE" in const_names

    @pytest.mark.asyncio
    async def test_parse_async_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing async function definition."""
        code = '''
async def fetch_data(url):
    """Fetch data from URL."""
    response = await http_client.get(url)
    return response.json()
'''
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find the async function
        func_symbols = [s for s in symbols if s["name"] == "fetch_data"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["kind"] == "function"


class TestTypeScriptParsing:
    """Tests for TypeScript parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_function(self, parser_service: TreeSitterService) -> None:
        """Test parsing a function declaration."""
        code = """
function greet(name: string): string {
    return `Hello, ${name}!`;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        func_symbols = [s for s in symbols if s["name"] == "greet"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_parse_arrow_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing arrow function."""
        code = """
export const add = (a: number, b: number): number => {
    return a + b;
};
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        func_symbols = [s for s in symbols if s["name"] == "add"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_parse_class(self, parser_service: TreeSitterService) -> None:
        """Test parsing class declaration."""
        code = """
export class UserService {
    private users: User[] = [];

    addUser(user: User): void {
        this.users.push(user);
    }

    getUser(id: string): User | undefined {
        return this.users.find(u => u.id === id);
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        class_symbols = [s for s in symbols if s["name"] == "UserService"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["kind"] == "class"

    @pytest.mark.asyncio
    async def test_parse_interface(self, parser_service: TreeSitterService) -> None:
        """Test parsing interface declaration."""
        code = """
export interface User {
    id: string;
    name: string;
    email: string;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        interface_symbols = [s for s in symbols if s["name"] == "User"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0]["kind"] == "interface"

    @pytest.mark.asyncio
    async def test_parse_type_alias(self, parser_service: TreeSitterService) -> None:
        """Test parsing type alias."""
        code = """
export type UserId = string;
export type UserMap = Record<string, User>;
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        type_symbols = [s for s in symbols if s["kind"] == "type"]
        type_names = [s["name"] for s in type_symbols]

        assert "UserId" in type_names
        assert "UserMap" in type_names

    @pytest.mark.asyncio
    async def test_parse_imports(self, parser_service: TreeSitterService) -> None:
        """Test parsing import statements."""
        code = """
import React from 'react';
import { useState, useEffect } from 'react';
import type { User } from './types';
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_texts = [r["text"] for r in import_refs]

        assert "React" in import_texts
        assert "useState" in import_texts
        assert "useEffect" in import_texts

    @pytest.mark.asyncio
    async def test_parse_constants(self, parser_service: TreeSitterService) -> None:
        """Test parsing constants."""
        code = """
export const MAX_RETRIES = 3;
export const API_URL = 'https://api.example.com';
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        const_symbols = [s for s in symbols if s["kind"] == "constant"]
        const_names = [s["name"] for s in const_symbols]

        assert "MAX_RETRIES" in const_names
        assert "API_URL" in const_names


class TestPythonNewSymbolTypes:
    """Tests for new Python symbol types (tree-sitter extraction)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_instance_variables(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing instance variables from __init__."""
        code = """
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
        self._password = None
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find instance variables
        instance_vars = [s for s in symbols if s["kind"] == "instance_variable"]
        var_names = [s["name"] for s in instance_vars]

        assert "name" in var_names
        assert "email" in var_names
        assert "_password" in var_names

        # Should have correct scope
        for var in instance_vars:
            assert var["scope"] == "User"

    @pytest.mark.asyncio
    async def test_parse_class_variables(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing class variables."""
        code = """
class Config:
    default_timeout: int = 30
    max_retries = 3
    enabled = True
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find class variables
        class_vars = [s for s in symbols if s["kind"] == "class_variable"]
        var_names = [s["name"] for s in class_vars]

        assert "default_timeout" in var_names
        assert "max_retries" in var_names
        assert "enabled" in var_names

    @pytest.mark.asyncio
    async def test_parse_class_constants(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing class constants (UPPER_CASE class variables)."""
        code = """
class Constants:
    MAX_SIZE = 1024
    DEFAULT_NAME = "test"
    TIMEOUT = 30
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find class constants
        class_consts = [s for s in symbols if s["kind"] == "class_constant"]
        const_names = [s["name"] for s in class_consts]

        assert "MAX_SIZE" in const_names
        assert "DEFAULT_NAME" in const_names
        assert "TIMEOUT" in const_names

    @pytest.mark.asyncio
    async def test_parse_properties(self, parser_service: TreeSitterService) -> None:
        """Test parsing @property decorators."""
        code = """
class Rectangle:
    def __init__(self, width, height):
        self._width = width
        self._height = height

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def area(self):
        return self._width * self._height
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find properties
        properties = [s for s in symbols if s["kind"] == "property"]
        prop_names = [s["name"] for s in properties]

        assert "width" in prop_names
        assert "height" in prop_names
        assert "area" in prop_names

    @pytest.mark.asyncio
    async def test_parse_staticmethod(self, parser_service: TreeSitterService) -> None:
        """Test parsing @staticmethod decorators."""
        code = """
class MathUtils:
    @staticmethod
    def add(a, b):
        return a + b

    @staticmethod
    def multiply(a, b):
        return a * b
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find static methods
        static_methods = [s for s in symbols if s["kind"] == "staticmethod"]
        method_names = [s["name"] for s in static_methods]

        assert "add" in method_names
        assert "multiply" in method_names

    @pytest.mark.asyncio
    async def test_parse_classmethod(self, parser_service: TreeSitterService) -> None:
        """Test parsing @classmethod decorators."""
        code = """
class Factory:
    @classmethod
    def create(cls, name):
        return cls(name)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        # Should find class methods
        class_methods = [s for s in symbols if s["kind"] == "classmethod"]
        method_names = [s["name"] for s in class_methods]

        assert "create" in method_names
        assert "from_dict" in method_names


class TestTypeScriptNewSymbolTypes:
    """Tests for new TypeScript symbol types (tree-sitter extraction)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_interface_properties(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing interface property definitions."""
        code = """
interface User {
    id: string;
    name: string;
    email: string;
    age?: number;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should find interface properties
        interface_props = [s for s in symbols if s["kind"] == "interface_property"]
        prop_names = [s["name"] for s in interface_props]

        assert "id" in prop_names
        assert "name" in prop_names
        assert "email" in prop_names
        assert "age" in prop_names

    @pytest.mark.asyncio
    async def test_parse_interface_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing interface method signatures."""
        code = """
interface Repository {
    find(id: string): User | null;
    findAll(): User[];
    save(user: User): void;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should find interface methods
        interface_methods = [s for s in symbols if s["kind"] == "interface_method"]
        method_names = [s["name"] for s in interface_methods]

        assert "find" in method_names
        assert "findAll" in method_names
        assert "save" in method_names

    @pytest.mark.asyncio
    async def test_parse_enum(self, parser_service: TreeSitterService) -> None:
        """Test parsing enum declarations."""
        code = """
enum Color {
    Red,
    Green,
    Blue
}

enum Status {
    Active = 'active',
    Inactive = 'inactive',
    Pending = 'pending'
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should find enums
        enums = [s for s in symbols if s["kind"] == "enum"]
        enum_names = [s["name"] for s in enums]

        assert "Color" in enum_names
        assert "Status" in enum_names

        # Should find enum members
        members = [s for s in symbols if s["kind"] == "enum_member"]
        member_names = [s["name"] for s in members]

        assert "Red" in member_names
        assert "Green" in member_names
        assert "Blue" in member_names
        assert "Active" in member_names
        assert "Inactive" in member_names
        assert "Pending" in member_names

    @pytest.mark.asyncio
    async def test_parse_class_fields(self, parser_service: TreeSitterService) -> None:
        """Test parsing class field definitions."""
        code = """
class Service {
    private apiKey: string;
    public name: string;
    protected data: any;
    readonly id: string;
    static count = 0;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should find various field types
        fields = [s for s in symbols if "field" in s["kind"]]
        field_names = [s["name"] for s in fields]

        assert "apiKey" in field_names
        assert "name" in field_names
        assert "data" in field_names
        assert "id" in field_names
        assert "count" in field_names

        # Check specific kinds
        static_fields = [s for s in symbols if s["kind"] == "static_field"]
        assert any(s["name"] == "count" for s in static_fields)

        readonly_fields = [s for s in symbols if s["kind"] == "readonly_field"]
        assert any(s["name"] == "id" for s in readonly_fields)

    @pytest.mark.asyncio
    async def test_parse_static_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing static method definitions."""
        code = """
class Utils {
    static formatDate(date: Date): string {
        return date.toISOString();
    }

    static parseNumber(value: string): number {
        return parseInt(value, 10);
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should find static methods
        static_methods = [s for s in symbols if s["kind"] == "staticmethod"]
        method_names = [s["name"] for s in static_methods]

        assert "formatDate" in method_names
        assert "parseNumber" in method_names


class TestUnsupportedLanguage:
    """Tests for unsupported language handling."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_unsupported_language_returns_empty(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that unsupported languages return empty results."""
        code = """
fn main() {
    println!("Hello, Rust!");
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="rust", file_path="test.rs"
        )

        assert symbols == []
        assert references == []


class TestCallReferenceExtraction:
    """Regression tests for call reference extraction (issue #72).

    These tests verify that function/method calls are correctly extracted
    as references with type=="call" from Python source code.
    """

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_simple_function_call_in_function_body(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that a simple function call inside a function body is extracted."""
        code = '''
def setup_logging(verbose, log_level):
    """Configure logging."""
    pass

def main():
    setup_logging(verbose, log_level)
'''
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_names = [r["text"] for r in call_refs]
        assert "setup_logging" in call_names

    @pytest.mark.asyncio
    async def test_function_call_inside_decorated_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test calls inside a heavily-decorated function (like Click CLI commands)."""
        code = '''
import click

def setup_logging(verbose, log_level):
    pass

@click.command()
@click.option("--verbose", is_flag=True)
@click.option("--log-level", default="INFO")
def cli(verbose, log_level):
    """CLI entry point."""
    setup_logging(verbose, log_level)
    do_work()
'''
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_names = [r["text"] for r in call_refs]
        assert "setup_logging" in call_names
        assert "do_work" in call_names

    @pytest.mark.asyncio
    async def test_method_call(self, parser_service: TreeSitterService) -> None:
        """Test that method calls (obj.method()) produce call references."""
        code = """
def process():
    result = client.fetch_data()
    result.transform()
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_names = [r["text"] for r in call_refs]
        assert "fetch_data" in call_names
        assert "transform" in call_names

    @pytest.mark.asyncio
    async def test_calls_inside_class_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that function calls inside class methods are extracted."""
        code = """
def helper():
    pass

class MyService:
    def execute(self):
        helper()
        self.validate()
        result = compute_value(42)
        return result
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_names = [r["text"] for r in call_refs]
        assert "helper" in call_names
        assert "validate" in call_names
        assert "compute_value" in call_names

    @pytest.mark.asyncio
    async def test_nested_calls(self, parser_service: TreeSitterService) -> None:
        """Test that nested function calls are all extracted."""
        code = """
def process():
    result = outer(inner(value))
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_names = [r["text"] for r in call_refs]
        assert "outer" in call_names
        assert "inner" in call_names

    @pytest.mark.asyncio
    async def test_call_reference_has_correct_line_info(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that call references have correct source line information."""
        code = """def main():
    setup_logging()
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        setup_ref = [r for r in call_refs if r["text"] == "setup_logging"]
        assert len(setup_ref) == 1
        assert setup_ref[0]["source_line"] == 2

    @pytest.mark.asyncio
    async def test_call_references_after_multibyte_characters(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regression test: references after multi-byte UTF-8 chars are correct.

        Tree-sitter uses byte offsets but _get_text was slicing a Python string
        by character index, causing corrupted reference text after non-ASCII
        characters like em-dashes (3 bytes, 1 character).
        """
        # The em-dash (—) is 3 bytes in UTF-8 but 1 character in Python
        code = '''def main():
    """Description \u2014 with em-dash."""
    setup_logging(verbose)
'''
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_names = [r["text"] for r in call_refs]
        assert (
            "setup_logging" in call_names
        ), f"Expected 'setup_logging' in call references but got: {call_names}"

    @pytest.mark.asyncio
    async def test_symbols_after_multibyte_characters(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regression test: symbol names are correct after multi-byte chars."""
        code = """# Comment with em-dash \u2014 here
def my_function():
    pass
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        func_names = [s["name"] for s in symbols if s["kind"] == "function"]
        assert (
            "my_function" in func_names
        ), f"Expected 'my_function' but got: {func_names}"


class TestTypeScriptNewExpression:
    """Tests for new_expression reference extraction in TypeScript (issue #145).

    Verifies that `new ClassName(...)` is indexed as a reference with
    type=="instantiation".
    """

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_new_simple_class(self, parser_service: TreeSitterService) -> None:
        """Test that `new Foo()` creates an instantiation reference to Foo."""
        code = """
class Foo {
    constructor() {}
}

function create() {
    const f = new Foo();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inst_refs = [r for r in references if r["type"] == "instantiation"]
        inst_names = [r["text"] for r in inst_refs]
        assert "Foo" in inst_names

    @pytest.mark.asyncio
    async def test_new_member_expression(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `new module.Foo()` creates an instantiation reference to Foo."""
        code = """
function create() {
    const f = new some.module.Foo();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inst_refs = [r for r in references if r["type"] == "instantiation"]
        inst_names = [r["text"] for r in inst_refs]
        assert "Foo" in inst_names

    @pytest.mark.asyncio
    async def test_new_builtin_excluded(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `new Map()` is excluded as a builtin."""
        code = """
function create() {
    const m = new Map();
    const s = new Set();
    const f = new MyClass();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inst_refs = [r for r in references if r["type"] == "instantiation"]
        inst_names = [r["text"] for r in inst_refs]
        # Map and Set are builtins and should be excluded
        assert "Map" not in inst_names
        assert "Set" not in inst_names
        # MyClass is not a builtin and should be included
        assert "MyClass" in inst_names

    @pytest.mark.asyncio
    async def test_new_expression_line_column(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that line and column numbers are correct for new expressions."""
        code = """function create() {
    const f = new Foo();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inst_refs = [r for r in references if r["type"] == "instantiation"]
        foo_ref = [r for r in inst_refs if r["text"] == "Foo"]
        assert len(foo_ref) == 1
        assert foo_ref[0]["source_line"] == 2
        assert foo_ref[0]["source_column"] == 18

    @pytest.mark.asyncio
    async def test_new_expression_not_confused_with_call(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `new Foo()` is 'instantiation', not 'call'."""
        code = """
function test() {
    const a = new Foo();
    const b = bar();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inst_refs = [r for r in references if r["type"] == "instantiation"]
        call_refs = [r for r in references if r["type"] == "call"]

        inst_names = [r["text"] for r in inst_refs]
        call_names = [r["text"] for r in call_refs]

        assert "Foo" in inst_names
        assert "Foo" not in call_names
        assert "bar" in call_names
        assert "bar" not in inst_names


class TestPythonNestedFunctions:
    """Tests for nested function extraction in Python (issue #43)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_nested_function_in_top_level_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that a nested function inside a top-level function is extracted."""
        code = """def outer():
    def inner():
        pass
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        func_names = [s["name"] for s in func_symbols]

        assert "outer" in func_names
        assert "inner" in func_names

        inner = next(s for s in func_symbols if s["name"] == "inner")
        assert inner["scope"] == "outer"
        assert inner["qualified_name"] == "outer.inner"

    @pytest.mark.asyncio
    async def test_nested_function_in_class_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that nested functions inside class methods are extracted."""
        code = """class MyClass:
    def extract(self):
        def process_item(node):
            pass
        def handle_error(e):
            pass
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        nested = [s for s in symbols if s["kind"] == "function"]
        nested_names = [s["name"] for s in nested]

        assert "process_item" in nested_names
        assert "handle_error" in nested_names

        process_item = next(s for s in nested if s["name"] == "process_item")
        assert process_item["scope"] == "MyClass.extract"
        assert process_item["qualified_name"] == "MyClass.extract.process_item"

        handle_error = next(s for s in nested if s["name"] == "handle_error")
        assert handle_error["scope"] == "MyClass.extract"
        assert handle_error["qualified_name"] == "MyClass.extract.handle_error"

    @pytest.mark.asyncio
    async def test_multiple_nested_functions_at_same_level(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test multiple nested functions at the same nesting level."""
        code = """def process():
    def validate(item):
        pass
    def transform(item):
        pass
    def save(item):
        pass
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        nested = [
            s for s in symbols if s["kind"] == "function" and s["scope"] == "process"
        ]
        nested_names = [s["name"] for s in nested]

        assert len(nested) == 3
        assert "validate" in nested_names
        assert "transform" in nested_names
        assert "save" in nested_names

    @pytest.mark.asyncio
    async def test_deeply_nested_functions(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test functions nested multiple levels deep."""
        code = """def level0():
    def level1():
        def level2():
            pass
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]

        level0 = next(s for s in func_symbols if s["name"] == "level0")
        assert level0["scope"] is None

        level1 = next(s for s in func_symbols if s["name"] == "level1")
        assert level1["scope"] == "level0"
        assert level1["qualified_name"] == "level0.level1"

        level2 = next(s for s in func_symbols if s["name"] == "level2")
        assert level2["scope"] == "level0.level1"
        assert level2["qualified_name"] == "level0.level1.level2"

    @pytest.mark.asyncio
    async def test_nested_function_with_decorator(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that decorated nested functions are extracted."""
        code = """def outer():
    @some_decorator
    def inner():
        pass
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        inner = next(s for s in func_symbols if s["name"] == "inner")
        assert inner["scope"] == "outer"
        assert inner["qualified_name"] == "outer.inner"

    @pytest.mark.asyncio
    async def test_nested_function_in_decorated_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test nested functions inside decorated class methods."""
        code = """class MyClass:
    @staticmethod
    def process():
        def helper():
            pass
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        helper = next(s for s in func_symbols if s["name"] == "helper")
        assert helper["scope"] == "MyClass.process"
        assert helper["qualified_name"] == "MyClass.process.helper"

    @pytest.mark.asyncio
    async def test_nested_function_inside_control_structure(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test nested function defined inside a control structure in a method."""
        code = """class Parser:
    def process(self, items):
        for item in items:
            if item.valid:
                def handle(x):
                    pass
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        handle = next(s for s in func_symbols if s["name"] == "handle")
        assert handle["scope"] == "Parser.process"
        assert handle["qualified_name"] == "Parser.process.handle"

    @pytest.mark.asyncio
    async def test_nested_function_coexists_with_instance_variables(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that nested functions and instance variables are both extracted."""
        code = """class Service:
    def __init__(self, config):
        self.config = config
        self._cache = {}

        def build_key(item):
            return str(item)

        self._key_builder = build_key
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )

        instance_vars = [s for s in symbols if s["kind"] == "instance_variable"]
        var_names = [s["name"] for s in instance_vars]
        assert "config" in var_names
        assert "_cache" in var_names
        assert "_key_builder" in var_names

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        build_key = next(s for s in func_symbols if s["name"] == "build_key")
        assert build_key["scope"] == "Service.__init__"
        assert build_key["qualified_name"] == "Service.__init__.build_key"


class TestSelfAttributeReferences:
    """Tests for self.x usage references (issue #162).

    Verifies that reading self.x in methods generates usage references
    back to the instance variable symbol.
    """

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_self_read_generates_usage_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.x read in a method creates a usage reference."""
        code = """
class MyClass:
    def __init__(self):
        self.name = "test"

    def get_name(self):
        return self.name
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["type"] == "usage" and r["text"] == "name"]
        assert len(usage_refs) == 1

    @pytest.mark.asyncio
    async def test_self_assignment_not_duplicated_as_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.x = value does NOT create a usage reference."""
        code = """
class MyClass:
    def __init__(self):
        self.name = "test"
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["type"] == "usage" and r["text"] == "name"]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_self_method_call_not_duplicated(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.method() is 'call', not also 'usage'."""
        code = """
class MyClass:
    def validate(self):
        pass

    def process(self):
        self.validate()
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        call_refs = [r for r in refs if r["type"] == "call" and r["text"] == "validate"]
        usage_refs = [
            r for r in refs if r["type"] == "usage" and r["text"] == "validate"
        ]
        assert len(call_refs) == 1
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_self_augmented_assignment_creates_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.count += 1 creates a usage reference (read + write)."""
        code = """
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["type"] == "usage" and r["text"] == "count"]
        assert len(usage_refs) == 1

    @pytest.mark.asyncio
    async def test_self_read_in_expression(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.x used in expressions creates usage references."""
        code = """
class MyClass:
    def __init__(self):
        self.value = 10

    def compute(self):
        result = self.value * 2
        return result
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["type"] == "usage" and r["text"] == "value"]
        assert len(usage_refs) == 1

    @pytest.mark.asyncio
    async def test_self_read_as_argument(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.x passed as argument creates usage reference."""
        code = """
class MyClass:
    def __init__(self):
        self.name = "test"

    def display(self):
        do_something(self.name)
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["type"] == "usage" and r["text"] == "name"]
        assert len(usage_refs) == 1

    @pytest.mark.asyncio
    async def test_multiple_self_reads_in_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that multiple self.x reads each create a usage reference."""
        code = """
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def distance(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        x_usages = [r for r in refs if r["type"] == "usage" and r["text"] == "x"]
        y_usages = [r for r in refs if r["type"] == "usage" and r["text"] == "y"]
        assert len(x_usages) == 1
        assert len(y_usages) == 1

    @pytest.mark.asyncio
    async def test_self_tuple_unpacking_not_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.x in tuple unpacking LHS is not a usage reference."""
        code = """
class MyClass:
    def update(self):
        self.x, self.y = get_coords()
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        x_usages = [r for r in refs if r["type"] == "usage" and r["text"] == "x"]
        y_usages = [r for r in refs if r["type"] == "usage" and r["text"] == "y"]
        assert len(x_usages) == 0
        assert len(y_usages) == 0

    @pytest.mark.asyncio
    async def test_self_for_loop_target_not_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.x as for-loop target is not a usage reference."""
        code = """
class MyClass:
    def load(self):
        for self.item in items:
            pass
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["type"] == "usage" and r["text"] == "item"]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_self_del_not_usage(self, parser_service: TreeSitterService) -> None:
        """Test that del self.x is not a usage reference."""
        code = """
class MyClass:
    def cleanup(self):
        del self.cache
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["type"] == "usage" and r["text"] == "cache"]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_self_with_as_target_not_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that 'with expr as self.x' is not a usage reference."""
        code = """
class MyClass:
    def run(self):
        with open("f") as self.handle:
            pass
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["type"] == "usage" and r["text"] == "handle"]
        assert len(usage_refs) == 0


class TestTypeScriptInheritanceReferences:
    """Tests for extends/implements inheritance reference extraction (issue #161)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_class_extends(self, parser_service: TreeSitterService) -> None:
        """Test that `class Child extends Parent` creates an inheritance reference."""
        code = """
class Parent {
    greet() {}
}

class Child extends Parent {
    sayHi() {}
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "Parent" in inherit_names

    @pytest.mark.asyncio
    async def test_class_implements(self, parser_service: TreeSitterService) -> None:
        """Test that `class Impl implements IFoo` creates an inheritance reference."""
        code = """
interface IFoo {
    doStuff(): void;
}

class Impl implements IFoo {
    doStuff() {}
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "IFoo" in inherit_names

    @pytest.mark.asyncio
    async def test_class_extends_and_implements_multiple(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test multi-heritage: extends Base implements IFoo, IBar."""
        code = """
class Multi extends Base implements IFoo, IBar {
    doStuff() {}
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "Base" in inherit_names
        assert "IFoo" in inherit_names
        assert "IBar" in inherit_names

    @pytest.mark.asyncio
    async def test_class_extends_builtin_excluded(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that extending builtins like Error doesn't create a reference."""
        code = """
class CustomError extends Error {
    constructor(message: string) {
        super(message);
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "Error" not in inherit_names

    @pytest.mark.asyncio
    async def test_class_extends_scope(self, parser_service: TreeSitterService) -> None:
        """Test that inheritance reference has correct scope (the child class name)."""
        code = """
class Child extends Parent {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        parent_ref = next(r for r in inherit_refs if r["text"] == "Parent")
        assert parent_ref["scope"] == "Child"

    @pytest.mark.asyncio
    async def test_javascript_class_extends(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that JS class extends creates inheritance reference."""
        code = """
class Child extends Parent {
    constructor() {
        super();
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "Parent" in inherit_names

    @pytest.mark.asyncio
    async def test_inheritance_not_duplicated_as_type_annotation(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that extends/implements refs are not also emitted as type_annotation."""
        code = """
class Child extends Parent implements IFoo {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should have inheritance refs
        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        assert len(inherit_refs) >= 2

        # Parent should NOT also appear as type_annotation
        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_names = [r["text"] for r in type_refs]
        assert "Parent" not in type_names

    @pytest.mark.asyncio
    async def test_namespaced_extends(self, parser_service: TreeSitterService) -> None:
        """Test that `extends ns.Parent` creates an inheritance reference to Parent."""
        code = """
class Child extends ns.Parent {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "Parent" in inherit_names

        # Parent should NOT also appear as a usage reference
        usage_refs = [
            r for r in references if r["type"] == "usage" and r["text"] == "Parent"
        ]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_deeply_namespaced_extends_no_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `extends ns.sub.Parent` does not emit usage refs for nested parts."""
        code = """
class Child extends ns.sub.Parent {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "Parent" in inherit_names

        # Neither sub nor Parent should appear as usage references
        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "sub" not in usage_names
        assert "Parent" not in usage_names

    @pytest.mark.asyncio
    async def test_generic_implements(self, parser_service: TreeSitterService) -> None:
        """Test `implements IFoo<Bar>`: IFoo is inheritance, not type_annotation; Bar is type_annotation."""
        code = """
class Impl implements IFoo<Bar> {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "IFoo" in inherit_names

        # IFoo should NOT also appear as type_annotation
        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_names = [r["text"] for r in type_refs]
        assert "IFoo" not in type_names
        # But the type argument Bar should still be captured as a type_annotation
        assert "Bar" in type_names

    @pytest.mark.asyncio
    async def test_anonymous_class_extends(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `export default class extends Base` creates an inheritance reference."""
        code = """
export default class extends Base {
    doStuff() {}
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "Base" in inherit_names

    @pytest.mark.asyncio
    async def test_class_expression_extends(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `const X = class extends Base {}` creates an inheritance reference."""
        code = """
const X = class extends Base {};
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        inherit_names = [r["text"] for r in inherit_refs]
        assert "Base" in inherit_names


class TestTypeScriptMemberAccessReferences:
    """Tests for property read (obj.field) reference extraction (issue #161)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_property_read(self, parser_service: TreeSitterService) -> None:
        """Test that `obj.field` creates a usage reference to 'field'."""
        code = """
function test() {
    const x = obj.field;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "field" in usage_names

    @pytest.mark.asyncio
    async def test_method_call_not_duplicated(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `obj.method()` is 'call', NOT also 'usage'."""
        code = """
function test() {
    obj.method();
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_names = [r["text"] for r in call_refs]
        assert "method" in call_names

        # Should NOT also have a usage reference for the same method
        usage_refs = [
            r for r in references if r["type"] == "usage" and r["text"] == "method"
        ]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_new_expression_not_duplicated(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `new some.Foo()` is 'instantiation', NOT also 'usage'."""
        code = """
function test() {
    const f = new some.Foo();
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inst_refs = [r for r in references if r["type"] == "instantiation"]
        inst_names = [r["text"] for r in inst_refs]
        assert "Foo" in inst_names

        usage_refs = [
            r for r in references if r["type"] == "usage" and r["text"] == "Foo"
        ]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_chained_property_access(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `a.b.c` creates usage references for accessed properties."""
        code = """
function test() {
    const x = a.b.c;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "b" in usage_names
        assert "c" in usage_names

    @pytest.mark.asyncio
    async def test_javascript_property_read(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that JS property access creates usage references."""
        code = """
function test() {
    const x = config.value;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "value" in usage_names
