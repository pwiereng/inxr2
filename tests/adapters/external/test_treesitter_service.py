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


class TestInstanceVariableColumnPositions:
    """Tests for instance variable symbol column positions (issue #169).

    Verifies that start_column points to the attribute name (e.g., _bar),
    not to 'self' in self._bar assignments.
    """

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_instance_variable_start_column_points_to_attr_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that instance variable start_column points to attr name, not self."""
        code = """class Foo:
    def __init__(self):
        self._bar = 42
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        ivar = [
            s
            for s in symbols
            if s["name"] == "_bar" and s["kind"] == "instance_variable"
        ]
        assert len(ivar) == 1
        # "        self._bar = 42"
        #  01234567890123
        # self starts at col 8, _bar starts at col 13
        assert ivar[0]["start_column"] == 13

    @pytest.mark.asyncio
    async def test_instance_variable_end_column_matches_attr_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that instance variable end_column covers only the attr name."""
        code = """class Foo:
    def __init__(self):
        self._bar = 42
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        ivar = [
            s
            for s in symbols
            if s["name"] == "_bar" and s["kind"] == "instance_variable"
        ]
        assert len(ivar) == 1
        # _bar ends at col 17 (13 + len("_bar"))
        assert ivar[0]["end_column"] == 17

    @pytest.mark.asyncio
    async def test_usage_reference_column_points_to_attr_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that self.x usage reference column points to attr name."""
        code = """class Foo:
    def __init__(self):
        self._bar = 42
    def method(self):
        return self._bar
