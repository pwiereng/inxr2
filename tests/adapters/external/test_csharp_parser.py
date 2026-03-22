"""Tests for C# language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestCSharpSupport:
    """Tests for C# language support in TreeSitterService."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    def test_supports_csharp(self, parser_service: TreeSitterService) -> None:
        assert parser_service.supports_language("csharp")
        assert parser_service.supports_language("CSharp")
        assert parser_service.supports_language("CSHARP")


class TestCSharpClasses:
    """Tests for C# class parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_class(self, parser_service: TreeSitterService) -> None:
        code = """
public class HelloWorld {
    public void Main() {
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="HelloWorld.cs"
        )

        class_symbols = [s for s in symbols if s.name == "HelloWorld"]
        assert len(class_symbols) == 1
        assert class_symbols[0].kind == "class"

    @pytest.mark.asyncio
    async def test_parse_abstract_class(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public abstract class Shape {
    public abstract double Area();
    public abstract double Perimeter();
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Shape.cs"
        )

        class_symbols = [s for s in symbols if s.name == "Shape"]
        assert len(class_symbols) == 1
        assert class_symbols[0].kind == "class"
        assert class_symbols[0].metadata["is_abstract"] is True

    @pytest.mark.asyncio
    async def test_parse_sealed_class(self, parser_service: TreeSitterService) -> None:
        code = """
public sealed class Singleton {
    public static Singleton Instance { get; }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Singleton.cs"
        )

        class_symbols = [s for s in symbols if s.name == "Singleton"]
        assert len(class_symbols) == 1
        assert class_symbols[0].metadata["is_sealed"] is True

    @pytest.mark.asyncio
    async def test_parse_static_class(self, parser_service: TreeSitterService) -> None:
        code = """
public static class MathHelper {
    public static int Square(int n) { return n * n; }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="MathHelper.cs"
        )

        class_symbols = [s for s in symbols if s.name == "MathHelper"]
        assert len(class_symbols) == 1
        assert class_symbols[0].metadata["is_static"] is True

    @pytest.mark.asyncio
    async def test_parse_inner_class(self, parser_service: TreeSitterService) -> None:
        code = """
public class Outer {
    public class Inner {
        public void DoSomething() {}
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Outer.cs"
        )

        outer = [s for s in symbols if s.name == "Outer" and s.kind == "class"]
        assert len(outer) == 1

        inner = [s for s in symbols if s.name == "Inner" and s.kind == "class"]
        assert len(inner) == 1
        assert inner[0].scope == "Outer"
        assert inner[0].metadata["is_inner"] is True

    @pytest.mark.asyncio
    async def test_parse_partial_class(self, parser_service: TreeSitterService) -> None:
        code = """
public partial class MyService {
    public void MethodA() {}
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="MyService.cs"
        )

        class_symbols = [s for s in symbols if s.name == "MyService"]
        assert len(class_symbols) == 1
        assert class_symbols[0].metadata["is_partial"] is True

    @pytest.mark.asyncio
    async def test_parse_generic_class(self, parser_service: TreeSitterService) -> None:
        code = """
public class Repository<T> where T : class {
    public T GetById(int id) { return default; }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Repository.cs"
        )

        class_symbols = [s for s in symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "Repository"

    @pytest.mark.asyncio
    async def test_parse_class_with_inheritance(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Dog : Animal, IMovable {
    public void Speak() {}
    public void Move() {}
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Dog.cs"
        )

        class_symbols = [s for s in symbols if s.name == "Dog"]
        assert len(class_symbols) == 1

        inheritance_refs = [r for r in references if r.reference_type == "inheritance"]
        inheritance_texts = [r.reference_text for r in inheritance_refs]
        assert "Animal" in inheritance_texts
        assert "IMovable" in inheritance_texts


class TestCSharpStructsAndRecords:
    """Tests for C# struct and record parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_struct(self, parser_service: TreeSitterService) -> None:
        code = """
public struct Point {
    public int X;
    public int Y;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Point.cs"
        )

        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0].name == "Point"

    @pytest.mark.asyncio
    async def test_parse_readonly_struct(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public readonly struct Vector2D {
    public readonly double X;
    public readonly double Y;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Vector2D.cs"
        )

        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0].metadata["is_readonly"] is True

    @pytest.mark.asyncio
    async def test_parse_record(self, parser_service: TreeSitterService) -> None:
        code = """
public record Person(string FirstName, string LastName);
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Person.cs"
        )

