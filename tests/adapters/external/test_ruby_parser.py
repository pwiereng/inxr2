"""Tests for Ruby language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestRubySupport:
    """Tests for Ruby language support in TreeSitterService."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    def test_supports_ruby(self, parser_service: TreeSitterService) -> None:
        """Test that Ruby is supported case-insensitively."""
        assert parser_service.supports_language("ruby")
        assert parser_service.supports_language("Ruby")
        assert parser_service.supports_language("RUBY")


class TestRubyClasses:
    """Tests for Ruby class parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_class(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple class definition."""
        code = """class MyClass
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="my_class.rb"
        )

        class_symbols = [s for s in symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "MyClass"

    @pytest.mark.asyncio
    async def test_parse_class_with_inheritance(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a class with superclass inheritance."""
        code = """class Child < Parent
end
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="child.rb"
        )

        class_symbols = [s for s in symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "Child"

        inheritance_refs = [r for r in references if r.reference_type == "inheritance"]
        assert len(inheritance_refs) == 1
        assert inheritance_refs[0].reference_text == "Parent"


class TestRubyModules:
    """Tests for Ruby module parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_module(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple module definition."""
        code = """module MyModule
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="my_module.rb"
        )

        mod_symbols = [s for s in symbols if s.kind == "module"]
        assert len(mod_symbols) == 1
        assert mod_symbols[0].name == "MyModule"

    @pytest.mark.asyncio
    async def test_parse_scope_resolution_module(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a module with scope resolution operator."""
        code = """module Outer::Inner
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="nested.rb"
        )

        mod_symbols = [s for s in symbols if s.kind == "module"]
        assert len(mod_symbols) == 1
        assert mod_symbols[0].name == "Outer::Inner"


class TestRubyMethods:
    """Tests for Ruby method parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_method_in_class(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a method inside a class."""
        code = """class MyClass
  def my_method
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="my_class.rb"
        )

        method_symbols = [s for s in symbols if s.kind == "method"]
        assert len(method_symbols) == 1
        assert method_symbols[0].name == "my_method"
        assert method_symbols[0].scope == "MyClass"

    @pytest.mark.asyncio
    async def test_parse_method_with_params(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a method with parameters."""
        code = """class Calculator
  def add(a, b)
    a + b
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="calc.rb"
        )

        method_symbols = [s for s in symbols if s.kind == "method"]
        assert len(method_symbols) == 1
        assert method_symbols[0].name == "add"
        assert method_symbols[0].scope == "Calculator"

    @pytest.mark.asyncio
    async def test_parse_multiple_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing multiple methods in a class."""
        code = """class Dog
  def bark
  end

  def fetch(item)
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="dog.rb"
        )

        method_symbols = [s for s in symbols if s.kind == "method"]
        method_names = [s.name for s in method_symbols]
        assert "bark" in method_names
        assert "fetch" in method_names
        for m in method_symbols:
            assert m.scope == "Dog"


class TestRubySingletonMethods:
    """Tests for Ruby singleton method (def self.method) parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_singleton_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a singleton method (def self.method)."""
        code = """class Factory
  def self.create(name)
    new(name)
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="factory.rb"
        )

        static_symbols = [s for s in symbols if s.kind == "staticmethod"]
        assert len(static_symbols) == 1
        assert static_symbols[0].name == "create"
        assert static_symbols[0].scope == "Factory"

    @pytest.mark.asyncio
    async def test_parse_multiple_singleton_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing multiple singleton methods."""
        code = """class Config
  def self.load(path)
  end

  def self.default
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="config.rb"
        )

        static_symbols = [s for s in symbols if s.kind == "staticmethod"]
        static_names = [s.name for s in static_symbols]
        assert "load" in static_names
        assert "default" in static_names

    @pytest.mark.asyncio
    async def test_parse_singleton_method_with_variable_receiver(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test singleton method where receiver is a local variable, not self."""
        code = """class MyClass
  obj = Object.new
  def obj.custom_method
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="custom.rb"
        )

        static_symbols = [s for s in symbols if s.kind == "staticmethod"]
        assert len(static_symbols) == 1
        assert static_symbols[0].name == "custom_method"


