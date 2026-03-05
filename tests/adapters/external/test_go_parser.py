"""Tests for Go language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestGoSupport:
    """Tests for Go language support in TreeSitterService."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    def test_supports_go(self, parser_service: TreeSitterService) -> None:
        """Test that Go is supported."""
        assert parser_service.supports_language("go")
        assert parser_service.supports_language("Go")
        assert parser_service.supports_language("GO")


class TestGoPackage:
    """Tests for Go package declaration parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_package_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a package declaration."""
        code = """package main

func main() {}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        pkg_symbols = [s for s in symbols if s["kind"] == "package"]
        assert len(pkg_symbols) == 1
        assert pkg_symbols[0]["name"] == "main"


class TestGoFunctions:
    """Tests for Go function parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a simple function."""
        code = """package main

func Hello() {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["name"] == "Hello"

    @pytest.mark.asyncio
    async def test_parse_function_with_params(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a function with parameters."""
        code = """package main

func Add(a int, b int) int {
    return a + b
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="math.go"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["name"] == "Add"
        assert "signature" in func_symbols[0]
        assert "Add" in func_symbols[0]["signature"]

    @pytest.mark.asyncio
    async def test_parse_exported_and_unexported_functions(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that both exported and unexported functions are parsed."""
        code = """package mypackage

func PublicFunc() {}

func privateFunc() {}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="funcs.go"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        func_names = [s["name"] for s in func_symbols]
        assert "PublicFunc" in func_names
        assert "privateFunc" in func_names

    @pytest.mark.asyncio
    async def test_parse_function_multiple_return_values(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a function with multiple return values."""
        code = """package main

func Divide(a, b float64) (float64, error) {
    if b == 0 {
        return 0, nil
    }
    return a / b, nil
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="math.go"
        )

        func_symbols = [s for s in symbols if s["kind"] == "function"]
        assert len(func_symbols) == 1
        assert func_symbols[0]["name"] == "Divide"


class TestGoMethods:
    """Tests for Go method parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_value_receiver_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a method with value receiver."""
        code = """package main

type Server struct {
    host string
}

func (s Server) Address() string {
    return s.host
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="server.go"
        )

        method_symbols = [s for s in symbols if s["kind"] == "method"]
        assert len(method_symbols) == 1
        assert method_symbols[0]["name"] == "Address"
        assert method_symbols[0]["scope"] == "Server"

    @pytest.mark.asyncio
    async def test_parse_pointer_receiver_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a method with pointer receiver."""
        code = """package main

type Server struct {
    host string
    port int
}

func (s *Server) Start() error {
    return nil
}

func (s *Server) Stop() {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="server.go"
        )

        method_symbols = [s for s in symbols if s["kind"] == "method"]
        method_names = [s["name"] for s in method_symbols]
        assert "Start" in method_names
        assert "Stop" in method_names

        for method in method_symbols:
            assert method["scope"] == "Server"

    @pytest.mark.asyncio
    async def test_method_signature(self, parser_service: TreeSitterService) -> None:
        """Test that method signatures include receiver type."""
        code = """package main

type Calculator struct{}

func (c *Calculator) Add(a, b int) int {
    return a + b
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="calc.go"
        )

        method_symbols = [s for s in symbols if s["kind"] == "method"]
        assert len(method_symbols) == 1
        assert "signature" in method_symbols[0]
        assert "Calculator" in method_symbols[0]["signature"]
        assert "Add" in method_symbols[0]["signature"]


class TestGoStructs:
    """Tests for Go struct parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_struct(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple struct."""
        code = """package main

type Person struct {
    Name string
    Age  int
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="person.go"
        )

        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0]["name"] == "Person"

        fields = [s for s in symbols if s["kind"] == "field"]
        field_names = [s["name"] for s in fields]
        assert "Name" in field_names
        assert "Age" in field_names

        for field in fields:
            assert field["scope"] == "Person"

    @pytest.mark.asyncio
    async def test_parse_struct_with_embedded_type(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a struct with embedded types."""
        code = """package main

type Base struct {
    ID int
}

type Extended struct {
    Base
    Extra string
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="types.go"
        )

        # Extended struct should exist
        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        struct_names = [s["name"] for s in struct_symbols]
        assert "Base" in struct_names
        assert "Extended" in struct_names

        # Base should be an embedded field in Extended
        extended_fields = [
            s for s in symbols if s["kind"] == "field" and s["scope"] == "Extended"
        ]
        field_names = [s["name"] for s in extended_fields]
        assert "Base" in field_names
        assert "Extra" in field_names


class TestGoInterfaces:
    """Tests for Go interface parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_interface(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a simple interface."""
        code = """package main

type Reader interface {
    Read(p []byte) (n int, err error)
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="reader.go"
        )

        interface_symbols = [s for s in symbols if s["kind"] == "interface"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0]["name"] == "Reader"

        # Interface methods are "property" kind (consistent with other parsers)
        methods = [s for s in symbols if s["kind"] == "property"]
        assert len(methods) == 1
        assert methods[0]["name"] == "Read"
        assert methods[0]["scope"] == "Reader"

    @pytest.mark.asyncio
    async def test_parse_interface_with_multiple_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing an interface with multiple methods."""
        code = """package main

type ReadWriter interface {
    Read(p []byte) (n int, err error)
    Write(p []byte) (n int, err error)
    Close() error
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="rw.go"
        )

        interface_symbols = [s for s in symbols if s["kind"] == "interface"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0]["name"] == "ReadWriter"

        methods = [s for s in symbols if s["kind"] == "property"]
        method_names = [s["name"] for s in methods]
        assert "Read" in method_names
        assert "Write" in method_names
        assert "Close" in method_names

    @pytest.mark.asyncio
    async def test_parse_empty_interface(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing an empty interface."""
        code = """package main

type Empty interface{}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="empty.go"
        )

        interface_symbols = [s for s in symbols if s["kind"] == "interface"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0]["name"] == "Empty"


class TestGoConstants:
    """Tests for Go constant parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_single_const(self, parser_service: TreeSitterService) -> None:
        """Test parsing a single constant declaration."""
        code = """package main

const MaxSize = 100
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="const.go"
        )

        const_symbols = [s for s in symbols if s["kind"] == "constant"]
        assert len(const_symbols) == 1
        assert const_symbols[0]["name"] == "MaxSize"

    @pytest.mark.asyncio
    async def test_parse_const_block(self, parser_service: TreeSitterService) -> None:
        """Test parsing a const block."""
        code = """package main

const (
    StatusOK    = 200
    StatusError = 500
    AppName     = "myapp"
)
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="const.go"
        )

        const_symbols = [s for s in symbols if s["kind"] == "constant"]
        const_names = [s["name"] for s in const_symbols]
        assert "StatusOK" in const_names
        assert "StatusError" in const_names
        assert "AppName" in const_names


class TestGoVariables:
    """Tests for Go variable parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_var_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing variable declarations."""
        code = """package main

var GlobalCounter int

var (
    AppVersion = "1.0.0"
    Debug      = false
)
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="vars.go"
        )

        var_symbols = [s for s in symbols if s["kind"] == "variable"]
        var_names = [s["name"] for s in var_symbols]
        assert "GlobalCounter" in var_names
        assert "AppVersion" in var_names
        assert "Debug" in var_names


class TestGoImports:
    """Tests for Go import parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_single_import(self, parser_service: TreeSitterService) -> None:
        """Test parsing a single import."""
        code = """package main

import "fmt"

func main() {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_texts = [r["text"] for r in import_refs]
        assert "fmt" in import_texts

    @pytest.mark.asyncio
    async def test_parse_grouped_imports(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing grouped imports."""
        code = """package main

import (
    "fmt"
    "os"
    "net/http"
    "encoding/json"
)

func main() {}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_texts = [r["text"] for r in import_refs]
        assert "fmt" in import_texts
        assert "os" in import_texts
        assert "net/http" in import_texts
        assert "encoding/json" in import_texts


class TestGoReferences:
    """Tests for Go reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_function_calls(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing function call references."""
        code = """package main

func helper() {}

func process() {
    helper()
    doWork()
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        assert "helper" in call_texts
        assert "doWork" in call_texts

    @pytest.mark.asyncio
    async def test_builtin_calls_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that builtin function calls are filtered."""
        code = """package main

func process() {
    s := make([]int, 10)
    n := len(s)
    s = append(s, 1)
    println(n)
    customFunc()
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        # Builtins should be filtered
        assert "make" not in call_texts
        assert "len" not in call_texts
        assert "append" not in call_texts
        assert "println" not in call_texts
        # Custom function should remain
        assert "customFunc" in call_texts

    @pytest.mark.asyncio
    async def test_parse_method_calls(self, parser_service: TreeSitterService) -> None:
        """Test parsing method call references on objects."""
        code = """package main

type Server struct{}

func (s *Server) Start() {}

func main() {
    s := Server{}
    s.Start()
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        assert "Start" in call_texts

    @pytest.mark.asyncio
    async def test_parse_std_lib_calls(self, parser_service: TreeSitterService) -> None:
        """Test parsing standard library calls (e.g., fmt.Println)."""
        code = """package main

import "fmt"

func main() {
    fmt.Println("hello")
    fmt.Sprintf("%d", 42)
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        assert "fmt.Println" in call_texts
        assert "fmt.Sprintf" in call_texts

    @pytest.mark.asyncio
    async def test_parse_type_usage_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing type usage references."""
        code = """package main

type Config struct {
    Logger   CustomLogger
    Handler  RequestHandler
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="config.go"
        )

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        assert "CustomLogger" in type_texts
        assert "RequestHandler" in type_texts

    @pytest.mark.asyncio
    async def test_primitive_types_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that primitive types are filtered from references."""
        code = """package main

func compute(a int, b float64) string {
    var flag bool
    return ""
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="compute.go"
        )

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        assert "int" not in type_texts
        assert "float64" not in type_texts
        assert "string" not in type_texts
        assert "bool" not in type_texts


class TestGoComplexStructures:
    """Tests for complex Go structures."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_type_alias(self, parser_service: TreeSitterService) -> None:
        """Test parsing a type alias."""
        code = """package main

type StringSlice []string
type HandlerFunc func(w ResponseWriter, r *Request)
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="types.go"
        )

        type_symbols = [s for s in symbols if s["kind"] == "type"]
        type_names = [s["name"] for s in type_symbols]
        assert "StringSlice" in type_names
        assert "HandlerFunc" in type_names

    @pytest.mark.asyncio
    async def test_parse_full_go_file(self, parser_service: TreeSitterService) -> None:
        """Test parsing a complete Go file with multiple constructs."""
        code = """package server

import (
    "fmt"
    "net/http"
)

const DefaultPort = 8080

var globalConfig Config

type Config struct {
    Host string
    Port int
}

type Handler interface {
    Handle(req Request) Response
}

func NewConfig(host string, port int) Config {
    return Config{Host: host, Port: port}
}

func (c *Config) Address() string {
    return fmt.Sprintf("%s:%d", c.Host, c.Port)
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="go", file_path="server.go"
        )

        # Package
        pkg = [s for s in symbols if s["kind"] == "package"]
        assert len(pkg) == 1
        assert pkg[0]["name"] == "server"

        # Constant
        consts = [s for s in symbols if s["kind"] == "constant"]
        assert any(c["name"] == "DefaultPort" for c in consts)

        # Variable
        vars_ = [s for s in symbols if s["kind"] == "variable"]
        assert any(v["name"] == "globalConfig" for v in vars_)

        # Struct
        structs = [s for s in symbols if s["kind"] == "struct"]
        assert any(s["name"] == "Config" for s in structs)

        # Interface
        interfaces = [s for s in symbols if s["kind"] == "interface"]
        assert any(i["name"] == "Handler" for i in interfaces)

        # Function
        funcs = [s for s in symbols if s["kind"] == "function"]
        assert any(f["name"] == "NewConfig" for f in funcs)

        # Method
        methods = [s for s in symbols if s["kind"] == "method"]
        assert any(m["name"] == "Address" and m["scope"] == "Config" for m in methods)

        # Imports
        import_refs = [r for r in references if r["type"] == "import"]
        import_texts = [r["text"] for r in import_refs]
        assert "fmt" in import_texts
        assert "net/http" in import_texts

    @pytest.mark.asyncio
    async def test_multiple_structs_and_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing multiple structs with methods."""
        code = """package main

type Dog struct {
    Name string
}

type Cat struct {
    Name string
}

func (d *Dog) Speak() string {
    return "Woof"
}

func (c *Cat) Speak() string {
    return "Meow"
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="animals.go"
        )

        structs = [s for s in symbols if s["kind"] == "struct"]
        struct_names = [s["name"] for s in structs]
        assert "Dog" in struct_names
        assert "Cat" in struct_names

        methods = [s for s in symbols if s["kind"] == "method"]
        assert any(m["name"] == "Speak" and m["scope"] == "Dog" for m in methods)
        assert any(m["name"] == "Speak" and m["scope"] == "Cat" for m in methods)


class TestGoEdgeCases:
    """Tests for edge cases in Go parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_malformed_go_code(self, parser_service: TreeSitterService) -> None:
        """Test that malformed Go code doesn't crash the parser."""
        code = """package main

func broken( {
    type incomplete struct {
    const =
}
"""
        # Should not raise an exception
        symbols, references = await parser_service.parse_file(
            content=code, language="go", file_path="broken.go"
        )

        # We should get at least the package declaration
        assert isinstance(symbols, list)
        assert isinstance(references, list)

    @pytest.mark.asyncio
    async def test_empty_go_file(self, parser_service: TreeSitterService) -> None:
        """Test parsing an empty Go file."""
        code = ""
        symbols, references = await parser_service.parse_file(
            content=code, language="go", file_path="empty.go"
        )

        assert isinstance(symbols, list)
        assert isinstance(references, list)

    @pytest.mark.asyncio
    async def test_function_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that function symbol start_line points to the function name."""
        code = """package main

func MyFunction() {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        func_symbols = [s for s in symbols if s["name"] == "MyFunction"]
        assert len(func_symbols) == 1
        # The function name is on line 3
        assert func_symbols[0]["start_line"] == 3

    @pytest.mark.asyncio
    async def test_struct_with_tags(self, parser_service: TreeSitterService) -> None:
        """Test parsing a struct with field tags."""
        code = """package main

type User struct {
    Name  string `json:"name"`
    Email string `json:"email" validate:"required"`
    Age   int    `json:"age,omitempty"`
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="user.go"
        )

        struct_symbols = [s for s in symbols if s["kind"] == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0]["name"] == "User"

        fields = [s for s in symbols if s["kind"] == "field" and s["scope"] == "User"]
        field_names = [s["name"] for s in fields]
        assert "Name" in field_names
        assert "Email" in field_names
        assert "Age" in field_names

    @pytest.mark.asyncio
    async def test_chained_selector_call(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that chained selector calls like a.B.Method() emit references."""
        code = """package main

type Registry struct{}
type Service struct{}

func (r *Registry) GetService() Service { return Service{} }
func (s *Service) Process() {}

func main() {
    var reg Registry
    reg.GetService().Process()
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        # Both method names in the chain should be captured
        assert "GetService" in call_texts
        assert "Process" in call_texts

    @pytest.mark.asyncio
    async def test_chained_selector_call_stdlib(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that stdlib chained calls like http.DefaultClient.Do() are qualified."""
        code = """package main

import "net/http"

func main() {
    req, _ := http.NewRequest("GET", "/", nil)
    http.DefaultClient.Do(req)
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        # Stdlib chained call should be qualified
        assert "http.DefaultClient.Do" in call_texts
        # Simple stdlib call should also be qualified
        assert "http.NewRequest" in call_texts

    @pytest.mark.asyncio
    async def test_chained_selector_field_access_stdlib_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that stdlib chained field access is filtered from usage refs."""
        code = """package main

import "net/http"

func main() {
    _ = http.DefaultClient.Transport
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_texts = [r["text"] for r in usage_refs]
        # Stdlib field access should not appear as bare usage refs
        assert "Transport" not in usage_texts

    @pytest.mark.asyncio
    async def test_chained_selector_field_access(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that chained selector field access like a.B.C emits references."""
        code = """package main

type Outer struct{}
type Inner struct{}

func main() {
    var o Outer
    _ = o.Inner.Value
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="go", file_path="main.go"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_texts = [r["text"] for r in usage_refs]
        # The outermost field "Value" should be captured
        assert "Value" in usage_texts

    @pytest.mark.asyncio
    async def test_iota_const_block(self, parser_service: TreeSitterService) -> None:
        """Test parsing const block with iota."""
        code = """package main

const (
    Sunday = iota
    Monday
    Tuesday
    Wednesday
)
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="go", file_path="days.go"
        )

        const_symbols = [s for s in symbols if s["kind"] == "constant"]
        const_names = [s["name"] for s in const_symbols]
        assert "Sunday" in const_names
        assert "Monday" in const_names
        assert "Tuesday" in const_names
        assert "Wednesday" in const_names
