"""Symbol kind enumeration."""

from enum import Enum


class SymbolKind(str, Enum):
    """
    Type of code symbol.

    TODO: Expand with language-specific kinds
    TODO: Add methods for grouping/categorization
    """

    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    VARIABLE = "variable"
    CONSTANT = "constant"
    FIELD = "field"
    PROPERTY = "property"
    ENUM = "enum"
    MODULE = "module"
    NAMESPACE = "namespace"

    # C-specific kinds
    STRUCT = "struct"
    UNION = "union"
    TYPEDEF = "typedef"
    MACRO = "macro"
    ENUM_VALUE = "enum_value"
    STRUCT_FIELD = "struct_field"
    UNION_FIELD = "union_field"

    # Java-specific kinds
    ANNOTATION = "annotation"  # @interface definitions
    RECORD = "record"  # Java 14+ record types
    CONSTRUCTOR = "constructor"  # Constructor methods

    # Python-specific kinds
    INSTANCE_VARIABLE = "instance_variable"  # self.x assignments in __init__
    CLASS_VARIABLE = "class_variable"  # Class-level variable assignments

    # TypeScript-specific kinds
    INTERFACE_PROPERTY = "interface_property"  # Properties in TypeScript interfaces
    TYPE = "type"  # TypeScript type aliases