class TestRubyConstants:
    """Tests for Ruby constant parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_constant_in_class(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing constants inside a class."""
        code = """class Settings
  MAX_RETRIES = 3
  DEFAULT_TIMEOUT = 30
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="settings.rb"
        )

        const_symbols = [s for s in symbols if s.kind == "constant"]
        const_names = [s.name for s in const_symbols]
        assert "MAX_RETRIES" in const_names
        assert "DEFAULT_TIMEOUT" in const_names
        for c in const_symbols:
            assert c.scope == "Settings"

    @pytest.mark.asyncio
    async def test_parse_constant_in_module(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a constant inside a module."""
        code = """module Constants
  VERSION = "1.0.0"
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="constants.rb"
        )

        const_symbols = [s for s in symbols if s.kind == "constant"]
        assert len(const_symbols) == 1
        assert const_symbols[0].name == "VERSION"
        assert const_symbols[0].scope == "Constants"


class TestRubyReferences:
    """Tests for Ruby reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_method_call_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting method call references."""
        code = """class Worker
  def process
    helper_method()
    do_work()
  end
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="worker.rb"
        )

        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "helper_method" in call_texts
        assert "do_work" in call_texts

    @pytest.mark.asyncio
    async def test_builtin_calls_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that builtin method calls are filtered from references."""
        code = """class Printer
  def show
    puts "hello"
    print "world"
    p 42
    custom_method()
  end
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="printer.rb"
        )

        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "puts" not in call_texts
        assert "print" not in call_texts
        assert "p" not in call_texts
        assert "custom_method" in call_texts

    @pytest.mark.asyncio
    async def test_parse_dotted_method_call(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting dotted method call references."""
        code = """class Worker
  def process(obj)
    obj.transform
    result = obj.compute(42)
  end
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="worker.rb"
        )

        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "transform" in call_texts
        assert "compute" in call_texts

    @pytest.mark.asyncio
    async def test_parse_instance_variable_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting instance variable references."""
        code = """class Person
  def initialize(name)
    @name = name
  end

  def greet
    @name
  end
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="person.rb"
        )

        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "@name" in usage_texts

    @pytest.mark.asyncio
    async def test_parse_scope_resolution_call(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting references from scope resolution calls."""
        code = """class Worker
  def process
    Other::Helper.call(data)
  end
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="worker.rb"
        )

        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "call" in call_texts

        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        # Individual constants from scope_resolution are emitted separately
        assert "Other" in usage_texts
        assert "Helper" in usage_texts

    @pytest.mark.asyncio
    async def test_scoped_superclass_not_duplicate_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that scoped superclass constants are not emitted as usage refs."""
        code = """class Child < Outer::Base
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="child.rb"
        )

        inheritance_refs = [r for r in references if r.reference_type == "inheritance"]
        assert len(inheritance_refs) == 1
        assert inheritance_refs[0].reference_text == "Outer::Base"

        # Outer and Base should NOT appear as separate usage refs
        # since they're part of the superclass declaration
        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "Outer" not in usage_texts
        assert "Base" not in usage_texts

    @pytest.mark.asyncio
    async def test_singleton_method_variable_receiver_scope(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that scope is correct inside def obj.method_name."""
        code = """class MyClass
  obj = Object.new
  def obj.custom_method
    helper_call()
  end
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="custom.rb"
        )

        call_refs = [r for r in references if r.reference_type == "call"]
        helper_ref = next(r for r in call_refs if r.reference_text == "helper_call")
        assert helper_ref.scope == "MyClass.custom_method"


class TestRubyImports:
    """Tests for Ruby require/require_relative parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_require(self, parser_service: TreeSitterService) -> None:
        """Test parsing require statements."""
        code = """require 'json'
require 'net/http'
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="app.rb"
        )

        import_refs = [r for r in references if r.reference_type == "import"]
        import_texts = [r.reference_text for r in import_refs]
        assert "json" in import_texts
        assert "net/http" in import_texts

    @pytest.mark.asyncio
    async def test_parse_require_relative(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing require_relative statements."""
        code = """require_relative 'helper'
require_relative 'lib/utils'
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="app.rb"
        )

        import_refs = [r for r in references if r.reference_type == "import"]
        import_texts = [r.reference_text for r in import_refs]
        assert "helper" in import_texts
        assert "lib/utils" in import_texts


class TestRubyIncludeExtend:
    """Tests for Ruby include/extend references."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_include(self, parser_service: TreeSitterService) -> None:
        """Test extracting include references."""
        code = """class MyList
  include Loggable

  def each(&block)
  end
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="my_list.rb"
        )

        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "Loggable" in usage_texts

    @pytest.mark.asyncio
    async def test_parse_extend(self, parser_service: TreeSitterService) -> None:
        """Test extracting extend references."""
        code = """class Config
  extend Serializable
end
"""
        _, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="config.rb"
        )

        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "Serializable" in usage_texts