        record_symbols = [s for s in symbols if s.kind == "record"]
        assert len(record_symbols) == 1
        assert record_symbols[0].name == "Person"

        # Record parameters should appear as properties
        props = [s for s in symbols if s.kind == "property"]
        prop_names = [s.name for s in props]
        assert "FirstName" in prop_names
        assert "LastName" in prop_names

    @pytest.mark.asyncio
    async def test_parse_record_struct(self, parser_service: TreeSitterService) -> None:
        code = """
public record struct Coordinate(double Latitude, double Longitude);
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Coordinate.cs"
        )

        record_symbols = [s for s in symbols if s.kind == "record"]
        assert len(record_symbols) == 1
        assert record_symbols[0].name == "Coordinate"


class TestCSharpInterfaces:
    """Tests for C# interface parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_interface(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public interface IDrawable {
    void Draw();
    void Resize(int width, int height);
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="IDrawable.cs"
        )

        interface_symbols = [s for s in symbols if s.name == "IDrawable"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0].kind == "interface"

        methods = [s for s in symbols if s.kind == "method"]
        method_names = [s.name for s in methods]
        assert "Draw" in method_names
        assert "Resize" in method_names

    @pytest.mark.asyncio
    async def test_parse_generic_interface(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public interface IRepository<T> {
    T GetById(int id);
    void Save(T entity);
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="IRepository.cs"
        )

        interface_symbols = [s for s in symbols if s.kind == "interface"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0].name == "IRepository"

    @pytest.mark.asyncio
    async def test_parse_interface_with_default_method(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public interface ILogger {
    void Log(string message);
    void LogError(string message) {
        Log("ERROR: " + message);
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="ILogger.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        method_names = [s.name for s in methods]
        assert "Log" in method_names
        assert "LogError" in method_names


class TestCSharpEnums:
    """Tests for C# enum parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_enum(self, parser_service: TreeSitterService) -> None:
        code = """
public enum Color {
    Red,
    Green,
    Blue
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Color.cs"
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
    async def test_parse_enum_with_values(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public enum HttpStatusCode {
    OK = 200,
    NotFound = 404,
    InternalServerError = 500
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="HttpStatusCode.cs"
        )

        enum_symbols = [s for s in symbols if s.kind == "enum"]
        assert len(enum_symbols) == 1

        enum_values = [s for s in symbols if s.kind == "enum_value"]
        value_names = [s.name for s in enum_values]
        assert "OK" in value_names
        assert "NotFound" in value_names
        assert "InternalServerError" in value_names

    @pytest.mark.asyncio
    async def test_parse_flags_enum(self, parser_service: TreeSitterService) -> None:
        code = """
[Flags]
public enum Permission {
    None = 0,
    Read = 1,
    Write = 2,
    Execute = 4,
    All = Read | Write | Execute
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Permission.cs"
        )

        enum_symbols = [s for s in symbols if s.kind == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0].name == "Permission"

        enum_values = [s for s in symbols if s.kind == "enum_value"]
        value_names = [s.name for s in enum_values]
        assert "None" in value_names
        assert "Read" in value_names
        assert "All" in value_names

    @pytest.mark.asyncio
    async def test_enum_value_scope(self, parser_service: TreeSitterService) -> None:
        code = """
public enum Direction {
    North, South, East, West
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Direction.cs"
        )

        enum_values = [s for s in symbols if s.kind == "enum_value"]
        for value in enum_values:
            assert value.scope == "Direction"


class TestCSharpMethods:
    """Tests for C# method parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_instance_method(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Calculator {
    public int Add(int a, int b) {
        return a + b;
    }

    public double Multiply(double x, double y) {
        return x * y;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Calculator.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        method_names = [s.name for s in methods]
        assert "Add" in method_names
        assert "Multiply" in method_names

        add_method = [s for s in methods if s.name == "Add"][0]
        assert add_method.scope == "Calculator"
        assert add_method.metadata["is_static"] is False

    @pytest.mark.asyncio
    async def test_parse_static_method(self, parser_service: TreeSitterService) -> None:
        code = """
public class MathUtils {
    public static int Square(int n) {
        return n * n;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="MathUtils.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].metadata["is_static"] is True

    @pytest.mark.asyncio
    async def test_parse_async_method(self, parser_service: TreeSitterService) -> None:
        code = """
public class DataService {
    public async Task<string> FetchDataAsync() {
        return await GetData();
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="DataService.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].name == "FetchDataAsync"
        assert methods[0].metadata["is_async"] is True

    @pytest.mark.asyncio
    async def test_parse_abstract_method(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public abstract class Animal {
    public abstract void Speak();
    public abstract void Move();
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Animal.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        for method in methods:
            assert method.metadata["is_abstract"] is True

    @pytest.mark.asyncio
    async def test_parse_virtual_method(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Base {
    public virtual void OnEvent() {
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Base.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].metadata["is_virtual"] is True

    @pytest.mark.asyncio
    async def test_parse_override_method(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Derived : Base {
    public override void OnEvent() {
        DoSomething();
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Derived.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].metadata["is_override"] is True

    @pytest.mark.asyncio
    async def test_method_signature(self, parser_service: TreeSitterService) -> None:
        code = """
public class Service {
    public string ProcessData(string input, int count) {
        return input;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Service.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].signature is not None
        assert (
            methods[0].signature is not None and "ProcessData" in methods[0].signature
        )

    @pytest.mark.asyncio
    async def test_parse_constructor(self, parser_service: TreeSitterService) -> None:
        code = """
public class Person {
    private string _name;
    private int _age;

    public Person(string name, int age) {
        _name = name;
        _age = age;
    }

    public Person(string name) : this(name, 0) {
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Person.cs"
        )

        constructors = [s for s in symbols if s.kind == "constructor"]
        assert len(constructors) == 2
        for constructor in constructors:
            assert constructor.name == "Person"
            assert constructor.scope == "Person"


class TestCSharpProperties:
    """Tests for C# property parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_auto_property(self, parser_service: TreeSitterService) -> None:
        code = """
public class User {
    public string Name { get; set; }
    public int Age { get; set; }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="User.cs"
        )

        props = [s for s in symbols if s.kind == "property"]
        prop_names = [s.name for s in props]
        assert "Name" in prop_names
        assert "Age" in prop_names

    @pytest.mark.asyncio
    async def test_parse_readonly_property(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Circle {
    public double Radius { get; }
    public double Area => Math.PI * Radius * Radius;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Circle.cs"
        )

        props = [s for s in symbols if s.kind == "property"]
        prop_names = [s.name for s in props]
        assert "Radius" in prop_names
        assert "Area" in prop_names

    @pytest.mark.asyncio
    async def test_parse_static_property(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Config {
    public static string AppName { get; set; }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Config.cs"
        )

        props = [s for s in symbols if s.kind == "property"]
        assert len(props) == 1
        assert props[0].metadata["is_static"] is True

    @pytest.mark.asyncio
    async def test_parse_indexer(self, parser_service: TreeSitterService) -> None:
        code = """
public class StringCollection {
    private string[] _items;

    public string this[int index] {
        get { return _items[index]; }
        set { _items[index] = value; }
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="StringCollection.cs"
        )

        indexers = [s for s in symbols if s.kind == "indexer"]
        assert len(indexers) == 1
        assert indexers[0].name == "this[]"
        assert indexers[0].scope == "StringCollection"


class TestCSharpFields:
    """Tests for C# field parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_instance_fields(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class User {
    private string _username;
    private string _email;
    protected int _age;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="User.cs"
        )

        fields = [s for s in symbols if s.kind == "field"]
        field_names = [s.name for s in fields]
        assert "_username" in field_names
        assert "_email" in field_names
        assert "_age" in field_names

        for field in fields:
            assert field.scope == "User"

    @pytest.mark.asyncio
    async def test_parse_const_fields(self, parser_service: TreeSitterService) -> None:
        code = """
public class Constants {
    public const int MaxValue = 100;
    public const string AppName = "MyApp";
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Constants.cs"
        )

        constants = [s for s in symbols if s.kind == "constant"]
        constant_names = [s.name for s in constants]
        assert "MaxValue" in constant_names
        assert "AppName" in constant_names

    @pytest.mark.asyncio
    async def test_parse_readonly_fields(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Config {
    private readonly string _connectionString;
    private readonly int _timeout;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Config.cs"
        )

        fields = [s for s in symbols if s.kind == "field"]
        for field in fields:
            assert field.metadata["is_readonly"] is True

    @pytest.mark.asyncio
    async def test_parse_static_fields(self, parser_service: TreeSitterService) -> None:
        code = """
public class Counter {
    private static int _count = 0;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Counter.cs"
        )

        fields = [s for s in symbols if s.kind == "field"]
        assert len(fields) == 1
        assert fields[0].metadata["is_static"] is True


class TestCSharpNamespacesAndUsings:
    """Tests for C# namespace and using directive parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_file_scoped_namespace(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
namespace MyApp.Services;

public class UserService {
    public void Create() {}
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="UserService.cs"
        )

        ns_symbols = [s for s in symbols if s.kind == "namespace"]
        assert len(ns_symbols) == 1
        assert ns_symbols[0].name == "MyApp.Services"

        class_symbols = [s for s in symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].scope == "MyApp.Services"

    @pytest.mark.asyncio
    async def test_parse_block_namespace(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
namespace MyApp.Models {
    public class User {
        public string Name { get; set; }
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="User.cs"
        )

        ns_symbols = [s for s in symbols if s.kind == "namespace"]
        assert len(ns_symbols) == 1
        assert ns_symbols[0].name == "MyApp.Models"

        class_symbols = [s for s in symbols if s.kind == "class"]
        assert len(class_symbols) == 1
        assert class_symbols[0].scope == "MyApp.Models"

    @pytest.mark.asyncio
    async def test_parse_using_directives(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
using System;
using System.Collections.Generic;
using System.Linq;

public class App {
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="App.cs"
        )

        import_refs = [r for r in references if r.reference_type == "import"]
        import_texts = [r.reference_text for r in import_refs]
        assert "System" in import_texts
        assert "System.Collections.Generic" in import_texts
        assert "System.Linq" in import_texts

    @pytest.mark.asyncio
    async def test_parse_using_static(self, parser_service: TreeSitterService) -> None:
        code = """
using static System.Math;

public class App {
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="App.cs"
        )

        import_refs = [r for r in references if r.reference_type == "import"]
        assert len(import_refs) >= 1
        static_imports = [r for r in import_refs if r.metadata.get("is_static")]
        assert len(static_imports) >= 1


class TestCSharpReferences:
    """Tests for C# reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_method_calls(self, parser_service: TreeSitterService) -> None:
        code = """
public class Service {
    public void Process() {
        Initialize();
        Calculate(1, 2);
        Cleanup();
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Service.cs"
        )

        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "Initialize" in call_texts
        assert "Calculate" in call_texts
        assert "Cleanup" in call_texts

    @pytest.mark.asyncio
    async def test_builtin_calls_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Test {
    public void TestMethod() {
        string s = "hello";
        s.ToString();
        s.Equals("world");
        MyMethod();
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Test.cs"
        )

        call_refs = [r for r in references if r.reference_type == "call"]
        call_texts = [r.reference_text for r in call_refs]
        assert "ToString" not in call_texts
        assert "Equals" not in call_texts
        assert "MyMethod" in call_texts

    @pytest.mark.asyncio
    async def test_parse_instantiation(self, parser_service: TreeSitterService) -> None:
        code = """
public class Factory {
    public void Create() {
        var p = new Person("John", 30);
        var obj = new MyObject();
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Factory.cs"
        )

        instantiation_refs = [
            r for r in references if r.reference_type == "instantiation"
        ]
        instantiation_texts = [r.reference_text for r in instantiation_refs]
        assert "Person" in instantiation_texts
        assert "MyObject" in instantiation_texts

    @pytest.mark.asyncio
    async def test_parse_type_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Repository {
    private UserService _userService;
    private DataMapper _mapper;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Repository.cs"
        )

        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        assert "UserService" in type_texts
        assert "DataMapper" in type_texts

    @pytest.mark.asyncio
    async def test_builtin_types_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Calculator {
    public int Add(int a, int b) {
        double result = 0.0;
        bool done = false;
        string name = "test";
        return 0;
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Calculator.cs"
        )

        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        assert "int" not in type_texts
        assert "double" not in type_texts
        assert "bool" not in type_texts
        assert "string" not in type_texts

    @pytest.mark.asyncio
    async def test_parse_attribute_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Controller {
    [HttpGet]
    [Route("api/data")]
    public void HandleRequest() {
    }
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Controller.cs"
        )

        usage_refs = [r for r in references if r.reference_type == "usage"]
        usage_texts = [r.reference_text for r in usage_refs]
        assert "HttpGet" in usage_texts
        assert "Route" in usage_texts

    @pytest.mark.asyncio
    async def test_parse_generic_type_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Container {
    private CustomList<MyItem> _items;
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Container.cs"
        )

        type_refs = [r for r in references if r.reference_type == "type_annotation"]
        type_texts = [r.reference_text for r in type_refs]
        assert "CustomList" in type_texts
        assert "MyItem" in type_texts

    @pytest.mark.asyncio
    async def test_parse_inheritance_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Dog : Animal {
    public void Speak() {}
}

public interface IExtended : IBase, ISerializable {
    void Extra();
}
"""
        _, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Types.cs"
        )

        inheritance_refs = [r for r in references if r.reference_type == "inheritance"]
        inheritance_texts = [r.reference_text for r in inheritance_refs]
        assert "Animal" in inheritance_texts
        assert "IBase" in inheritance_texts
        assert "ISerializable" in inheritance_texts


class TestCSharpComments:
    """Tests for C# comment extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_single_line_comment(self, parser_service: TreeSitterService) -> None:
        code = """
// This is a single line comment
public class Foo {
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="csharp", file_path="Foo.cs"
        )

        single_line = [c for c in comments if c.content_type == "single_line_comment"]
        assert len(single_line) >= 1
        assert any("single line comment" in c.content for c in single_line)

    @pytest.mark.asyncio
    async def test_block_comment(self, parser_service: TreeSitterService) -> None:
        code = """
/* This is a block comment */
public class Foo {
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="csharp", file_path="Foo.cs"
        )

        block = [c for c in comments if c.content_type == "block_comment"]
        assert len(block) >= 1
        assert any("block comment" in c.content for c in block)

    @pytest.mark.asyncio
    async def test_xml_doc_comment(self, parser_service: TreeSitterService) -> None:
        code = """
/// <summary>
/// This is an XML doc comment.
/// </summary>
public class Foo {
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="csharp", file_path="Foo.cs"
        )

        xml_docs = [c for c in comments if c.content_type == "xml_doc_comment"]
        assert len(xml_docs) >= 1


class TestCSharpEdgeCases:
    """Tests for edge cases in C# parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_multiple_classes_in_file(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Main {
    public static void Run() {
    }
}

class Helper {
    void Help() {
    }
}

class Utility {
    static void Util() {
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Main.cs"
        )

        class_symbols = [s for s in symbols if s.kind == "class"]
        class_names = [s.name for s in class_symbols]
        assert "Main" in class_names
        assert "Helper" in class_names
        assert "Utility" in class_names

    @pytest.mark.asyncio
    async def test_parse_delegate_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public delegate void MyCallback(string message);
public delegate int Transformer(int input);
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Delegates.cs"
        )

        delegates = [s for s in symbols if s.kind == "delegate"]
        delegate_names = [s.name for s in delegates]
        assert "MyCallback" in delegate_names
        assert "Transformer" in delegate_names

    @pytest.mark.asyncio
    async def test_parse_event_field_declaration(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Button {
    public event EventHandler Click;
    public event EventHandler DoubleClick;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Button.cs"
        )

        events = [s for s in symbols if s.kind == "event"]
        event_names = [s.name for s in events]
        assert "Click" in event_names
        assert "DoubleClick" in event_names

    @pytest.mark.asyncio
    async def test_parse_constructor_with_base_call(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class Derived : Base {
    public Derived(string name) : base(name) {
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Derived.cs"
        )

        constructors = [s for s in symbols if s.kind == "constructor"]
        assert len(constructors) == 1
        assert constructors[0].name == "Derived"

        inheritance_refs = [r for r in references if r.reference_type == "inheritance"]
        assert any(r.reference_text == "Base" for r in inheritance_refs)

    @pytest.mark.asyncio
    async def test_class_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """[Serializable]
public class MyClass {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="MyClass.cs"
        )

        class_symbols = [s for s in symbols if s.name == "MyClass"]
        assert len(class_symbols) == 1
        # The class name "MyClass" is on line 2, not line 1 where the attribute is
        assert class_symbols[0].start_line == 2

    @pytest.mark.asyncio
    async def test_method_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """public class Test {
    [Obsolete]
    public void MyMethod() {
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Test.cs"
        )

        method_symbols = [s for s in symbols if s.name == "MyMethod"]
        assert len(method_symbols) == 1
        # The method name "MyMethod" is on line 3
        assert method_symbols[0].start_line == 3

    @pytest.mark.asyncio
    async def test_namespace_scoped_types(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
namespace MyApp {
    public class ServiceA {
        public void Run() {}
    }

    public interface IServiceB {
        void Execute();
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Services.cs"
        )

        class_symbols = [s for s in symbols if s.name == "ServiceA"]
        assert len(class_symbols) == 1
        assert class_symbols[0].scope == "MyApp"

        interface_symbols = [s for s in symbols if s.name == "IServiceB"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0].scope == "MyApp"

    @pytest.mark.asyncio
    async def test_struct_with_interface(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public struct Money : IEquatable<Money> {
    public decimal Amount { get; }
    public string Currency { get; }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Money.cs"
        )

        struct_symbols = [s for s in symbols if s.kind == "struct"]
        assert len(struct_symbols) == 1
        assert struct_symbols[0].name == "Money"

    @pytest.mark.asyncio
    async def test_record_with_body(self, parser_service: TreeSitterService) -> None:
        code = """
public record Employee(string Name, int Age) {
    public string Greeting() {
        return "Hello, " + Name;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="Employee.cs"
        )

        record_symbols = [s for s in symbols if s.kind == "record"]
        assert len(record_symbols) == 1

        methods = [s for s in symbols if s.kind == "method"]
        assert any(m.name == "Greeting" for m in methods)

    @pytest.mark.asyncio
    async def test_empty_file(self, parser_service: TreeSitterService) -> None:
        code = ""
        symbols, references = await parser_service.parse_file(
            content=code, language="csharp", file_path="Empty.cs"
        )
        assert symbols == []
        assert references == []

    @pytest.mark.asyncio
    async def test_void_method_signature(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """
public class App {
    public void DoWork() {
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="csharp", file_path="App.cs"
        )

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].signature is not None and "void" in methods[0].signature
        assert methods[0].signature is not None and "DoWork" in methods[0].signature
