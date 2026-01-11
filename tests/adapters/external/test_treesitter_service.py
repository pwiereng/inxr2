"""Tests for TreeSitterService adapter."""

import pytest

from inxr2.adapters.external.treesitter_service import TreeSitterService


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

    def test_unsupported_language(self, parser_service: TreeSitterService) -> None:
        """Test that unsupported languages are rejected."""
        assert not parser_service.supports_language("rust")
        assert not parser_service.supports_language("go")
        assert not parser_service.supports_language("java")


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