class TestRubyNestedScoping:
    """Tests for nested class/module scoping."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_nested_class_in_module(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a class nested inside a module."""
        code = """module MyModule
  class MyClass
    def my_method
    end
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="nested.rb"
        )

        mod_symbols = [s for s in symbols if s.kind == "module"]
        assert len(mod_symbols) == 1
        assert mod_symbols[0].name == "MyModule"
        assert mod_symbols[0].scope is None

        class_symbols = [s for s in symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "MyClass"
        assert class_symbols[0].scope == "MyModule"

        method_symbols = [s for s in symbols if s.kind == "method"]
        assert len(method_symbols) == 1
        assert method_symbols[0].name == "my_method"
        assert method_symbols[0].scope == "MyModule::MyClass"

    @pytest.mark.asyncio
    async def test_nested_class_in_class(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a class nested inside another class."""
        code = """class Outer
  class Inner
    def inner_method
    end
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="nested.rb"
        )

        class_symbols = [s for s in symbols if s.kind == "class"]
        class_names = [s.name for s in class_symbols]
        assert "Outer" in class_names
        assert "Inner" in class_names

        inner = next(s for s in class_symbols if s.name == "Inner")
        assert inner.scope == "Outer"

        method_symbols = [s for s in symbols if s.kind == "method"]
        assert method_symbols[0].name == "inner_method"
        assert method_symbols[0].scope == "Outer::Inner"


class TestRubyComments:
    """Tests for Ruby comment extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_extract_single_line_comment(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting a single-line comment."""
        code = """# This is a comment
class MyClass
end
"""
        comments = await parser_service.extract_comments(
            content=code, language="ruby", file_path="my_class.rb"
        )

        assert len(comments) == 1
        assert comments[0].content == "This is a comment"
        assert comments[0].content_type == "single_line_comment"

    @pytest.mark.asyncio
    async def test_extract_multiple_comments(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting multiple comments."""
        code = """# First comment
# Second comment
class MyClass
  # Method comment
  def my_method
  end
end
"""
        comments = await parser_service.extract_comments(
            content=code, language="ruby", file_path="my_class.rb"
        )

        comment_texts = [c.content for c in comments]
        assert "First comment" in comment_texts
        assert "Second comment" in comment_texts
        assert "Method comment" in comment_texts

    @pytest.mark.asyncio
    async def test_empty_comment_skipped(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that empty comments are skipped."""
        code = """#
class MyClass
end
"""
        comments = await parser_service.extract_comments(
            content=code, language="ruby", file_path="my_class.rb"
        )

        assert len(comments) == 0


class TestRubyComplexStructures:
    """Tests for complex Ruby structures."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_full_ruby_file(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a complete Ruby file with mixed constructs."""
        code = """require 'json'
require_relative 'helper'

module MyApp
  MY_VERSION = "1.0"

  class Server < BaseServer
    include Loggable

    def initialize(host, port)
      @host = host
      @port = port
    end

    def self.default
      new("localhost", 8080)
    end

    def start
      logger.info("Starting")
      listen()
    end
  end
end
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="server.rb"
        )

        # Module
        mod = [s for s in symbols if s.kind == "module"]
        assert len(mod) == 1
        assert mod[0].name == "MyApp"

        # Constant
        consts = [s for s in symbols if s.kind == "constant"]
        assert any(c.name == "MY_VERSION" for c in consts)

        # Class
        classes = [s for s in symbols if s.kind == "class"]
        assert any(c.name == "Server" for c in classes)
        server = next(c for c in classes if c.name == "Server")
        assert server.scope == "MyApp"

        # Methods
        methods = [s for s in symbols if s.kind == "method"]
        method_names = [m.name for m in methods]
        assert "initialize" in method_names
        assert "start" in method_names

        # Singleton method
        statics = [s for s in symbols if s.kind == "staticmethod"]
        assert any(s.name == "default" for s in statics)

        # Imports
        import_refs = [r for r in references if r.reference_type == "import"]
        import_texts = [r.reference_text for r in import_refs]
        assert "json" in import_texts
        assert "helper" in import_texts

        # Inheritance
        inheritance_refs = [r for r in references if r.reference_type == "inheritance"]
        assert any(r.reference_text == "BaseServer" for r in inheritance_refs)

        # Include reference
        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "Loggable" in usage_texts

    @pytest.mark.asyncio
    async def test_method_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that method symbol location points to the name token."""
        code = """class MyClass
  def my_method
  end
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="my_class.rb"
        )

        method_symbols = [s for s in symbols if s.name == "my_method"]
        assert len(method_symbols) == 1
        assert method_symbols[0].start_line == 2


class TestRubyEdgeCases:
    """Tests for edge cases in Ruby parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_malformed_ruby_code(self, parser_service: TreeSitterService) -> None:
        """Test that malformed Ruby code does not crash the parser."""
        code = """class Broken
  def incomplete(
  end
  MY_CONST =
end
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="broken.rb"
        )

        assert isinstance(symbols, list)
        assert isinstance(references, list)

    @pytest.mark.asyncio
    async def test_empty_ruby_file(self, parser_service: TreeSitterService) -> None:
        """Test parsing an empty Ruby file."""
        code = ""
        symbols, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="empty.rb"
        )

        assert isinstance(symbols, list)
        assert isinstance(references, list)
        assert len(symbols) == 0

    @pytest.mark.asyncio
    async def test_rake_file_extension(self, parser_service: TreeSitterService) -> None:
        """Test parsing a .rake file."""
        code = """task :build do
  puts "Building..."
end
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="ruby", file_path="Rakefile.rake"
        )

        assert isinstance(symbols, list)
        assert isinstance(references, list)

    @pytest.mark.asyncio
    async def test_top_level_method(self, parser_service: TreeSitterService) -> None:
        """Test parsing a top-level method with no enclosing class or module."""
        code = """def top_level_helper
  42
end
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="ruby", file_path="helper.rb"
        )

        method_symbols = [s for s in symbols if s.kind == "method"]
        assert len(method_symbols) == 1
        assert method_symbols[0].name == "top_level_helper"
        assert method_symbols[0].scope is None
