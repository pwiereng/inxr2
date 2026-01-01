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

    # TODO: Add more kinds as needed:
    # - STRUCT
    # - UNION
    # - TYPEDEF
    # - MACRO
    # - etc.
