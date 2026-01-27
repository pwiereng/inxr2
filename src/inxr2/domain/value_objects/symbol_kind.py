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