"""
        _, refs = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_refs = [r for r in refs if r["text"] == "_bar" and r["type"] == "usage"]
        assert len(usage_refs) == 1
        # "        return self._bar"
        #  0123456789012345678
        # self starts at col 15, _bar starts at col 20
        assert usage_refs[0]["source_column"] == 20

    @pytest.mark.asyncio
    async def test_multiple_instance_variables_not_duplicated(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that each instance variable appears exactly once."""
        code = """class Foo:
    def __init__(self):
        self._x = 1
        self._y = 2
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        ivars = [s for s in symbols if s["kind"] == "instance_variable"]
        names = [s["name"] for s in ivars]
        assert "_x" in names
        assert "_y" in names
        assert names.count("_x") == 1
        assert names.count("_y") == 1


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


class TestClassExpressionSymbols:
    """Tests for class expression symbol extraction (issue #190).

    Class expressions like `module.exports = class Foo { ... }` and
    `const X = class { ... }` should be indexed as class symbols with
    their methods properly scoped.
    """

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_module_exports_class_expression(
        self, parser_service: TreeSitterService
    ) -> None:
        """module.exports = class Foo { ... } indexes Foo as a class with methods."""
        code = """
module.exports = class JiminnyApiClient {
    constructor(args = {}) { }
    fetchContent() { }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["name"] == "JiminnyApiClient"

        methods = [s for s in symbols if s["kind"] == "method"]
        method_names = {s["name"] for s in methods}
        assert "constructor" in method_names
        assert "fetchContent" in method_names
        # Methods should be scoped to the class
        for m in methods:
            assert m["scope"] == "JiminnyApiClient"

    @pytest.mark.asyncio
    async def test_const_class_expression(
        self, parser_service: TreeSitterService
    ) -> None:
        """const X = class { ... } indexes X as a class with methods."""
        code = """
const MyClass = class {
    method() { }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["name"] == "MyClass"

        methods = [s for s in symbols if s["kind"] == "method"]
        assert len(methods) == 1
        assert methods[0]["name"] == "method"
        assert methods[0]["scope"] == "MyClass"

    @pytest.mark.asyncio
    async def test_exports_dot_class_expression(
        self, parser_service: TreeSitterService
    ) -> None:
        """exports.Foo = class Foo { ... } indexes Foo as a class."""
        code = """
exports.MyClass = class MyClass {
    bar() { }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["name"] == "MyClass"

        methods = [s for s in symbols if s["kind"] == "method"]
        assert len(methods) == 1
        assert methods[0]["name"] == "bar"
        assert methods[0]["scope"] == "MyClass"

    @pytest.mark.asyncio
    async def test_exports_dot_class_expression_aliased(
        self, parser_service: TreeSitterService
    ) -> None:
        """exports.Foo = class Bar { ... } uses LHS name Foo, not RHS name Bar."""
        code = """
exports.Foo = class Bar {
    baz() { }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["name"] == "Foo"

        methods = [s for s in symbols if s["kind"] == "method"]
        assert len(methods) == 1
        assert methods[0]["scope"] == "Foo"

    @pytest.mark.asyncio
    async def test_non_export_assignment_ignored(
        self, parser_service: TreeSitterService
    ) -> None:
        """foo.bar = class { ... } should not create a top-level class symbol."""
        code = """
foo.bar = class {
    baz() { }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        assert len(class_symbols) == 0

    @pytest.mark.asyncio
    async def test_module_exports_function_expression(
        self, parser_service: TreeSitterService
    ) -> None:
        """module.exports = function foo() {} indexes foo as a function."""
        code = """
module.exports = function createServer() { }
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        fn_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(fn_symbols) == 1
        assert fn_symbols[0]["name"] == "createServer"

    @pytest.mark.asyncio
    async def test_exports_dot_function_expression(
        self, parser_service: TreeSitterService
    ) -> None:
        """exports.Foo = function Bar() {} uses LHS name Foo."""
        code = """
exports.create = function createImpl() { }
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        fn_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(fn_symbols) == 1
        assert fn_symbols[0]["name"] == "create"

    @pytest.mark.asyncio
    async def test_exports_dot_anonymous_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """exports.Foo = function() {} uses LHS name Foo."""
        code = """
exports.handler = function() { }
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        fn_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(fn_symbols) == 1
        assert fn_symbols[0]["name"] == "handler"

    @pytest.mark.asyncio
    async def test_class_expression_with_fields(
        self, parser_service: TreeSitterService
    ) -> None:
        """Class expression fields should be indexed with proper scope."""
        code = """
const Widget = class {
    static count = 0;
    render() { }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["name"] == "Widget"

        static_fields = [s for s in symbols if s["kind"] == "static_field"]
        assert any(s["name"] == "count" for s in static_fields)
        assert all(s["scope"] == "Widget" for s in static_fields)

    @pytest.mark.asyncio
    async def test_class_expression_inherits_scope_for_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Inheritance references from class expressions should have correct scope."""
        code = """
const Child = class extends Parent {
    greet() {}
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        inherit_refs = [r for r in references if r["type"] == "inheritance"]
        assert len(inherit_refs) == 1
        assert inherit_refs[0]["text"] == "Parent"
        assert inherit_refs[0].get("scope") == "Child"


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


class TestBareIdentifierUsageReferences:
    """Tests for bare identifier usage reference extraction (issue #197).

    Verifies that standalone identifier usage (not already covered by calls,
    member access, imports, types, or heritage) is extracted as references
    with type=="usage".
    """

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_constant_in_condition(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that a constant used in an if-condition is extracted."""
        code = """
const MAX_PAGES = 100;

function paginate(count) {
    if (count > MAX_PAGES) {
        return MAX_PAGES;
    }
    return count;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "MAX_PAGES" in usage_names

    @pytest.mark.asyncio
    async def test_variable_passed_as_argument(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that a variable passed as an argument is extracted."""
        code = """
const config = loadConfig();

function init() {
    setupApp(config);
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "config" in usage_names

    @pytest.mark.asyncio
    async def test_variable_in_return_statement(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that a variable in a return statement is extracted."""
        code = """
const defaultValue = 42;

function getValue() {
    return defaultValue;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "defaultValue" in usage_names

    @pytest.mark.asyncio
    async def test_variable_in_assignment(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that a variable used on the RHS of an assignment is extracted."""
        code = """
const source = [1, 2, 3];

function copy() {
    const target = source;
    return target;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "source" in usage_names

    @pytest.mark.asyncio
    async def test_single_char_identifiers_excluded(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that single-character identifiers are NOT extracted as usage refs."""
        code = """
function test() {
    const x = 1;
    const y = x + 2;
    return y;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "x" not in usage_names
        assert "y" not in usage_names

    @pytest.mark.asyncio
    async def test_builtin_identifiers_excluded(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that builtins like console, undefined are NOT extracted."""
        code = """
function test() {
    if (value === undefined) {
        console.log("missing");
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "undefined" not in usage_names
        assert "console" not in usage_names

    @pytest.mark.asyncio
    async def test_no_duplicate_refs_for_calls(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that a function call target is NOT also extracted as bare usage."""
        code = """
function doWork() {}

function main() {
    doWork();
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # doWork should appear as a "call" ref, NOT also as a "usage" ref
        call_refs = [
            r for r in references if r["text"] == "doWork" and r["type"] == "call"
        ]
        usage_refs = [
            r for r in references if r["text"] == "doWork" and r["type"] == "usage"
        ]
        assert len(call_refs) >= 1
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_identifier_in_array_literal(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that identifiers used in array literals are extracted."""
        code = """
const handler = () => {};
const middleware = () => {};

const pipeline = [handler, middleware];
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "handler" in usage_names
        assert "middleware" in usage_names

    @pytest.mark.asyncio
    async def test_identifier_in_ternary(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that identifiers used in ternary expressions are extracted."""
        code = """
const DEBUG = true;
const verbose = false;

function getLevel() {
    return DEBUG ? verbose : false;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "DEBUG" in usage_names
        assert "verbose" in usage_names

    @pytest.mark.asyncio
    async def test_object_literal_value_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that identifiers in object literal values ARE extracted as usage."""
        code = """
const handler = () => {};

const routes = { path: handler };
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        # 'handler' is a value in the object literal — should be usage
        assert "handler" in usage_names
        # 'path' is a key — should NOT be usage
        assert "path" not in usage_names

    @pytest.mark.asyncio
    async def test_for_of_binding_not_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that for-of loop variable bindings are NOT extracted as usage."""
        code = """
const items = [1, 2, 3];

function process() {
    for (const item of items) {
        doWork(item);
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        # 'items' is used as the iterable — should be a usage ref
        assert "items" in usage_names
        # 'item' should only appear once as usage (from the call argument),
        # not from the binding site
        item_usage_refs = [r for r in usage_refs if r["text"] == "item"]
        assert len(item_usage_refs) == 1

    @pytest.mark.asyncio
    async def test_destructuring_bindings_not_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that destructured binding names are NOT extracted as usage refs."""
        code = """
const data = { name: "test", count: 42 };
const { name, count } = data;
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        # 'data' on the RHS is a usage ref
        assert "data" in usage_names
        # 'name' and 'count' in the destructuring pattern are bindings, not usage
        name_usage = [r for r in usage_refs if r["text"] == "name"]
        count_usage = [r for r in usage_refs if r["text"] == "count"]
        assert len(name_usage) == 0
        assert len(count_usage) == 0


class TestCommonJSRequireReferences:
    """Tests for CommonJS require() destructured import extraction (issue #197).

    Verifies that `const { A, B } = require('./module')` produces import
    references for A and B.
    """

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_destructured_require(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that destructured require bindings produce import references."""
        code = """
const { Router, Request, Response } = require('express');
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_names = [r["text"] for r in import_refs]
        assert "Router" in import_names
        assert "Request" in import_names
        assert "Response" in import_names

    @pytest.mark.asyncio
    async def test_destructured_require_has_from_module(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that require import refs include the from_module field."""
        code = """
const { readFile } = require('fs');
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        import_refs = [
            r for r in references if r["type"] == "import" and r["text"] == "readFile"
        ]
        assert len(import_refs) == 1
        assert import_refs[0].get("from_module") == "fs"

    @pytest.mark.asyncio
    async def test_simple_require_not_destructured(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that `const x = require('y')` produces an import ref for x."""
        code = """
const express = require('express');
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_names = [r["text"] for r in import_refs]
        assert "express" in import_names

    @pytest.mark.asyncio
    async def test_require_in_typescript(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that require() works in TypeScript files too."""
        code = """
const { join, resolve } = require('path');
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_names = [r["text"] for r in import_refs]
        assert "join" in import_names
        assert "resolve" in import_names

    @pytest.mark.asyncio
    async def test_var_require(self, parser_service: TreeSitterService) -> None:
        """Test that var x = require('y') works (not just const/let)."""
        code = """
var express = require('express');
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_names = [r["text"] for r in import_refs]
        assert "express" in import_names

    @pytest.mark.asyncio
    async def test_aliased_destructured_require(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that const { A: localA } = require('m') extracts the local binding."""
        code = """
const { readFile: readF, writeFile: writeF } = require('fs');
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_names = [r["text"] for r in import_refs]
        # Should extract the local binding names, not the original keys
        assert "readF" in import_names
        assert "writeF" in import_names


class TestConstructorPropertyDefinitions:
    """Tests for this.property assignments in constructors (issue #197).

    Verifies that `this.x = value` inside a constructor produces a property
    symbol definition scoped to the class.
    """

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_constructor_property_extracted_as_symbol(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that this.prop = value in constructor creates a property symbol."""
        code = """
class Logger {
    constructor(level) {
        this.level = level;
        this.messages = [];
    }

    log(msg) {
        this.messages.push(msg);
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        prop_symbols = [s for s in symbols if s["kind"] == "property"]
        prop_names = [s["name"] for s in prop_symbols]
        assert "level" in prop_names
        assert "messages" in prop_names

    @pytest.mark.asyncio
    async def test_constructor_property_has_class_scope(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that constructor properties are scoped to their class."""
        code = """
class Service {
    constructor(db, log) {
        this.db = db;
        this.log = log;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        prop_symbols = [s for s in symbols if s["kind"] == "property"]
        for prop in prop_symbols:
            assert prop["scope"] == "Service"

    @pytest.mark.asyncio
    async def test_constructor_property_not_duplicated_with_field(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that if a field is already declared, constructor assignment doesn't duplicate."""
        code = """
class Timer {
    elapsed = 0;

    constructor(start, elapsed) {
        this.start = start;
        this.elapsed = elapsed;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # 'elapsed' is a field, 'start' is a constructor property
        field_names = [s["name"] for s in symbols if s["kind"] == "field"]
        prop_names = [s["name"] for s in symbols if s["kind"] == "property"]
        assert "elapsed" in field_names
        assert "start" in prop_names
        # Constructor assigns this.elapsed but field already declared — no duplicate
        assert "elapsed" not in prop_names

    @pytest.mark.asyncio
    async def test_non_constructor_this_assignment_ignored(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that this.x = ... in non-constructor methods does NOT create symbols."""
        code = """
class Counter {
    constructor() {
        this.count = 0;
    }

    reset() {
        this.count = 0;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        prop_symbols = [s for s in symbols if s["kind"] == "property"]
        prop_names = [s["name"] for s in prop_symbols]
        # 'count' should appear once as property from constructor
        assert prop_names.count("count") == 1

    @pytest.mark.asyncio
    async def test_constructor_property_javascript(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that constructor properties work in JavaScript too."""
        code = """
class EventEmitter {
    constructor() {
        this.listeners = {};
        this.maxListeners = 10;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        prop_symbols = [s for s in symbols if s["kind"] == "property"]
        prop_names = [s["name"] for s in prop_symbols]
        assert "listeners" in prop_names
        assert "maxListeners" in prop_names

    @pytest.mark.asyncio
    async def test_nested_function_this_not_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that this.x in a nested function inside constructor is NOT extracted."""
        code = """
class Wrapper {
    constructor(name) {
        this.name = name;
        this.greet = function() {
            this.greeting = "hello";
        };
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        prop_symbols = [s for s in symbols if s["kind"] == "property"]
        prop_names = [s["name"] for s in prop_symbols]
        # 'name' and 'greet' are direct constructor assignments
        assert "name" in prop_names
        assert "greet" in prop_names
        # 'greeting' is inside a nested function — this is rebound, should NOT be extracted
        assert "greeting" not in prop_names


class TestExportAndShorthandReferences:
    """Tests for ES6 export patterns and shorthand property references (#202)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    # --- Group A: Export patterns ---

    @pytest.mark.asyncio
    async def test_named_reexport_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Named re-exports should create import references with from_module."""
        code = """
export { foo, bar } from './module'
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_names = [r["text"] for r in import_refs]
        assert "foo" in import_names
        assert "bar" in import_names

        # Each should have from_module set
        for ref in import_refs:
            if ref["text"] in ("foo", "bar"):
                assert ref.get("from_module") == "./module"

    @pytest.mark.asyncio
    async def test_local_named_export_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Local named exports should create usage references (no from_module)."""
        code = """
const baz = 42;
export { baz }
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # baz should appear as a usage reference from the export
        usage_refs = [
            r for r in references if r["type"] == "usage" and r["text"] == "baz"
        ]
        assert len(usage_refs) == 1

        # Should NOT have from_module
        for ref in usage_refs:
            assert ref.get("from_module") is None

    @pytest.mark.asyncio
    async def test_named_reexport_with_alias(
        self, parser_service: TreeSitterService
    ) -> None:
        """Re-export with alias should reference the original name."""
        code = """
export { foo as bar } from './module'
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_names = [r["text"] for r in import_refs]
        # The reference should be to the original name 'foo', not the alias 'bar'
        assert "foo" in import_names
        assert "bar" not in import_names

    @pytest.mark.asyncio
    async def test_default_export_identifier_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        """export default identifier should create a usage reference."""
        code = """
function myFunction() {}
export default myFunction
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        usage_refs = [
            r for r in references if r["type"] == "usage" and r["text"] == "myFunction"
        ]
        assert len(usage_refs) == 1

    @pytest.mark.asyncio
    async def test_barrel_reexport(self, parser_service: TreeSitterService) -> None:
        """Barrel re-export should create an import reference to the module path."""
        code = """
export * from './utils'
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        module_refs = [r for r in import_refs if r["text"] == "./utils"]
        assert len(module_refs) == 1
        assert module_refs[0].get("from_module") == "./utils"

    @pytest.mark.asyncio
    async def test_namespace_reexport(self, parser_service: TreeSitterService) -> None:
        """Namespace re-export should create an import reference for the alias."""
        code = """
export * as ns from './helpers'
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        ns_refs = [r for r in import_refs if r["text"] == "ns"]
        assert len(ns_refs) == 1
        assert ns_refs[0].get("from_module") == "./helpers"

    @pytest.mark.asyncio
    async def test_reexport_no_duplicate_usage_refs(
        self, parser_service: TreeSitterService
    ) -> None:
        """Re-export identifiers should NOT also appear as usage references."""
        code = """
export { foo, bar } from './module'
"""
        _, references = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        # foo/bar should only be "import" type, not also "usage"
        usage_refs = [
            r
            for r in references
            if r["type"] == "usage" and r["text"] in ("foo", "bar")
        ]
        assert len(usage_refs) == 0

    # --- Group B: Shorthand properties and CommonJS patterns ---

    @pytest.mark.asyncio
    async def test_shorthand_property_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Shorthand properties in object literals should be usage references."""
        code = """
const sync = () => {};
const connect = () => {};
module.exports = { sync, connect }
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "sync" in usage_names
        assert "connect" in usage_names

    @pytest.mark.asyncio
    async def test_shorthand_property_in_plain_object(
        self, parser_service: TreeSitterService
    ) -> None:
        """Shorthand properties in regular objects should also be captured."""
        code = """
const foo = 1;
const bar = 2;
const obj = { foo, bar, baz: 3 }
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "foo" in usage_names
        assert "bar" in usage_names

    @pytest.mark.asyncio
    async def test_commonjs_rhs_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        """CommonJS export RHS values should be usage references."""
        code = """
function handler() {}
exports.foo = handler
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "handler" in usage_names

    @pytest.mark.asyncio
    async def test_module_exports_single_fn(
        self, parser_service: TreeSitterService
    ) -> None:
        """module.exports = singleFn should create a usage reference."""
        code = """
function singleFn() {}
module.exports = singleFn
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "singleFn" in usage_names

    @pytest.mark.asyncio
    async def test_spread_in_exports(self, parser_service: TreeSitterService) -> None:
        """Spread elements in export objects should create usage references."""
        code = """
const defaults = {};
module.exports = { ...defaults, override: true }
"""
        _, references = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_names = [r["text"] for r in usage_refs]
        assert "defaults" in usage_names


class TestVariableDeclarations:
    """Tests for variable declaration symbol extraction in JS/TS."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_const_variable_typescript(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regular const declarations should produce variable symbols."""
        code = """
const count = 0;
const name = "hello";
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "count" in var_names
        assert "name" in var_names

    @pytest.mark.asyncio
    async def test_let_variable_typescript(
        self, parser_service: TreeSitterService
    ) -> None:
        """let declarations should produce variable symbols."""
        code = """
let counter = 10;
let message = "world";
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "counter" in var_names
        assert "message" in var_names

    @pytest.mark.asyncio
    async def test_var_declaration_javascript(
        self, parser_service: TreeSitterService
    ) -> None:
        """var declarations should produce variable symbols."""
        code = """
var total = 42;
var label = "test";
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "total" in var_names
        assert "label" in var_names

    @pytest.mark.asyncio
    async def test_arrow_function_still_function_kind(
        self, parser_service: TreeSitterService
    ) -> None:
        """Arrow functions should still be function kind, not variable."""
        code = """
const add = (a: number, b: number) => a + b;
const count = 0;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        add_sym = [s for s in symbols if s["name"] == "add"]
        assert len(add_sym) == 1
        assert add_sym[0]["kind"] == "function"

        count_sym = [s for s in symbols if s["name"] == "count"]
        assert len(count_sym) == 1
        assert count_sym[0]["kind"] == "variable"

    @pytest.mark.asyncio
    async def test_upper_case_still_constant_kind(
        self, parser_service: TreeSitterService
    ) -> None:
        """UPPER_CASE names should still be constant kind, not variable."""
        code = """
const MAX_RETRIES = 5;
const count = 0;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        max_sym = [s for s in symbols if s["name"] == "MAX_RETRIES"]
        assert len(max_sym) == 1
        assert max_sym[0]["kind"] == "constant"

        count_sym = [s for s in symbols if s["name"] == "count"]
        assert len(count_sym) == 1
        assert count_sym[0]["kind"] == "variable"

    @pytest.mark.asyncio
    async def test_exported_variable_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        """Exported variable declarations should produce variable symbols."""
        code = """
export const baseUrl = "http://localhost";
export let timeout = 3000;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "baseUrl" in var_names
        assert "timeout" in var_names

    @pytest.mark.asyncio
    async def test_function_expression_is_function_kind(
        self, parser_service: TreeSitterService
    ) -> None:
        """Function expressions assigned to variables should be function kind."""
        code = """
const fn = function() { return 1; };
const gen = function*() { yield 1; };
const count = 0;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        fn_sym = [s for s in symbols if s["name"] == "fn"]
        assert len(fn_sym) == 1
        assert fn_sym[0]["kind"] == "function"

        gen_sym = [s for s in symbols if s["name"] == "gen"]
        assert len(gen_sym) == 1
        assert gen_sym[0]["kind"] == "function"

        count_sym = [s for s in symbols if s["name"] == "count"]
        assert len(count_sym) == 1
        assert count_sym[0]["kind"] == "variable"

    @pytest.mark.asyncio
    async def test_destructured_object_produces_individual_symbols(
        self, parser_service: TreeSitterService
    ) -> None:
        """Destructured object bindings should produce one symbol per binding."""
        code = """
const { alpha, beta } = getValues();
const { MAX_SIZE, name: localName } = config;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "alpha" in var_names
        assert "beta" in var_names
        assert "localName" in var_names

        const_symbols = [s for s in symbols if s["kind"] == "constant"]
        const_names = [s["name"] for s in const_symbols]
        assert "MAX_SIZE" in const_names

        # Should NOT have a symbol named "{ alpha, beta }"
        all_names = [s["name"] for s in symbols]
        assert not any("{" in n for n in all_names)

    @pytest.mark.asyncio
    async def test_destructured_array_produces_individual_symbols(
        self, parser_service: TreeSitterService
    ) -> None:
        """Destructured array bindings should produce one symbol per binding."""
        code = """
const [first, second] = getItems();
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "first" in var_names
        assert "second" in var_names

    @pytest.mark.asyncio
    async def test_nested_destructuring_extracts_inner_bindings(
        self, parser_service: TreeSitterService
    ) -> None:
        """Nested destructuring should extract inner binding names."""
        code = """
const { a: { b, c }, d } = obj;
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "b" in var_names
        assert "c" in var_names
        assert "d" in var_names
        # "a" is a property key, not a binding — should NOT be a symbol
        assert "a" not in var_names


class TestNestedConstArrowFunctions:
    """Const arrow functions inside function bodies should be extracted as symbols."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_nested_arrow_function_in_ts_function_body(
        self, parser_service: TreeSitterService
    ) -> None:
        """Arrow function declared inside a function body should be a symbol."""
        code = """
function MyComponent() {
    const handler = () => { console.log("clicked"); };
    const loadData = async () => { return fetch("/api"); };
    const add = (x: number) => x + 1;
    return handler;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        sym_names = [s["name"] for s in symbols]
        assert "MyComponent" in sym_names

        handler_sym = [s for s in symbols if s["name"] == "handler"]
        assert len(handler_sym) == 1
        assert handler_sym[0]["kind"] == "function"

        load_sym = [s for s in symbols if s["name"] == "loadData"]
        assert len(load_sym) == 1
        assert load_sym[0]["kind"] == "function"

        add_sym = [s for s in symbols if s["name"] == "add"]
        assert len(add_sym) == 1
        assert add_sym[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_nested_arrow_function_in_js_function_body(
        self, parser_service: TreeSitterService
    ) -> None:
        """Arrow function inside a JS function body should be a symbol."""
        code = """
function setup() {
    const onClick = () => {};
    const fetchItems = async () => { return []; };
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="javascript", file_path="test.js"
        )

        sym_names = [s["name"] for s in symbols]
        assert "setup" in sym_names

        onclick_sym = [s for s in symbols if s["name"] == "onClick"]
        assert len(onclick_sym) == 1
        assert onclick_sym[0]["kind"] == "function"

        fetch_sym = [s for s in symbols if s["name"] == "fetchItems"]
        assert len(fetch_sym) == 1
        assert fetch_sym[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_nested_arrow_in_arrow_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Arrow function nested inside another arrow function should be extracted."""
        code = """
const outer = () => {
    const inner = () => { return 1; };
    return inner;
};
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        outer_sym = [s for s in symbols if s["name"] == "outer"]
        assert len(outer_sym) == 1
        assert outer_sym[0]["kind"] == "function"

        inner_sym = [s for s in symbols if s["name"] == "inner"]
        assert len(inner_sym) == 1
        assert inner_sym[0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_nested_regular_variables_also_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        """Non-function const declarations inside function bodies should also be extracted."""
        code = """
function init() {
    const MAX_RETRIES = 5;
    const name = "test";
    const handler = () => {};
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="typescript", file_path="test.ts"
        )

        max_sym = [s for s in symbols if s["name"] == "MAX_RETRIES"]
        assert len(max_sym) == 1
        assert max_sym[0]["kind"] == "constant"

        name_sym = [s for s in symbols if s["name"] == "name"]
        assert len(name_sym) == 1
        assert name_sym[0]["kind"] == "variable"

        handler_sym = [s for s in symbols if s["name"] == "handler"]
        assert len(handler_sym) == 1
        assert handler_sym[0]["kind"] == "function"
