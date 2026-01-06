"""Reference type enumeration."""

from enum import Enum


class ReferenceType(str, Enum):
    """
    Type of symbol reference.

    Describes the nature of how a symbol is being referenced.
    """

    CALL = "call"  # Function/method call
    IMPORT = "import"  # Import statement
    INHERITANCE = "inheritance"  # Class inheritance
    TYPE_ANNOTATION = "type_annotation"  # Type hint/annotation
    ASSIGNMENT = "assignment"  # Variable assignment
    ATTRIBUTE_ACCESS = "attribute_access"  # Object attribute access
    INSTANTIATION = "instantiation"  # Class instantiation
    DEFINITION = "definition"  # Symbol definition site
    USAGE = "usage"  # Generic usage/reference
