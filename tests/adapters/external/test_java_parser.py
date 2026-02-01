"""Tests for Java language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestJavaSupport:
    """Tests for Java language support in TreeSitterService."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    def test_supports_java(self, parser_service: TreeSitterService) -> None:
        """Test that Java is supported."""
        assert parser_service.supports_language("java")
        assert parser_service.supports_language("Java")
        assert parser_service.supports_language("JAVA")


class TestJavaClasses:
    """Tests for Java class parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_class(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple class."""
        code = """
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="HelloWorld.java"
        )

        class_symbols = [s for s in symbols if s["name"] == "HelloWorld"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["kind"] == "class"

    @pytest.mark.asyncio
    async def test_parse_abstract_class(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing an abstract class."""
        code = """
public abstract class Shape {
    public abstract double area();
    public abstract double perimeter();
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Shape.java"
        )

        class_symbols = [s for s in symbols if s["name"] == "Shape"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["kind"] == "class"
        assert class_symbols[0]["is_abstract"] is True

    @pytest.mark.asyncio
    async def test_parse_final_class(self, parser_service: TreeSitterService) -> None:
        """Test parsing a final class."""
        code = """
public final class Constants {
    public static final int MAX_SIZE = 100;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Constants.java"
        )

        class_symbols = [s for s in symbols if s["name"] == "Constants"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["kind"] == "class"
        assert class_symbols[0]["is_final"] is True

    @pytest.mark.asyncio
    async def test_parse_inner_class(self, parser_service: TreeSitterService) -> None:
        """Test parsing inner classes."""
        code = """
public class Outer {
    public class Inner {
        public void doSomething() {}
    }

    public static class StaticInner {
        public void doSomethingElse() {}
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Outer.java"
        )

        outer = [s for s in symbols if s["name"] == "Outer" and s["kind"] == "class"]
        assert len(outer) == 1

        inner = [s for s in symbols if s["name"] == "Inner" and s["kind"] == "class"]
        assert len(inner) == 1
        assert inner[0]["scope"] == "Outer"
        assert inner[0]["is_inner"] is True

        static_inner = [
            s for s in symbols if s["name"] == "StaticInner" and s["kind"] == "class"
        ]
        assert len(static_inner) == 1
        assert static_inner[0]["scope"] == "Outer"
        assert static_inner[0]["is_static"] is True
        # Static nested classes are NOT inner classes in Java terminology
        assert static_inner[0]["is_inner"] is False


class TestJavaInterfaces:
    """Tests for Java interface parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_interface(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a simple interface."""
        code = """
public interface Drawable {
    void draw();
    void resize(int width, int height);
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Drawable.java"
        )

        interface_symbols = [s for s in symbols if s["name"] == "Drawable"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0]["kind"] == "interface"

        methods = [s for s in symbols if s["kind"] == "method"]
        method_names = [s["name"] for s in methods]
        assert "draw" in method_names
        assert "resize" in method_names

    @pytest.mark.asyncio
    async def test_parse_interface_with_default_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing an interface with default methods."""
        code = """
public interface Vehicle {
    void start();

    default void stop() {
        System.out.println("Stopping...");
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Vehicle.java"
        )

        interface_symbols = [s for s in symbols if s["name"] == "Vehicle"]
        assert len(interface_symbols) == 1
        assert interface_symbols[0]["kind"] == "interface"

        # Check that abstract method (no body) is marked abstract
        start_method = [s for s in symbols if s["name"] == "start"][0]
        assert start_method["is_abstract"] is True

        # Check that default method (has body) is NOT marked abstract
        stop_method = [s for s in symbols if s["name"] == "stop"][0]
        assert stop_method["is_abstract"] is False

    @pytest.mark.asyncio
    async def test_parse_interface_constants(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing interface constants."""
        code = """
public interface Config {
    int MAX_CONNECTIONS = 100;
    String DEFAULT_HOST = "localhost";
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Config.java"
        )

        constants = [s for s in symbols if s["kind"] == "constant"]
        constant_names = [s["name"] for s in constants]
        assert "MAX_CONNECTIONS" in constant_names
        assert "DEFAULT_HOST" in constant_names


class TestJavaMethods:
    """Tests for Java method parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_instance_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing instance methods."""
        code = """
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public double multiply(double x, double y) {
        return x * y;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Calculator.java"
        )

        methods = [s for s in symbols if s["kind"] == "method"]
        method_names = [s["name"] for s in methods]
        assert "add" in method_names
        assert "multiply" in method_names

        add_method = [s for s in methods if s["name"] == "add"][0]
        assert add_method["scope"] == "Calculator"
        assert add_method["is_static"] is False
        # Verify primitive return type is captured in signature
        assert "int add(" in add_method["signature"]

        multiply_method = [s for s in methods if s["name"] == "multiply"][0]
        assert "double multiply(" in multiply_method["signature"]

    @pytest.mark.asyncio
    async def test_parse_static_method(self, parser_service: TreeSitterService) -> None:
        """Test parsing static methods."""
        code = """
public class MathUtils {
    public static int square(int n) {
        return n * n;
    }

    public static double sqrt(double n) {
        return Math.sqrt(n);
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="MathUtils.java"
        )

        methods = [s for s in symbols if s["kind"] == "method"]
        for method in methods:
            assert method["is_static"] is True

    @pytest.mark.asyncio
    async def test_parse_abstract_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing abstract methods."""
        code = """
public abstract class Animal {
    public abstract void speak();
    public abstract void move();
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Animal.java"
        )

        methods = [s for s in symbols if s["kind"] == "method"]
        for method in methods:
            assert method["is_abstract"] is True

    @pytest.mark.asyncio
    async def test_method_signature(self, parser_service: TreeSitterService) -> None:
        """Test that method signatures are captured correctly."""
        code = """
public class Service {
    public String processData(String input, int count) {
        return input;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Service.java"
        )

        methods = [s for s in symbols if s["kind"] == "method"]
        assert len(methods) == 1
        assert "signature" in methods[0]
        assert "processData" in methods[0]["signature"]


class TestJavaConstructors:
    """Tests for Java constructor parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_constructor(self, parser_service: TreeSitterService) -> None:
        """Test parsing constructors."""
        code = """
public class Person {
    private String name;
    private int age;

    public Person(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public Person(String name) {
        this(name, 0);
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Person.java"
        )

        constructors = [s for s in symbols if s["kind"] == "constructor"]
        assert len(constructors) == 2
        for constructor in constructors:
            assert constructor["name"] == "Person"
            assert constructor["scope"] == "Person"


class TestJavaFields:
    """Tests for Java field parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_instance_fields(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing instance fields."""
        code = """
public class User {
    private String username;
    private String email;
    protected int age;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="User.java"
        )

        fields = [s for s in symbols if s["kind"] == "field"]
        field_names = [s["name"] for s in fields]
        assert "username" in field_names
        assert "email" in field_names
        assert "age" in field_names

        for field in fields:
            assert field["scope"] == "User"
            assert field["is_static"] is False

    @pytest.mark.asyncio
    async def test_parse_static_fields(self, parser_service: TreeSitterService) -> None:
        """Test parsing static fields."""
        code = """
public class Counter {
    private static int count = 0;
    private static String prefix = "item_";
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Counter.java"
        )

        fields = [s for s in symbols if s["kind"] == "field"]
        for field in fields:
            assert field["is_static"] is True

    @pytest.mark.asyncio
    async def test_parse_constants(self, parser_service: TreeSitterService) -> None:
        """Test parsing static final fields as constants."""
        code = """
public class Constants {
    public static final int MAX_VALUE = 100;
    public static final String APP_NAME = "MyApp";
    private static final double PI = 3.14159;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Constants.java"
        )

        constants = [s for s in symbols if s["kind"] == "constant"]
        constant_names = [s["name"] for s in constants]
        assert "MAX_VALUE" in constant_names
        assert "APP_NAME" in constant_names
        assert "PI" in constant_names


class TestJavaEnums:
    """Tests for Java enum parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_enum(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple enum."""
        code = """
public enum Color {
    RED,
    GREEN,
    BLUE
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Color.java"
        )

        enum_symbols = [s for s in symbols if s["kind"] == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0]["name"] == "Color"

        enum_values = [s for s in symbols if s["kind"] == "enum_value"]
        value_names = [s["name"] for s in enum_values]
        assert "RED" in value_names
        assert "GREEN" in value_names
        assert "BLUE" in value_names

    @pytest.mark.asyncio
    async def test_parse_enum_with_constructor(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing an enum with constructor and fields."""
        code = """
public enum Planet {
    MERCURY(3.303e+23, 2.4397e6),
    VENUS(4.869e+24, 6.0518e6),
    EARTH(5.976e+24, 6.37814e6);

    private final double mass;
    private final double radius;

    Planet(double mass, double radius) {
        this.mass = mass;
        this.radius = radius;
    }

    public double getMass() {
        return mass;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Planet.java"
        )

        enum_symbols = [s for s in symbols if s["kind"] == "enum"]
        assert len(enum_symbols) == 1
        assert enum_symbols[0]["name"] == "Planet"

        enum_values = [s for s in symbols if s["kind"] == "enum_value"]
        value_names = [s["name"] for s in enum_values]
        assert "MERCURY" in value_names
        assert "VENUS" in value_names
        assert "EARTH" in value_names

        # Should also find the constructor and methods
        constructors = [s for s in symbols if s["kind"] == "constructor"]
        assert any(c["name"] == "Planet" for c in constructors)

        methods = [s for s in symbols if s["kind"] == "method"]
        assert any(m["name"] == "getMass" for m in methods)

    @pytest.mark.asyncio
    async def test_enum_value_scope(self, parser_service: TreeSitterService) -> None:
        """Test that enum values have correct scope."""
        code = """
public enum Direction {
    NORTH, SOUTH, EAST, WEST
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Direction.java"
        )

        enum_values = [s for s in symbols if s["kind"] == "enum_value"]
        for value in enum_values:
            assert value["scope"] == "Direction"


class TestJavaAnnotations:
    """Tests for Java annotation type (@interface) parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_annotation_type(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing an annotation type definition."""
        code = """
public @interface MyAnnotation {
    String value() default "";
    int priority() default 0;
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="MyAnnotation.java"
        )

        annotation_symbols = [s for s in symbols if s["kind"] == "annotation"]
        assert len(annotation_symbols) == 1
        assert annotation_symbols[0]["name"] == "MyAnnotation"


class TestJavaRecords:
    """Tests for Java record parsing (Java 14+)."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_simple_record(self, parser_service: TreeSitterService) -> None:
        """Test parsing a simple record."""
        code = """
public record Point(int x, int y) {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Point.java"
        )

        record_symbols = [s for s in symbols if s["kind"] == "record"]
        assert len(record_symbols) == 1
        assert record_symbols[0]["name"] == "Point"

        # Record components should be extracted as fields
        fields = [s for s in symbols if s["kind"] == "field"]
        field_names = [s["name"] for s in fields]
        assert "x" in field_names
        assert "y" in field_names

    @pytest.mark.asyncio
    async def test_parse_record_with_methods(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a record with additional methods."""
        code = """
public record Person(String name, int age) {
    public String greeting() {
        return "Hello, " + name;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Person.java"
        )

        record_symbols = [s for s in symbols if s["kind"] == "record"]
        assert len(record_symbols) == 1
        assert record_symbols[0]["name"] == "Person"

        methods = [s for s in symbols if s["kind"] == "method"]
        assert any(m["name"] == "greeting" for m in methods)


class TestJavaReferences:
    """Tests for Java reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_import_statements(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing import statements."""
        code = """
import java.util.List;
import java.util.ArrayList;
import java.io.*;
import static java.lang.Math.PI;

public class App {
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="App.java"
        )

        import_refs = [r for r in references if r["type"] == "import"]
        import_texts = [r["text"] for r in import_refs]
        assert "java.util.List" in import_texts
        assert "java.util.ArrayList" in import_texts
        assert "java.io.*" in import_texts
        assert "java.lang.Math.PI" in import_texts

    @pytest.mark.asyncio
    async def test_parse_method_calls(self, parser_service: TreeSitterService) -> None:
        """Test parsing method calls."""
        code = """
public class Service {
    public void process() {
        initialize();
        calculate(1, 2);
        cleanup();
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Service.java"
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
        """Test that common Java methods are filtered out."""
        code = """
public class Test {
    public void test() {
        String s = "hello";
        s.toString();
        s.equals("world");
        myMethod();
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Test.java"
        )

        call_refs = [r for r in references if r["type"] == "call"]
        call_texts = [r["text"] for r in call_refs]
        # Builtins should be filtered
        assert "toString" not in call_texts
        assert "equals" not in call_texts
        # Custom method should remain
        assert "myMethod" in call_texts

    @pytest.mark.asyncio
    async def test_parse_constructor_calls(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing constructor calls (new expressions)."""
        code = """
public class Factory {
    public void create() {
        Person p = new Person("John", 30);
        MyObject obj = new MyObject();
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Factory.java"
        )

        instantiation_refs = [r for r in references if r["type"] == "instantiation"]
        instantiation_texts = [r["text"] for r in instantiation_refs]
        assert "Person" in instantiation_texts
        assert "MyObject" in instantiation_texts

    @pytest.mark.asyncio
    async def test_parse_type_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing type references."""
        code = """
public class Repository {
    private UserService userService;
    private DataMapper mapper;

    public void process(CustomType input) {
        AnotherType result = null;
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Repository.java"
        )

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        assert "UserService" in type_texts
        assert "DataMapper" in type_texts
        assert "CustomType" in type_texts
        assert "AnotherType" in type_texts

    @pytest.mark.asyncio
    async def test_primitive_types_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that primitive types are filtered from references."""
        code = """
public class Calculator {
    public int add(int a, int b) {
        double result = 0.0;
        boolean done = false;
        return 0;
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Calculator.java"
        )

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        # Primitives should be filtered
        assert "int" not in type_texts
        assert "double" not in type_texts
        assert "boolean" not in type_texts


class TestJavaInheritance:
    """Tests for Java inheritance references."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_extends_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing extends references."""
        code = """
public class Dog extends Animal {
    public void speak() {
        System.out.println("Woof!");
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Dog.java"
        )

        inheritance_refs = [r for r in references if r["type"] == "inheritance"]
        inheritance_texts = [r["text"] for r in inheritance_refs]
        assert "Animal" in inheritance_texts

    @pytest.mark.asyncio
    async def test_parse_implements_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing implements references."""
        code = """
public class Circle implements Drawable, Resizable {
    public void draw() {}
    public void resize(int size) {}
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Circle.java"
        )

        inheritance_refs = [r for r in references if r["type"] == "inheritance"]
        inheritance_texts = [r["text"] for r in inheritance_refs]
        assert "Drawable" in inheritance_texts
        assert "Resizable" in inheritance_texts

    @pytest.mark.asyncio
    async def test_parse_interface_extends_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing interface extends references."""
        code = """
public interface ExtendedDrawable extends Drawable, Printable {
    void extraMethod();
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="ExtendedDrawable.java"
        )

        inheritance_refs = [r for r in references if r["type"] == "inheritance"]
        inheritance_texts = [r["text"] for r in inheritance_refs]
        assert "Drawable" in inheritance_texts
        assert "Printable" in inheritance_texts


class TestJavaEdgeCases:
    """Tests for edge cases in Java parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_generic_class(self, parser_service: TreeSitterService) -> None:
        """Test parsing a generic class."""
        code = """
public class Box<T> {
    private T content;

    public void set(T content) {
        this.content = content;
    }

    public T get() {
        return content;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Box.java"
        )

        class_symbols = [s for s in symbols if s["name"] == "Box"]
        assert len(class_symbols) == 1
        assert class_symbols[0]["kind"] == "class"

    @pytest.mark.asyncio
    async def test_parse_generic_type_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing generic type references."""
        code = """
public class Container {
    private CustomList<MyItem> items;
    private CustomMap<String, MyValue> mapping;
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Container.java"
        )

        type_refs = [r for r in references if r["type"] == "type_annotation"]
        type_texts = [r["text"] for r in type_refs]
        assert "CustomList" in type_texts
        assert "MyItem" in type_texts
        assert "CustomMap" in type_texts
        assert "MyValue" in type_texts

    @pytest.mark.asyncio
    async def test_parse_lambda_containing_class(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing a class containing lambdas."""
        code = """
public class StreamProcessor {
    public void process() {
        items.stream()
            .filter(item -> item.isValid())
            .map(item -> item.transform())
            .collect(Collectors.toList());
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="StreamProcessor.java"
        )

        class_symbols = [s for s in symbols if s["name"] == "StreamProcessor"]
        assert len(class_symbols) == 1

    @pytest.mark.asyncio
    async def test_parse_annotation_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing annotation usage references."""
        code = """
public class Controller {
    @CustomAnnotation
    @AnotherAnnotation(value = "test")
    public void handleRequest() {
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Controller.java"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_texts = [r["text"] for r in usage_refs]
        assert "CustomAnnotation" in usage_texts
        assert "AnotherAnnotation" in usage_texts

    @pytest.mark.asyncio
    async def test_parse_field_access(self, parser_service: TreeSitterService) -> None:
        """Test parsing field access references."""
        code = """
public class Example {
    public void test() {
        config.setting = 10;
        myObject.field = "value";
    }
}
"""
        symbols, references = await parser_service.parse_file(
            content=code, language="java", file_path="Example.java"
        )

        usage_refs = [r for r in references if r["type"] == "usage"]
        usage_texts = [r["text"] for r in usage_refs]
        assert "config" in usage_texts
        assert "setting" in usage_texts
        assert "myObject" in usage_texts
        assert "field" in usage_texts

    @pytest.mark.asyncio
    async def test_parse_multiple_classes_in_file(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing multiple classes in a single file."""
        code = """
public class Main {
    public static void main(String[] args) {
    }
}

class Helper {
    void help() {
    }
}

class Utility {
    static void util() {
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Main.java"
        )

        class_symbols = [s for s in symbols if s["kind"] == "class"]
        class_names = [s["name"] for s in class_symbols]
        assert "Main" in class_names
        assert "Helper" in class_names
        assert "Utility" in class_names

    @pytest.mark.asyncio
    async def test_class_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that class symbol start_line points to the class name."""
        code = """@Annotation
public class MyClass {
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="MyClass.java"
        )

        class_symbols = [s for s in symbols if s["name"] == "MyClass"]
        assert len(class_symbols) == 1
        # The class name "MyClass" is on line 2, not line 1 where the annotation is
        assert class_symbols[0]["start_line"] == 2

    @pytest.mark.asyncio
    async def test_method_symbol_line_points_to_name(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that method symbol start_line points to the method name."""
        code = """public class Test {
    @Override
    public void myMethod() {
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Test.java"
        )

        method_symbols = [s for s in symbols if s["name"] == "myMethod"]
        assert len(method_symbols) == 1
        # The method name "myMethod" is on line 3
        assert method_symbols[0]["start_line"] == 3

    @pytest.mark.asyncio
    async def test_parse_varargs_method(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing methods with varargs parameters."""
        code = """
public class Formatter {
    public String format(String template, Object... args) {
        return template;
    }
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="java", file_path="Formatter.java"
        )

        methods = [s for s in symbols if s["kind"] == "method"]
        assert len(methods) == 1
        assert methods[0]["name"] == "format"
